# Module 09 — Browser: Live Carrier Tracking

In this module you will add **Amazon Bedrock AgentCore Browser** to Aria, giving
her the ability to interact with real websites — not just APIs. Some information
customers ask for doesn't live behind a tidy API; it's only on a web page, such
as a shipping carrier's tracking portal. AgentCore Browser lets Aria drive a
managed Chrome session to reach that information.

Concretely, Aria will visit a fictional carrier portal, submit a tracking
number, and read back the live tracking result — so she can answer "where is my
package?" using the same page a human would check. To keep the module
self-contained, you'll deploy a small simulated carrier site (rather than
scraping a real third-party carrier), then point Aria's browser tool at it.

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

## Step 1 — Deploy the simulated carrier website infrastructure

The template creates:

- A private, encrypted S3 bucket with all public-access blocks enabled.
- A CloudFront distribution using the default CloudFront hostname.
- An Origin Access Control (OAC) allowing only that distribution to read the
  bucket.
- Outputs for the bucket name, distribution ID, and HTTPS URL.

Deploy it from the repository root:

```bash
export AWS_REGION=us-east-1

aws cloudformation deploy \
  --template-file modules/module-09-browser/shopsmart-carrier-browser.yaml \
  --stack-name shopsmart-carrier-browser \
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

Aria loads all of its configuration from the `/aria/` SSM parameter prefix
(model ID, knowledge base ID, gateway endpoint, memory ID, and so on). Add the
carrier website URL as one more parameter under that prefix. Store the
CloudFront URL without a trailing slash.

### Via AWS Console

1. Go to **AWS Console → Systems Manager → Parameter Store → Create parameter**.
2. Configure the parameter:
   - **Name**: `/aria/carrier_tracking_url`
   - **Tier**: `Standard`
   - **Type**: `String`
   - **Value**: the CloudFront URL stored in `$CARRIER_URL` (for example,
     `https://d123example.cloudfront.net`)
3. Choose **Create parameter**.

<details>
<summary>Via CLI</summary>

```bash
aws ssm put-parameter \
  --name /aria/carrier_tracking_url \
  --type String \
  --value "$CARRIER_URL" \
  --overwrite \
  --region "$AWS_REGION"
```

</details>

## Step 4 — Grant AgentCore Browser permissions

Grant the Aria Runtime execution role permission to use AgentCore Browser. Do
this first — the container needs these permissions to start Browser sessions at
runtime.

### Via AWS Console

1. Go to **IAM → Roles → AriaAgentExecutionRole**
2. Click **Add permissions → Create inline policy**
3. Switch to the **JSON** editor and paste (replace `<ACCOUNT_ID>` with your
   account ID and `us-east-1` with your Region if different):

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
      "Resource": "arn:aws:bedrock-agentcore:us-east-1:<ACCOUNT_ID>:browser/*"
    }
  ]
}
```

4. Name the policy `AriaBrowserAccess` and click **Create policy**

<details>
<summary>Via CLI</summary>

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1

aws iam put-role-policy \
  --role-name AriaAgentExecutionRole \
  --policy-name AriaBrowserAccess \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Sid\": \"AgentCoreBrowserAccess\",
      \"Effect\": \"Allow\",
      \"Action\": [
        \"bedrock-agentcore:CreateBrowser\",
        \"bedrock-agentcore:ListBrowsers\",
        \"bedrock-agentcore:GetBrowser\",
        \"bedrock-agentcore:DeleteBrowser\",
        \"bedrock-agentcore:StartBrowserSession\",
        \"bedrock-agentcore:ListBrowserSessions\",
        \"bedrock-agentcore:GetBrowserSession\",
        \"bedrock-agentcore:StopBrowserSession\",
        \"bedrock-agentcore:UpdateBrowserStream\",
        \"bedrock-agentcore:ConnectBrowserAutomationStream\",
        \"bedrock-agentcore:ConnectBrowserLiveViewStream\"
      ],
      \"Resource\": \"arn:aws:bedrock-agentcore:${AWS_REGION}:${AWS_ACCOUNT_ID}:browser/*\"
    }]
  }"
```

</details>

> Confirm AgentCore Browser is available in your Region. The action set is
> intentionally broad so the same policy works whether the role creates the
> Browser resource or only starts sessions against it.

## Step 5 — Add Browser dependencies and tool code

Unlike Gateway tools — which the agent discovers automatically over MCP — the
Browser capability is driven by code you write and package into the agent.
AgentCore Browser provides a managed Chrome session, but *how* Aria uses it
(which URL to open, which page elements to read) lives in a local Strands tool.
There's nothing to auto-discover, so you add the tool to the agent and redeploy.

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

## Step 6 — Build and deploy the Browser-enabled Runtime

Rebuild and push the image, then update the `aria` Runtime:

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1
export ECR_REPO=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aria-agent

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin \
    "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

cd aria-agent
docker build --platform linux/arm64 -t aria-agent .
docker tag aria-agent:latest "$ECR_REPO:latest"
docker push "$ECR_REPO:latest"
cd ..
```

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
execution role must include the AgentCore Browser permissions from Step 4, and
the `/aria/carrier_tracking_url` parameter must be present before the container
starts.

## Step 7 — Test the end-to-end flow

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

<details>
<summary>Troubleshooting</summary>

| Symptom | Check |
|---|---|
| CloudFront returns `403` | Confirm all site files were uploaded to the output bucket and wait for distribution deployment. |
| Page loads but assets are missing | Confirm the object names are exactly `index.html`, `app.js`, and `styles.css`. |
| Browser is not configured | Check `/aria/carrier_tracking_url` and restart/redeploy Aria so its startup config reloads. |
| Browser session cannot start | Check Region support, Browser IAM actions, and the Runtime role permissions. |
| Tool returns temporary unavailable | Inspect Runtime logs for Browser/Playwright errors and test `$CARRIER_URL` manually. |
| Old tracking result appears | Create a CloudFront invalidation for `/*`. |

</details>

<details>
<summary>What You Learned</summary>

- AgentCore Browser is a managed browser runtime, not a Gateway API target.
- Playwright can connect to Browser through the CDP automation stream.
- A private S3 origin plus CloudFront OAC provides a simple, reproducible test
  website without a custom domain.
- Browser is useful when the information exists only in a web interface and
  cannot be obtained through a stable API.

</details>

---

## Congratulations!

You've successfully completed all the modules in this course. Here's what you built:

**Aria** — ShopSmart's AI customer support agent with:

- **Runtime** — Amazon Bedrock AgentCore Runtime that orchestrates the agent's capabilities
- **Gateway** — Real-time integration with ShopSmart's backend APIs (orders, products, returns)
- **Knowledge Base** — ShopSmart FAQ with custom grounding data
- **Memory** — Stateful conversations that remember customers across sessions
- **Identity** — Customer authentication via Amazon Cognito with JWT handling
- **Policy** — Guardrails powered by Amazon Cedar for governance and access control
- **Browser** — Ability to scrape live carrier tracking pages using Playwright

You deployed Aria end-to-end on AWS, learning how to connect real tools, manage state, authenticate users, enforce policies, and interact with web pages — all using Amazon Bedrock AgentCore capabilities.

## Next step

Proceed to [Module 10 — Cleanup](../module-10-cleanup/README.md)
