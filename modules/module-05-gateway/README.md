# Module 05 — Gateway: Connecting Real Tools

In this module you will connect Aria to the ShopSmart backend — real Lambda
functions backed by DynamoDB. Aria moves from answering only FAQ questions to
looking up actual orders, searching the product catalog, and submitting support
requests on behalf of customers.

Tools are routed through **AgentCore Gateway** using the ShopSmart REST API as
an HTTP target. The Gateway parses the OpenAPI spec, exposes each API operation
as an MCP tool, and the agent discovers them automatically — no hardcoded tool
definitions in agent code.

---

## What You Will Build

```
aria-agent (Runtime)
    │  discovers + calls tools via MCP
    ▼
AgentCore Gateway
    │  routes to HTTP target using OpenAPI spec
    ▼
ShopSmart REST API (API Gateway)
    ├── GET  /orders           → list_orders Lambda    → DynamoDB
    ├── GET  /orders/{id}      → get_order Lambda      → DynamoDB
    ├── GET  /products         → search_products Lambda → DynamoDB
    ├── GET  /products/{id}    → get_product Lambda    → DynamoDB
    └── POST /requests         → submit_request Lambda → DynamoDB
```

The API Gateway methods require `AWS_IAM`. AgentCore Gateway signs outbound
requests with SigV4 using its Gateway service role, while the Runtime role
authenticates the Runtime-to-Gateway connection.

<details>
<summary>Why HTTP target instead of Lambda target?</summary>

AgentCore Gateway supports both Lambda and HTTP targets. We use HTTP because:

- The ShopSmart backend already has a REST API (deployed by CloudFormation)
- The existing Lambda functions stay completely unchanged
- OpenAPI specs are the industry-standard way to describe REST APIs
- HTTP targets are more representative of real-world usage — most backends
  already have an HTTP API

Lambda targets make sense when you're writing a new Lambda specifically to
serve as a tool, with no HTTP layer in front of it.

</details>

<details>
<summary>How This Differs from Module 04</summary>

| | Module 04 — Runtime | Module 05 — Gateway |
|---|---|---|
| Knowledge source | Knowledge Base only | Knowledge Base + Live backend |
| Order lookup | Not possible | Real DynamoDB orders |
| Product search | Not possible | Real DynamoDB products |
| Return requests | Not possible | Submitted via REST API |
| Tool routing | N/A | AgentCore Gateway (MCP) |
| Policy ready | No | Yes — Gateway is the hook |

</details>

---

## Step 1 — Deploy the ShopSmart Backend

### 1a. Create an S3 bucket for Lambda deployment packages

```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export BUCKET=shopsmart-lambda-$AWS_ACCOUNT_ID

aws s3 mb s3://$BUCKET --region $AWS_REGION
```

### 1b. Package and upload Lambda code

```bash
cd shopsmart-backend/lambdas
for f in list_orders get_order get_product search_products submit_request; do
  zip ${f}.zip ${f}.py
  aws s3 cp ${f}.zip s3://$BUCKET/lambdas/${f}.zip
done
cd ../..
```

### 1c. Deploy the CloudFormation stack

```bash
aws cloudformation deploy \
  --template-file shopsmart-backend/cloudformation/shopsmart-backend.yaml \
  --stack-name shopsmart-backend \
  --parameter-overrides \
      Environment=dev \
      LambdaCodeBucket=$BUCKET \
  --capabilities CAPABILITY_NAMED_IAM \
  --region $AWS_REGION
```

Wait for `CREATE_COMPLETE`. Then note the API base URL:

```bash
aws cloudformation describe-stacks \
  --stack-name shopsmart-backend \
  --query "Stacks[0].Outputs[?OutputKey=='ApiBaseUrl'].OutputValue" \
  --output text --region $AWS_REGION
```

Note down the `ApiBaseUrl` — you'll need it in Step 3 and Step 4.

---

## Step 2 — Seed the Database

