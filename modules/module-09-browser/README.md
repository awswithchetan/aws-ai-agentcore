# Module 09 — Browser: Live Carrier Tracking

**Course link** [Udemy | Build Production-Ready AI Agent on AWS with AgentCore](https://www.udemy.com/course/build-production-ready-ai-agent-on-aws/?referralCode=C3F97ED4D706F1112786)

In this module you will add **Amazon Bedrock AgentCore Browser** to Aria, giving
it the ability to interact with real websites — not just APIs. Some information
customers ask for doesn't live behind a tidy API; it's only on a web page, such
as a shipping carrier's tracking portal. AgentCore Browser lets Aria drive a
managed Chrome session to reach that information.

Concretely, Aria will visit a fictional carrier portal, submit a tracking
number, and read back the live tracking result — so it can answer "where is my
package?" using the same page a human would check. To keep the module
self-contained, you'll deploy a small simulated carrier site (rather than
scraping a real third-party carrier), then point Aria's browser tool at it.

It will also **capture a screenshot** of the carrier page during the lookup and
upload it to a private S3 bucket, so the customer can see the exact page Aria
read.

## What you will build

```text
Customer → Streamlit → Aria Runtime
                         ├── Gateway → ShopSmart API → DynamoDB
                         └── AgentCore Browser → CloudFront → private S3 site
                                   └── screenshot → private S3 bucket → presigned link
                     → Load screenshot image in the chat
```

By the end, Aria can answer questions such as:

> Where is my package and when will it arrive?

The agent first obtains the order's `trackingNumber` through the existing
Gateway tool, then calls the local `check_carrier_tracking` tool. That tool
opens a managed AgentCore Browser session, extracts the result from the
carrier page, and captures a screenshot of that page which it uploads to a
private S3 bucket. It returns the tracking details plus a presigned link to
the screenshot, which the Streamlit chat renders inline as an image.

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


## Step 3 — Create a bucket for Browser screenshots

Create a separate, private bucket where Aria stores the screenshots it captures
during a tracking lookup — kept distinct from the carrier site bucket.

### Via AWS Console

1. Go to **AWS Console → S3 → Create bucket**
2. Configure:
   - **Bucket name**: `shopsmart-browser-screenshots-<your-account-id>` *(must be globally unique)*
   - **Region**: `us-east-1`
   - **Block all public access**: enabled (default)
   - All other settings: leave as default
3. Click **Create bucket**

<details>
<summary>Via CLI (Optional)</summary>

```bash
export SCREENSHOT_BUCKET="shopsmart-browser-screenshots-$AWS_ACCOUNT_ID"

aws s3 mb "s3://$SCREENSHOT_BUCKET" --region "$AWS_REGION"
```

</details>

> The agent never makes this bucket public. It uploads each screenshot as a
> private object and returns a short-lived presigned URL so only the current
> customer can open that one screenshot.


## Step 4 — Add parameters in SSM Parameter Store

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
4. Create a second parameter for the screenshot bucket:
   - **Name**: `/aria/screenshot_bucket`
   - **Tier**: `Standard`
   - **Type**: `String`
   - **Value**: the bucket name stored in `$SCREENSHOT_BUCKET` (for example,
     `shopsmart-browser-screenshots-123456789012`)
5. Choose **Create parameter**.

<details>
<summary>Via CLI</summary>

```bash
aws ssm put-parameter \
  --name /aria/carrier_tracking_url \
  --type String \
  --value "$CARRIER_URL" \
  --overwrite \
  --region "$AWS_REGION"

aws ssm put-parameter \
  --name /aria/screenshot_bucket \
  --type String \
  --value "$SCREENSHOT_BUCKET" \
  --overwrite \
  --region "$AWS_REGION"
```

</details>

