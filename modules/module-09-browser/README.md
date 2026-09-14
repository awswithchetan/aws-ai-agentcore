# Module 09 — Browser: Live Carrier Tracking

In this module you will add **Amazon Bedrock AgentCore Browser** to Aria. Aria
will use a managed Chrome browser session to visit a fictional carrier portal,
submit a tracking number, and read the live-looking tracking result.

This module intentionally does not use a custom domain, Route 53, or a
third-party carrier. CloudFormation creates a private S3 bucket and a
CloudFront distribution with Origin Access Control. The static site assets are
uploaded to S3 after the stack is created.

## What you will build

```text
Customer → Streamlit → Aria Runtime
                         ├── Gateway → ShopSmart API → DynamoDB
                         └── AgentCore Browser → CloudFront → private S3 site
```

By the end, Aria can answer questions such as:

> Where is my package and when will it arrive?

The agent first obtains the order's `trackingNumber` through the existing
Gateway tool, then calls the local `check_carrier_tracking` tool. That tool
opens a managed AgentCore Browser session and extracts the result from the
carrier page.

## What you will learn

- Why Browser is separate from Gateway: Gateway connects APIs; Browser
  interacts with websites.
- How AgentCore Browser provides a managed Chrome session.
- How Playwright connects to that session over Chrome DevTools Protocol.
- How to host a private static website behind CloudFront without a custom
  domain.
- How to configure a Browser-backed local Strands tool in Aria.

## Prerequisites

Complete Modules 05–08 first:

- A deployed Aria Runtime and working Streamlit UI.
- The ShopSmart Gateway can list orders and retrieve an order.
- Seed data includes tracking numbers such as `UPS1234567890`.
- AWS CLI credentials configured in the target Region.
- Permission to create CloudFormation, S3, and CloudFront resources, and to
  use AgentCore Browser.

Set the Region used by the course:

```bash
export AWS_REGION=us-east-1
export ENVIRONMENT=dev
```

The IAM identity deploying the stack and the Aria Runtime execution role need
permission to use AgentCore Browser. Attach the following policy to the
appropriate identity. Replace `${AWS_REGION}` and `${AWS_ACCOUNT_ID}` with the
actual Region and account ID before applying it:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AgentCoreBrowserAccess",
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:CreateBrowser",
        "bedrock-agentcore:ListBrowsers",
        "bedrock-agentcore:GetBrowser",
        "bedrock-agentcore:DeleteBrowser",
        "bedrock-agentcore:StartBrowserSession",
        "bedrock-agentcore:ListBrowserSessions",
        "bedrock-agentcore:GetBrowserSession",
        "bedrock-agentcore:StopBrowserSession",
        "bedrock-agentcore:UpdateBrowserStream",
        "bedrock-agentcore:ConnectBrowserAutomationStream",
        "bedrock-agentcore:ConnectBrowserLiveViewStream"
      ],
      "Resource": "arn:aws:bedrock-agentcore:${AWS_REGION}:${AWS_ACCOUNT_ID}:browser/*"
    }
  ]
}
```

For a least-privilege deployment, the identity creating the Browser resource
needs the create/list/get/delete actions, while the Runtime role only needs the
session and automation-stream actions. The policy above is intentionally
combined so the course setup is straightforward. Confirm that AgentCore
Browser is available in `${AWS_REGION}` before deploying.

## Step 1 — Deploy the simulated carrier website infrastructure

The template creates:

- A private, encrypted S3 bucket with all public-access blocks enabled.
- A CloudFront distribution using the default CloudFront hostname.
- An Origin Access Control (OAC) allowing only that distribution to read the
  bucket.
- Outputs for the bucket name, distribution ID, and HTTPS URL.

Deploy it from the repository root:

```bash
aws cloudformation deploy \
  --template-file modules/module-09-browser/shopsmart-carrier-browser.yaml \
  --stack-name shopsmart-carrier-browser \
  --parameter-overrides Environment="$ENVIRONMENT" \
  --region "$AWS_REGION"
```

Wait for `CREATE_COMPLETE`. This may take 4-5 minutes as CloudFront distribution deployment takes time. After the stack is successfully created, capture the following outputs:

```bash
export CARRIER_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name shopsmart-carrier-browser \
  --query "Stacks[0].Outputs[?OutputKey=='WebsiteBucketName'].OutputValue" \
  --output text --region "$AWS_REGION")

