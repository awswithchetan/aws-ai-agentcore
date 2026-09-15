# Module 05 — Gateway: Connecting Real Tools

In this module you will connect Aria to the ShopSmart backend — the ShopSmart
REST API, backed by Lambda functions and DynamoDB. Aria moves from answering
only FAQ questions to looking up actual orders, searching the product catalog,
and submitting support requests on behalf of customers.

Tools are routed through **AgentCore Gateway** using the ShopSmart REST API as
an HTTP target. The Gateway parses the OpenAPI spec, exposes each API operation
as an MCP tool, and the agent discovers them automatically — no hardcoded tool
definitions in agent code. The Lambda functions and DynamoDB tables behind the
API are an implementation detail the agent never sees; it only calls API
operations.

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

The backend tables (`shopsmart-orders` and `shopsmart-products`) are created empty
by CloudFormation. This step loads realistic sample data so Aria's tools have
something to return — a product catalog to search and orders to look up. It writes
directly to DynamoDB using Boto3 and is idempotent, so you can safely re-run it.

```bash
export AWS_REGION=us-east-1
python shopsmart-backend/seed_data.py
```

Expected output:
```
✅ All done! Tables are ready for use.

Test customers (5 orders each):
  C001 — Alice Johnson (delivered, shipped, processing, delivered >$500, delivered + open return)
  C002 — Bob Smith     (processing, shipped, delivered, shipped >$500, cancelled)
  C003 — Carol White   (delivered + open return, delivered, shipped, processing, delivered)

High-value orders (> $500, for order-value policy flows): ORD-1004 (C001), ORD-1009 (C002)
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

#### Unauthenticated request (should fail)

```bash
curl -i "$API_URL/orders?customerId=C001"
```

Expected result: `403 Forbidden`. This confirms that anonymous callers cannot
invoke the backend.

#### Authenticated API test with awscurl

[`awscurl`](https://github.com/okigan/awscurl) signs requests with SigV4 using
the AWS SDK credential chain, so it's the quickest way to confirm a signed
request succeeds. It was installed with the course dependencies in Module 00
(run `pip install awscurl` if it isn't on your PATH).

```bash
awscurl --service execute-api --region "$AWS_REGION" \
  "$API_URL/orders?customerId=C001"
```

Expected result: a `200` response with Alice Johnson's orders. The IAM identity
running this command needs `execute-api:Invoke` permission on the API.

<details>
<summary>Alternative — authenticated API test with the Python validator (no third-party CLI)</summary>

If you prefer not to install `awscurl`, the repository includes a small
validator that uses botocore and the AWS SDK credential chain to sign requests:

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

</details>

---

## Step 3 — Create the AgentCore Gateway

### 3a. Create the Gateway service role

The Gateway assumes this role to call the ShopSmart API on the agent's behalf.
It needs a trust policy for the AgentCore service and `execute-api:Invoke` on
the API.

#### Via AWS Console

1. Go to **AWS Console → IAM → Roles → Create role**
2. **Trusted entity type**: **AWS service**
3. **Use case**: scroll down and select **Amazon Bedrock AgentCore** — this
   automatically configures the correct trust policy
4. Click **Next**, then skip attaching managed policies and click **Next** again
5. **Role name**: `ShopSmartGatewayRole`, then click **Create role**
6. Open the role → **Add permissions → Create inline policy** → **JSON**, and paste
   the `execute-api:Invoke` policy below. Replace `<REGION>`, `<ACCOUNT_ID>`, and
   `<API_ID>` with your values (find `<API_ID>` in the `ApiId` CloudFormation output).
   Name it `ShopSmartApiInvoke`.
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": "execute-api:Invoke",
         "Resource": "arn:aws:execute-api:<REGION>:<ACCOUNT_ID>:<API_ID>/prod/*/*"
       }
     ]
   }
   ```

<details>
<summary>Via CLI (Optional)</summary>

```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export API_ID=$(aws cloudformation describe-stacks \
  --stack-name shopsmart-backend \
  --query "Stacks[0].Outputs[?OutputKey=='ApiId'].OutputValue" \
  --output text --region "$AWS_REGION")

aws iam create-role \
  --role-name ShopSmartGatewayRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "GatewayAssumeRolePolicy",
        "Effect": "Allow",
        "Principal": { "Service": "bedrock-agentcore.amazonaws.com" },
        "Action": "sts:AssumeRole"
      }
    ]
  }'

aws iam put-role-policy \
  --role-name ShopSmartGatewayRole \
  --policy-name ShopSmartApiInvoke \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Action\": \"execute-api:Invoke\",
      \"Resource\": \"arn:aws:execute-api:${AWS_REGION}:${AWS_ACCOUNT_ID}:${API_ID}/prod/*/*\"
    }]
  }"
```

</details>