```bash
export AWS_REGION=us-east-1
export ENVIRONMENT=dev
python shopsmart-backend/seed_data.py
```

Expected output:
```
✅ All done! Tables are ready for use.

Test customers:
  C001 — Alice Johnson (2 orders: delivered, shipped)
  C002 — Bob Smith     (1 order: processing)
  C003 — Carol White   (1 order: delivered, with return request)
```

### Verify API authentication

The API methods require AWS Signature Version 4 (`AWS_IAM`). An unsigned
request must fail, while a request signed by an IAM principal with
`execute-api:Invoke` permission must succeed.

First set the API URL and region:

```bash
export AWS_REGION=us-east-1
export API_URL=$(aws cloudformation describe-stacks \
  --stack-name shopsmart-backend \
  --query "Stacks[0].Outputs[?OutputKey=='ApiBaseUrl'].OutputValue" \
  --output text --region $AWS_REGION)
```

#### Negative test: unsigned request

```bash
curl -i "$API_URL/orders?customerId=C001"
```

Expected result: `403 Forbidden`. This confirms that anonymous callers cannot
invoke the backend.

#### Signed test: Python validator

The repository includes a small validator that uses the AWS SDK credential
chain and botocore to sign requests. It does not require a third-party CLI:

```bash
python modules/module-05-gateway/validate_api.py \
  --base-url "$API_URL" \
  --region "$AWS_REGION"
```

The IAM identity running this command needs `execute-api:Invoke` permission on
the API. The script checks list orders, get order, and product search. Use a
named profile when needed:

```bash
AWS_PROFILE=shopsmart-admin python modules/module-05-gateway/validate_api.py \
  --base-url "$API_URL" \
  --region "$AWS_REGION"
```

`awscurl` is an optional community alternative for interactive checks:

```bash
awscurl --service execute-api --region "$AWS_REGION" \
  "$API_URL/orders?customerId=C001"
```

#### End-to-end test through AgentCore Gateway

After configuring the Gateway target with IAM outbound authorization, test the
actual tool path in the Streamlit UI. The Gateway service role, rather than
your local developer identity, must have `execute-api:Invoke` permission.

Try these prompts:

- `My customer ID is C001. What are my orders?`
- `Tell me about order ORD-1001`
- `Search for backpacks`
- `I want to return order ORD-1001`
- `What is your return policy?` — still works via Knowledge Base


---

## Step 3 — Create the AgentCore Gateway

### Via AWS Console

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Gateways**
2. Click **Create gateway**
3. **Gateway details**:
   - **Gateway name**: `shopsmart-gateway`
   - Expand **Additional configurations**:
     - **Description**: `ShopSmart tool gateway — orders, products, returns`
     - **Exception level debug**: ✅ enabled (helpful during development)

4. **Inbound Auth configurations**: select **IAM**
   > The agent's execution role signs requests to the Gateway with SigV4 —
   > no separate JWT config needed here.

5. **Permissions**:
   - Select **Use an IAM service role**
   - Choose **Create and use a new service role**