export CARRIER_URL=$(aws cloudformation describe-stacks \
  --stack-name shopsmart-carrier-browser \
  --query "Stacks[0].Outputs[?OutputKey=='CarrierTrackingUrl'].OutputValue" \
  --output text --region "$AWS_REGION")

echo "$CARRIER_BUCKET"
echo "$CARRIER_URL"
```

## Step 2 — Upload the mock carrier site

Upload the three static files. `--delete` removes stale objects in this
course-only bucket; do not use it if the bucket contains unrelated content.

```bash
aws s3 sync modules/module-09-browser/site/ "s3://$CARRIER_BUCKET/" \
  --delete --region "$AWS_REGION" \
  --cache-control "no-cache, max-age=0"
```

CloudFront may still serve an earlier object briefly because of caching. For a
course deployment, wait a minute or create an invalidation:

```bash
DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
  --stack-name shopsmart-carrier-browser \
  --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDistributionId'].OutputValue" \
  --output text --region "$AWS_REGION")

aws cloudfront create-invalidation \
  --distribution-id "$DISTRIBUTION_ID" \
  --paths '/*'
```

Open `$CARRIER_URL` in a browser and try these fictional values:

| Tracking number | Expected status |
|---|---|
| `UPS1234567890` | In transit |
| `FDX9876543210` | Out for delivery |
| `UPS0011223344` | Delivered |

The page is deliberately deterministic. It does not call a real carrier API
and contains no customer data.

## Step 3 — Configure Aria

The Browser tool reads the website URL from the same SSM prefix used by the
rest of Aria. Store the CloudFront URL without a trailing slash.

### Via AWS Console

1. Go to **AWS Console → Systems Manager → Parameter Store → Create parameter**.
2. Configure the parameter:
   - **Name**: `/aria/carrier_tracking_url`
   - **Tier**: `Standard`
   - **Type**: `String`
   - **Value**: the CloudFront URL stored in `$CARRIER_URL` (for example,
     `https://d123example.cloudfront.net`)
3. Choose **Create parameter**.

### Via CLI (Optional)

```bash
aws ssm put-parameter \
  --name /aria/carrier_tracking_url \
  --type String \
  --value "$CARRIER_URL" \
  --overwrite \
  --region "$AWS_REGION"
```

The equivalent environment variable for local development is:

```bash
export CARRIER_TRACKING_URL="$CARRIER_URL"
```

The repository’s `aria-agent/config.py` loads this value as
`cfg.carrier_tracking_url`.

## Step 4 — Add Browser dependencies and tool code

The Browser implementation is already included in this repository. Copy the
Module 09 files into the main `aria-agent/` directory so the Docker build
uses the Browser-enabled agent:

```bash
cp modules/module-09-browser/agent.py aria-agent/agent.py
cp modules/module-09-browser/config.py aria-agent/config.py
cp modules/module-09-browser/Dockerfile aria-agent/Dockerfile
cp modules/module-09-browser/requirements.txt aria-agent/requirements.txt
cp modules/module-09-browser/tools/browser.py aria-agent/tools/browser.py
```

The Browser module files are provided here:

- `agent.py` registers `check_carrier_tracking` alongside the Knowledge Base and
  Gateway tools.
- `config.py` loads `/aria/carrier_tracking_url`.
- `tools/browser.py` starts an AgentCore Browser session, connects Playwright
  over CDP, navigates to the CloudFront page, and extracts the tracking result.
- `requirements.txt` adds `playwright==1.52.0`.
- `Dockerfile` packages the Browser-enabled agent.

Verify the copied files:

```bash
ls aria-agent/tools/browser.py \
   aria-agent/agent.py \
   aria-agent/config.py \
   aria-agent/Dockerfile \
   aria-agent/requirements.txt
```

> The existing `identity/` and `memory/` directories from Modules 06–07 must
> remain in `aria-agent/`; the Dockerfile copies them into the image along with
> the new Browser tool.

> The `aria-agent/` directory is the deployment source. Copy the
> files before building the image; changing the source files afterward does not
> change an image that has already been pushed to ECR.

## Step 5 — Build and deploy the Browser-enabled Runtime

Use the same arm64 container deployment flow introduced in Module 04. If the
ECR repository already exists, reuse it; otherwise create it once:

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1
export ECR_REPO=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aria-agent

aws ecr describe-repositories \
  --repository-names aria-agent \
  --region "$AWS_REGION" >/dev/null 2>&1 || \
