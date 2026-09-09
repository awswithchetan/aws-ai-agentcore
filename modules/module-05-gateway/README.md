# Module 05 — Gateway: Connecting Real Tools

In this module you will connect Aria to the ShopSmart backend — real Lambda
functions backed by DynamoDB. Aria moves from answering only FAQ questions to
looking up actual orders, searching the product catalog, and submitting support
requests on behalf of customers.

---

## What You Will Build

```
shopsmart-backend/
├── cloudformation/
│   └── shopsmart-backend.yaml   # DynamoDB + Lambda + API Gateway
├── lambdas/
│   ├── list_orders.py
│   ├── get_order.py
│   ├── get_product.py
│   ├── search_products.py
│   └── submit_request.py
└── seed_data.py                 # Populate tables with sample data

modules/module-05-gateway/
└── agent.py                     # Aria with order and product tools
```

---

## How This Differs from Module 04

| | Module 04 — Runtime | Module 05 — Gateway |
|---|---|---|
| Knowledge source | Knowledge Base only | Knowledge Base + Live backend |
| Order lookup | Not possible | Real DynamoDB orders |
| Product search | Not possible | Real DynamoDB products |
| Return requests | Not possible | Submitted via API |
| Customer identity | N/A | Customer provides their ID |

---

## Step 1 — Deploy the ShopSmart Backend

### 1a. Create an S3 bucket for Lambda deployment packages

You need an S3 bucket to upload the Lambda zip files before CloudFormation can
deploy them. Create it once — it will be reused for all future deployments.

```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export BUCKET=shopsmart-lambda-$AWS_ACCOUNT_ID

aws s3 mb s3://$BUCKET --region $AWS_REGION
```

> The bucket name includes your account ID to make it globally unique.
> S3 bucket names must be unique across all AWS accounts worldwide.

### 1b. Package and upload Lambda code to S3

> The environment variables from step 1a (`AWS_REGION`, `AWS_ACCOUNT_ID`, `BUCKET`) must still be set in the same terminal session.

```bash
# Package and upload Lambda functions
cd shopsmart-backend/lambdas
for f in list_orders get_order get_product search_products submit_request; do
  zip ${f}.zip ${f}.py
  aws s3 cp ${f}.zip s3://$BUCKET/lambdas/${f}.zip
done
cd ../..
```

### 1c. Deploy the stack

```bash
aws cloudformation deploy \
  --template-file shopsmart-backend/cloudformation/shopsmart-backend.yaml \
  --stack-name shopsmart-backend \
  --parameter-overrides \
      Environment=dev \
      LambdaCodeBucket=$BUCKET \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

Wait for the stack to reach `CREATE_COMPLETE`. Note the API URL from the outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name shopsmart-backend \
  --query "Stacks[0].Outputs" \
  --output table \
  --region us-east-1
```

Note down the `ApiBaseUrl` value — you will need it in Step 4.

---

## Step 2 — Seed the Database

Run the seed script to populate DynamoDB with sample orders and products:

```bash
export AWS_REGION=us-east-1
export ENVIRONMENT=dev
python shopsmart-backend/seed_data.py
```

You should see:
```
✅ All done! Tables are ready for use.

Test customers:
  C001 — Alice Johnson (2 orders: delivered, shipped)
  C002 — Bob Smith     (1 order: processing)
  C003 — Carol White   (1 order: delivered, with return request)
```

### Verify via AWS Console

Go to **DynamoDB → Tables → shopsmart-orders-dev → Explore items** and confirm
you can see the seeded orders.

---

## Step 3 — Test the API directly

Before connecting Aria, verify the API works on its own:

```bash
export API_URL=$(aws cloudformation describe-stacks \
  --stack-name shopsmart-backend \
  --query "Stacks[0].Outputs[?OutputKey=='ApiBaseUrl'].OutputValue" \
  --output text --region us-east-1)

# List orders for customer C001
curl "$API_URL/orders?customerId=C001"

# Get a specific order
curl "$API_URL/orders/ORD-1001"

# Search products
curl "$API_URL/products?q=backpack"

# Get a specific product
curl "$API_URL/products/P001"
```

---

## Step 4 — Add api_base_url to SSM

Add the API URL to SSM so the agent can load it at startup:

### Via AWS Console

1. Go to **AWS Console → Systems Manager → Parameter Store → Create parameter**
2. **Name**: `/aria/api_base_url`
3. **Type**: String
4. **Value**: the `ApiBaseUrl` from Step 1c

### Via CLI (Optional)

```bash
export API_BASE_URL="https://<api-id>.execute-api.us-east-1.amazonaws.com/dev"

API_BASE_URL=$API_BASE_URL \
KNOWLEDGE_BASE_ID=<your-kb-id> \
bash aria-agent/scripts/put_ssm_params.sh
```

---

## Step 5 — Update the Agent

Copy the Module 05 agent to `aria-agent/`:

```bash
cp modules/module-05-gateway/agent.py aria-agent/agent.py
```

Review the new tools in `agent.py` — notice how each tool calls the ShopSmart
API through a simple `requests` call. In a later module these calls will go
through AgentCore Gateway which adds authentication and access controls.

---

## Step 6 — Rebuild and Deploy

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

aws bedrock-agentcore control update-agent-runtime \
  --agent-runtime-id <YOUR_RUNTIME_ID> \
  --agent-runtime-artifact "{\"containerConfiguration\":{\"containerUri\":\"$ECR_REPO:latest\"}}" \
  --role-arn "arn:aws:iam::$AWS_ACCOUNT_ID:role/AriaHarnessExecutionRole" \
  --network-configuration '{"networkMode":"PUBLIC"}' \
  --description "Module 05 — Gateway tools" \
  --region us-east-1
```

---

## Step 7 — Add API Gateway permissions to the execution role

The agent container needs to call the ShopSmart API Gateway. Since the API is
public in this module, no additional permissions are needed — `requests` makes
a plain HTTPS call. This changes in Module 07 when we add authentication.

---

## Step 8 — Test

Try these prompts in the console Test tab or Streamlit UI:

- `What are my orders?` — Aria asks for your customer ID
- `My customer ID is C001. What are my orders?`
- `Tell me about order ORD-1001`
- `Search for backpacks`
- `I want to return order ORD-1001`
- `What is your return policy?` — still works via Knowledge Base

---

## What You Learned

- How to deploy a serverless backend with CloudFormation
- How to seed DynamoDB with realistic test data
- How to add HTTP-based tools to a Strands agent
- How Aria can combine Knowledge Base retrieval and live API calls
- Why externalizing the API URL to SSM matters (no redeploy to change environments)

---

## Next Step

Proceed to [Module 06 — Memory](../module-06-memory/README.md) where you will
add persistent memory to Aria so she remembers customers across sessions.