6. **Target** — configure the ShopSmart REST API:
   - **Target name**: `ShopSmartAPI`
   - **Target type**: HTTP
   - **Endpoint URL**: paste your `ApiBaseUrl` from Step 1c
     (e.g. `https://abc123.execute-api.us-east-1.amazonaws.com/dev`)
   - **API schema**: select **Inline** and paste the contents of
     `modules/module-05-gateway/shopsmart-api.yaml`
     — but first replace `<API_BASE_URL>` in the `servers.url` field with
     your actual ApiBaseUrl
   - **Outbound Auth**: IAM / SigV4
     - Use the Gateway service role for credentials
     - Configure the AWS service as `execute-api`
     - Use the same AWS Region as the API Gateway REST API

   The Gateway service role must be allowed to invoke this API. Add an IAM
   policy like the following to that role, replacing the placeholders with the
   values from the CloudFormation outputs:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": "execute-api:Invoke",
         "Resource": "arn:aws:execute-api:<REGION>:<ACCOUNT_ID>:<API_ID>/<ENVIRONMENT>/*/*"
       }
     ]
   }
   ```

   You can retrieve the API ID with:

   ```bash
   aws cloudformation describe-stacks \
     --stack-name shopsmart-backend \
     --query "Stacks[0].Outputs[?OutputKey=='ApiId'].OutputValue" \
     --output text --region "$AWS_REGION"
   ```

7. Click **Create gateway**

8. Note down from the gateway detail page:
   - **Gateway ARN** — needed for Cedar policies in Module 08
   - **Gateway endpoint URL** — needed for agent code in Step 5

> **Tool naming**: AgentCore Gateway names each tool as
> `<TargetName>___<operationId>`. With target name `ShopSmartAPI` and
> operationId `list_orders`, the MCP tool name visible to the agent is
> `ShopSmartAPI___list_orders`. This is what you'll reference in Cedar
> policies in Module 08.

---

## Step 4 — Grant the Agent Permission to Invoke the Gateway

The agent runs inside AgentCore Runtime using `AriaAgentExecutionRole`. That
role needs `bedrock-agentcore:InvokeGateway` permission on the Gateway,
otherwise the `MCPClient` connection will fail with an authorization error.

### Via AWS Console

1. Go to **AWS Console → IAM → Roles → AriaAgentExecutionRole**
2. Click **Add permissions → Create inline policy**
3. Switch to **JSON** and paste:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "bedrock-agentcore:InvokeGateway",
      "Resource": "<GATEWAY_ARN>"
    }
  ]
}
```

Replace `<GATEWAY_ARN>` with the Gateway ARN from Step 3
(e.g. `arn:aws:bedrock-agentcore:us-east-1:<account>:gateway/shopsmart-gateway-XXXXXXXXXX`)

4. **Policy name**: `Gateway_Permissions`
5. Click **Create policy**

### Via CLI (Optional)

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1

GATEWAY_ARN=$(aws bedrock-agentcore-control get-gateway \
  --gateway-identifier <your-gateway-id> \
  --region $AWS_REGION \
  --query 'gatewayArn' --output text)

aws iam put-role-policy \
  --role-name AriaAgentExecutionRole \
  --policy-name Gateway_Permissions \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Action\": \"bedrock-agentcore:InvokeGateway\",
      \"Resource\": \"${GATEWAY_ARN}\"
    }]
  }"
```

---

## Step 5 — Save the Gateway Endpoint to SSM

### Via CLI (Optional)

```bash
export GATEWAY_ENDPOINT=<your-gateway-endpoint-url>

aws ssm put-parameter \
  --name /aria/gateway_endpoint \
  --value "$GATEWAY_ENDPOINT" \
  --type String \
  --overwrite \
  --region $AWS_REGION
```

---

## Step 6 — Update the Agent

```bash
cp modules/module-05-gateway/agent.py aria-agent/agent.py
cp modules/module-05-gateway/config.py aria-agent/config.py
cp modules/module-05-gateway/requirements.txt aria-agent/requirements.txt
cp modules/module-05-gateway/Dockerfile aria-agent/Dockerfile
cp modules/module-05-gateway/app.py streamlit-ui/app.py
```

<details>
<summary>What changed in agent.py</summary>

Tools are no longer defined with `@tool` decorators in agent code. Instead,
the agent connects to the Gateway MCP endpoint at invocation time and receives
the full tool list dynamically.

Because the Gateway uses **IAM (AWS_IAM) inbound auth**, MCP requests must be
signed with SigV4 using the container's execution role. The
`mcp-proxy-for-aws` library provides `aws_iam_streamablehttp_client` which
handles the signing automatically:

```python
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from strands.tools.mcp import MCPClient