aws ecr create-repository \
  --repository-name aria-agent \
  --region "$AWS_REGION"

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin \
    "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# Required when the Docker host is Intel/AMD (x86_64) and the target is arm64.
# Run this once per Docker installation.
docker run --privileged --rm tonistiigi/binfmt --install arm64

cd aria-agent
docker build --platform linux/arm64 -t aria-agent .
docker tag aria-agent:latest "$ECR_REPO:latest"
docker push "$ECR_REPO:latest"
cd ..
```

If Docker is already running on an arm64 host, the emulation command is not
needed. On an Intel/AMD host, the command above must complete successfully
before `docker build` starts.

Update the existing `aria` Runtime. Replace `<YOUR_RUNTIME_ID>` and the role
ARN if your deployment uses different values:

```bash
aws bedrock-agentcore-control update-agent-runtime \
  --agent-runtime-id <YOUR_RUNTIME_ID> \
  --agent-runtime-artifact "{\"containerConfiguration\":{\"containerUri\":\"$ECR_REPO:latest\"}}" \
  --role-arn "arn:aws:iam::$AWS_ACCOUNT_ID:role/AriaAgentExecutionRole" \
  --network-configuration '{"networkMode":"PUBLIC"}' \
  --description "Module 09 — Browser" \
  --region "$AWS_REGION"
```

If you need to find the Runtime ID:

```bash
aws bedrock-agentcore-control list-agent-runtimes \
  --region "$AWS_REGION" \
  --query "agentRuntimes[?agentRuntimeName=='aria'].agentRuntimeId" \
  --output text
```

Wait for the Runtime status to return to **Ready** before testing. The Runtime
execution role must include the AgentCore Browser permissions from the
prerequisites section, and the `/aria/carrier_tracking_url` parameter must be
present before the container starts.

> Do not add the carrier website as a Gateway target. It is not an API tool;
> Browser is the correct AgentCore capability for interacting with it.

## Step 6 — Test the end-to-end flow

Log in to the Streamlit UI and try:

```text
Where is my package?
```

Aria should:

1. Call `list_orders` for the authenticated customer.
2. Select an order with a tracking number.
3. Call `check_carrier_tracking`.
4. Start a managed Browser session.
5. Navigate to the CloudFront carrier page.
6. Return the carrier, status, location, and estimated delivery.

For a direct test of the tool behavior, ask:

```text
What is the latest status of order ORD001?
```

Use an order ID from your seeded data if it differs. The agent should not
invent a tracking status when the order has no tracking number; it should
explain that tracking is unavailable.

## Troubleshooting

| Symptom | Check |
|---|---|
| CloudFront returns `403` | Confirm all site files were uploaded to the output bucket and wait for distribution deployment. |
| Page loads but assets are missing | Confirm the object names are exactly `index.html`, `app.js`, and `styles.css`. |
| Browser is not configured | Check `/aria/carrier_tracking_url` and restart/redeploy Aria so its startup config reloads. |
| Browser session cannot start | Check Region support, Browser IAM actions, and the Runtime role permissions. |
| Tool returns temporary unavailable | Inspect Runtime logs for Browser/Playwright errors and test `$CARRIER_URL` manually. |
| Old tracking result appears | Create a CloudFront invalidation for `/*`. |

## Cleanup

The stack uses `DeletionPolicy: Delete` for the course bucket. Delete the
CloudFormation stack only after removing the uploaded objects:

```bash
aws s3 rm "s3://$CARRIER_BUCKET" --recursive --region "$AWS_REGION"
aws cloudformation delete-stack \
  --stack-name shopsmart-carrier-browser \
  --region "$AWS_REGION"

aws ssm delete-parameter \
  --name /aria/carrier_tracking_url \
  --region "$AWS_REGION"
```

CloudFront distributions can take several minutes to delete. The stack is
independent of the ShopSmart backend stack, so deleting it does not remove
orders, products, or the API.

## What you learned

- AgentCore Browser is a managed browser runtime, not a Gateway API target.
- Playwright can connect to Browser through the CDP automation stream.
- A private S3 origin plus CloudFront OAC provides a simple, reproducible test
  website without a custom domain.
- Browser is useful when the information exists only in a web interface and
  cannot be obtained through a stable API.

## Next step

Proceed to [Module 10 — Cleanup](../module-10-cleanup/README.md) to remove the
course resources when you are finished.