### 3b. Create the gateway (Console)

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Gateways**
2. Click **Create gateway**
3. **Gateway details**:
   - **Gateway name**: `shopsmart-gateway`
   - Expand **Additional configurations**:
     - **Description**: `ShopSmart tool gateway — orders, products, returns`
     - **Exception level debug**: ✅ enabled (helpful during development)

4. **Inbound Auth configurations**: select **Use IAM Permission**
   > The agent's execution role signs requests to the Gateway with SigV4 —
   > no separate JWT config needed here.

5. **Permissions**:
   - Select **Use an IAM service role**
   - Choose **Use an existing service role** and select `ShopSmartGatewayRole`
     (created in step 3a)

6. **Target** — configure the ShopSmart REST API:
   - **Target protocol**: **MCP Target**
   - **Target name**: `ShopSmartAPI`
   - **Passthrough**: leave the default **Do not use passthrough — default aggregated**
   - **Target type**: **REST API**
     (other options include MCP Server, Lambda ARN, API Gateway, and Connectors)
   - **REST API type**: **OpenAPI schema**
   - **Schema**: paste the contents of `modules/module-05-gateway/shopsmart-api.yaml`
     into the inline schema box — but first replace `<API_BASE_URL>` in the
     `servers.url` field with your `ApiBaseUrl` from Step 1c
     (e.g. `https://abc123.execute-api.us-east-1.amazonaws.com/prod`)
   - **Outbound Auth configuration**: **IAM Role**
     - **Service**: `execute-api`
     - **Region** (optional): the same Region as the API Gateway REST API
   - **Additional configurations**: no extra headers or query parameters are needed

   Selecting **IAM Role** here sets the outbound auth type only — there's no role
   picker. The Gateway signs the outbound call with the service role you selected
   in step 5 (`ShopSmartGatewayRole`), which already carries the
   `execute-api:Invoke` permission from step 3a.

7. Click **Create gateway**

8. Note down from the gateway detail page:
   - **Gateway Resource ARN** — needed for Cedar policies in Module 08 and agent code in Step 5
   - **Gateway Resource URL** — needed for agent code in Step 5

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

4. **Policy name**: `AriaAgentGatewayPermissions`
5. Click **Create policy**

<details>
<summary>Via CLI (Optional)</summary>

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1

GATEWAY_ARN=$(aws bedrock-agentcore-control get-gateway \
  --gateway-identifier <your-gateway-id> \
  --region $AWS_REGION \
  --query 'gatewayArn' --output text)

aws iam put-role-policy \
  --role-name AriaAgentExecutionRole \
  --policy-name AriaAgentGatewayPermissions \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Action\": \"bedrock-agentcore:InvokeGateway\",
      \"Resource\": \"${GATEWAY_ARN}\"
    }]
  }"
```

</details>

---

## Step 5 — Save the Gateway Endpoint to SSM

Store the Gateway Resource URL from Step 3 in SSM so the agent can read it at
startup (the same pattern used for the other `/aria/` parameters).

### Via AWS Console

1. Go to **AWS Console → Systems Manager → Parameter Store → Create parameter**
2. Configure:
   - **Name**: `/aria/gateway_endpoint`
   - **Tier**: Standard
   - **Type**: String
   - **Value**: your Gateway Resource URL from Step 3
3. Click **Create parameter**

<details>
<summary>Via CLI (Optional)</summary>

```bash
export GATEWAY_ENDPOINT=<your-gateway-endpoint-url>

aws ssm put-parameter \
  --name /aria/gateway_endpoint \
  --value "$GATEWAY_ENDPOINT" \
  --type String \
  --overwrite \
  --region $AWS_REGION
```

</details>

---

## Step 6 — Update the Agent Code to Use Gateway Tools

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
the complete tool path through AgentCore Gateway in the Streamlit UI.

Make sure you copied the Module 05 `app.py` to `streamlit-ui/app.py` in Step 6,
then launch it:

```bash
export ARIA_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:$AWS_ACCOUNT_ID:runtime/<your-runtime-id>"
export AWS_REGION="us-east-1"
streamlit run streamlit-ui/app.py
```

Aria does not know who the customer is yet (that comes with Memory in Module 06),
so she asks for the customer ID in the conversation when she needs one. Try these
prompts:

- `What are my orders?` — Aria asks for your customer ID, then lists from DynamoDB
- `My customer ID is C001. What are my orders?`
- `Tell me about order ORD-1001`
- `Search for backpacks`
- `I want to return order ORD-1001`
- `What is your return policy?` — still works via Knowledge Base

**Great work!** Aria is now connected to real ShopSmart tools through
AgentCore Gateway. You've gone from a knowledge-base-only agent to one that
lists and looks up orders, searches products, and files return requests — all
via tools the agent discovers dynamically over MCP, with no tool definitions
hardcoded in the agent. The order, product, return, and knowledge-base flows
are all working end to end.

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