## Step 5 — Grant AgentCore Browser permissions

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
    },
    {
      "Sid": "BrowserScreenshotBucketAccess",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::shopsmart-browser-screenshots-<ACCOUNT_ID>/*"
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
    }, {
      \"Sid\": \"BrowserScreenshotBucketAccess\",
      \"Effect\": \"Allow\",
      \"Action\": [
        \"s3:PutObject\",
        \"s3:GetObject\"
      ],
      \"Resource\": \"arn:aws:s3:::${SCREENSHOT_BUCKET}/*\"
    }]
  }"
```

</details>

## Step 6 — Update agent code to use Browser tool

Unlike Gateway tools — which the agent discovers automatically over MCP — the
Browser capability is code you write and package into the agent. The managed
Chrome session is provided by AgentCore, but *how* Aria uses it lives in a local
Strands tool, so you add it to the agent and redeploy.

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

## Step 7 — Build and deploy the Browser-enabled Runtime

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

Now update the existing `aria` Runtime so it pulls the image you just pushed.
Because the image tag is unchanged (`:latest`), the simplest way to force the
Runtime to reload it is to update the Runtime and change its description — the
console re-pulls the current tag on update.

### Via AWS Console

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Runtime → aria**
2. Click **Update runtime**
3. Leave the container image URI as-is — it still points at
   `aria-agent:latest`, which is the image you just pushed.
4. Change the **Description** to `Module 09 — Browser` (any change here forces
   the Runtime to re-pull the `:latest` image).
5. Leave all other settings — protocol, inbound auth (JWT), network — unchanged.
6. Click **Update runtime**

<details>
<summary>Via CLI (Optional)</summary>

`update-agent-runtime` is a full PUT operation — any field you omit is reset,
not preserved. So the CLI path must re-supply the artifact, role, network, and
(because Module 07 configured it) the JWT authorizer and request-header
allowlist. This is why the console update is simpler for a repeat deploy.

```bash
RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes \
  --region "$AWS_REGION" \
  --query "agentRuntimes[?agentRuntimeName=='aria'].agentRuntimeId" \
  --output text)

# Pre-flight check: confirm every variable the update command needs is set.
for VAR in AWS_REGION AWS_ACCOUNT_ID ECR_REPO RUNTIME_ID USER_POOL_ID CLIENT_ID; do
  echo "$VAR = ${!VAR:-<MISSING>}"
done
# If any value shows <MISSING> (or still contains a <placeholder>), fix it
# before running the update below.

aws bedrock-agentcore-control update-agent-runtime \
  --agent-runtime-id "$RUNTIME_ID" \
  --agent-runtime-artifact "{\"containerConfiguration\":{\"containerUri\":\"$ECR_REPO:latest\"}}" \
  --role-arn "arn:aws:iam::$AWS_ACCOUNT_ID:role/AriaAgentExecutionRole" \
  --network-configuration '{"networkMode":"PUBLIC"}' \
  --authorizer-configuration "{
    \"customJWTAuthorizer\": {
      \"discoveryUrl\": \"https://cognito-idp.${AWS_REGION}.amazonaws.com/${USER_POOL_ID}/.well-known/openid-configuration\",
      \"allowedClients\": [\"${CLIENT_ID}\"]
    }
  }" \
  --request-header-configuration '{"requestHeaderAllowlist": ["Authorization", "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Id-Token"]}' \
  --description "Module 09 — Browser (updated via CLI)" \
  --region "$AWS_REGION"
```

</details>

Wait for the Runtime status to return to **Ready** before testing. The Runtime
execution role must include the AgentCore Browser permissions from Step 4, and
the `/aria/carrier_tracking_url` and `/aria/screenshot_bucket` parameters must
be present before the container starts.

## Step 8 — Test the end-to-end flow

> **No Streamlit changes are needed for this module.** All the new behavior
> lives in the agent (the Browser tool and system prompt) running in the Runtime
> container you just redeployed. Keep using the existing Streamlit app.

Start the UI:

```bash
export AWS_REGION=us-east-1
streamlit run streamlit-ui/app.py
```

Open `http://localhost:8501`, log in, and try:

```text
Where is my order ORD-1002?
```

Aria should:

1. Call `list_orders` for the authenticated customer.
2. Select an order with a tracking number.
3. Call `check_carrier_tracking`.
4. Start a managed Browser session.
5. Navigate to the CloudFront carrier page.
6. Capture a screenshot and upload it to the screenshot bucket.
7. Return the carrier, status, location, estimated delivery, and a link to the
   screenshot.

The screenshot appears **inline in the chat** — an image of the exact carrier
page Aria read, right below the tracking details.

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
| Tracking works but no screenshot link | Confirm `/aria/screenshot_bucket` is set and the `AriaBrowserAccess` policy includes `s3:PutObject`/`s3:GetObject` on that bucket. |
| Screenshot link returns `AccessDenied` | The presigned URL has expired — ask Aria again to regenerate it, or confirm the role has `s3:GetObject` on the screenshot bucket. |

</details>

<details>
<summary>What You Learned</summary>

- AgentCore Browser is a managed browser runtime, not a Gateway API target.
- Playwright can connect to Browser through the CDP automation stream.
- A private S3 origin plus CloudFront OAC provides a simple, reproducible test
  website without a custom domain.
- Browser is useful when the information exists only in a web interface and
  cannot be obtained through a stable API.
- A Playwright `page.screenshot()` plus a private S3 bucket and a presigned URL
  lets the agent share proof of what it saw without exposing the bucket.

</details>

## Other Browser capabilities (for reference)

This module uses two Browser features: **page automation** and **screenshots**.
Two more are worth knowing about, though we don't use them here:

- **Live view** — Stream a browser session in real time and optionally take over
  control, via `client.generate_live_view_url(...)` and
  `client.take_control()` / `client.release_control()`. The
  `ConnectBrowserLiveViewStream` action in Step 4 already permits it. Best as a
  debugging or demo tool rather than a customer-facing response.

- **Session recording and replay** — Record a session (DOM changes, clicks,
  console logs, network calls) to S3 for later replay in the AWS Console. This
  needs a **custom browser** created with
  `create_browser(..., recording={"enabled": True, "s3Location": {...}})` plus
  extra S3 and CloudWatch Logs permissions. A strong fit for auditing and
  compliance.

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
- **Browser** — Ability to scrape live carrier tracking pages using Playwright, and capture a screenshot of the page to a private S3 bucket shared via a presigned link

You deployed Aria end-to-end on AWS, learning how to connect real tools, manage state, authenticate users, enforce policies, and interact with web pages — all using Amazon Bedrock AgentCore capabilities.

## Next step

Proceed to [Module 10 — Cleanup](../module-10-cleanup/README.md)