mcp_client = MCPClient(
    lambda: aws_iam_streamablehttp_client(
        endpoint=cfg.gateway_endpoint,
        aws_region=cfg.region,
        aws_service="bedrock-agentcore",
    )
)
with mcp_client:
    gateway_tools = mcp_client.list_tools_sync()
    agent = Agent(
        model=cfg.model_id,
        tools=[retrieve_from_knowledge_base] + gateway_tools,
    )
    result = agent(user_message)
```

This adds `mcp-proxy-for-aws` to `requirements.txt`. The Knowledge Base tool
is still defined locally since it calls Bedrock directly and doesn't go
through the Gateway.

</details>

<details>
<summary>What changed in config.py</summary>

`api_base_url` is replaced by `gateway_endpoint` — the agent no longer calls
the ShopSmart API directly, so it doesn't need the API URL. It only needs the
Gateway MCP endpoint to discover and invoke tools.

</details>

---

## Step 7 — Rebuild and Deploy

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1
export ECR_REPO=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aria-agent

aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS --password-stdin \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

cd aria-agent
docker build --platform linux/arm64 -t aria-agent .
docker tag aria-agent:latest $ECR_REPO:latest
docker push $ECR_REPO:latest
cd ..

RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes \
  --region $AWS_REGION \
  --query "agentRuntimes[?agentRuntimeName=='aria'].agentRuntimeId" \
  --output text)

aws bedrock-agentcore-control update-agent-runtime \
  --agent-runtime-id $RUNTIME_ID \
  --agent-runtime-artifact "{\"containerConfiguration\":{\"containerUri\":\"$ECR_REPO:latest\"}}" \
  --role-arn "arn:aws:iam::$AWS_ACCOUNT_ID:role/AriaAgentExecutionRole" \
  --network-configuration '{"networkMode":"PUBLIC"}' \
  --description "Module 05 — Gateway tools" \
  --region $AWS_REGION
```

Wait for the runtime status to return to **Ready**.

---

## Step 8 — Test

The API authentication checks above validate the backend directly. Now test
the complete tool path through AgentCore Gateway in the Streamlit UI:

- `What are my orders?` — Aria asks for customer ID, then lists from DynamoDB
- `My customer ID is C001. What are my orders?`
- `Tell me about order ORD-1001`
- `Search for backpacks`
- `I want to return order ORD-1001`
- `What is your return policy?` — still works via Knowledge Base

The successful direct validator uses your local IAM principal. The successful
Streamlit test uses the AgentCore Gateway service role for the API call. These
are separate authorization checks and both should pass.

---

<details>
<summary>Troubleshooting</summary>

**Agent can't reach the Gateway / tools not found**

- Check `/aria/gateway_endpoint` in SSM — the URL must include the full path
- Verify the Gateway status is **Active** in the console
- Check the agent execution role has `bedrock-agentcore:InvokeGateway`
  permission on the gateway ARN

**Gateway returns errors when calling the API**

- Enable **Exception level debug** on the Gateway to see detailed error messages
- Check CloudWatch logs under `/aws/bedrock-agentcore/gateway/`
- Confirm the `servers.url` in the OpenAPI spec exactly matches your `ApiBaseUrl`

**Tool names in errors look like `ShopSmartAPI___list_orders`**

- This is expected — AgentCore Gateway prefixes tool names with the target
  name. The agent handles this transparently via MCP.

</details>

<details>
<summary>What You Learned</summary>

- How AgentCore Gateway acts as a unified MCP server for all tools
- How to register a REST API as an HTTP Gateway target using an OpenAPI spec
- How the Gateway parses the spec and exposes each operation as an MCP tool
- How agents discover and call Gateway tools via MCP without hardcoded definitions
- How to protect API Gateway methods with AWS_IAM and SigV4
- How to configure AgentCore Gateway outbound IAM authorization
- How to validate anonymous denial, signed API access, and the end-to-end tool path
- Why the Gateway architecture enables Policy (Module 08) and Observability
  (Module 09) with no agent code changes

</details>

---

## Next Step

Proceed to [Module 06 — Memory](../module-06-memory/README.md) where you will
add persistent memory to Aria so she remembers customers across sessions.
