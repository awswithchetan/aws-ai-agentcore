# Module 04 — Knowledge Base

**Course link** [Udemy | Build Production-Ready AI Agent on AWS with AgentCore](https://www.udemy.com/course/build-production-ready-ai-agent-on-aws/?referralCode=C3F97ED4D706F1112786)

In Module 03 you deployed Aria on AgentCore Runtime, but it's ShopSmart knowledge
is still hardcoded in the system prompt. In this module you externalize that
knowledge into a managed **Bedrock Knowledge Base**, then rebuild and redeploy
Aria so she retrieves answers from it instead of from inline prompt text.

This is the first time you'll see the production iteration loop the rest of the
course follows: **change the agent → rebuild the image → redeploy a new version
to Runtime.** You deployed v1 in Module 03; here you deploy next version.

Moving knowledge into documents is how production support agents actually work —
content lives in files that non-engineers can update, not in prompts that require
a code change and redeploy.

---

## What You Will Build

```
S3 Bucket (shopsmart-knowledge-base)
└── Documents
    ├── return-policy.md
    ├── shipping-info.md
    ├── payment-methods.md
    ├── store-hours-and-support.md
    └── general-faq.md
        ↓
Bedrock Knowledge Base
└── Vector store (Amazon OpenSearch Serverless)
    └── Aria retrieves relevant chunks at query time
```

Then you rebuild Aria's agent with a `retrieve_from_knowledge_base` tool and
redeploy it to the Runtime you created in previous Module.

---

## Knowledge Base Documents

The documents are already in the repo at `shopsmart-backend/knowledge-base/`. You will upload these to S3 in Step 2.

| File | Content |
|------|---------|
| `return-policy.md` | Return windows, conditions, process, refund timelines |
| `shipping-info.md` | Domestic/international shipping options, tracking, restrictions |
| `payment-methods.md` | Accepted cards, wallets, BNPL, gift cards, security |
| `store-hours-and-support.md` | Support channels, hours, escalation |
| `general-faq.md` | Orders, account, products, pricing, loyalty, privacy |

## Module Architecture
<img width="1152" height="648" alt="image" src="https://github.com/user-attachments/assets/07b375d0-5b7a-423d-bba6-fe22aed9299f" />

---

## Step 1 — Create S3 Bucket

### Via AWS Console

1. Go to **AWS Console → S3 → Create bucket**
2. Configure:
   - **Bucket name**: `shopsmart-knowledge-base-<your-account-id>` *(must be globally unique)*
   - **Region**: `us-east-1`
   - **Block all public access**: enabled (default)
   - All other settings: leave as default
3. Click **Create bucket**

<details>
<summary>Via CLI (Optional)</summary>

```bash
# Replace <your-account-id> with your actual AWS account ID
aws s3 mb s3://shopsmart-knowledge-base-<your-account-id> --region us-east-1
```

</details>

---

## Step 2 — Upload Knowledge Base Documents

### Via AWS Console

1. Open your newly created S3 bucket
2. Click **Upload → Add files**
3. Select all 5 files from `shopsmart-backend/knowledge-base/` in the repo
4. Click **Upload**

<details>
<summary>Via CLI (Optional)</summary>

```bash
# From the repo root
aws s3 cp shopsmart-backend/knowledge-base/ \
  s3://shopsmart-knowledge-base-<your-account-id>/ \
  --recursive

# Verify the upload
aws s3 ls s3://shopsmart-knowledge-base-<your-account-id>/
```

</details>

---

## Step 3 — Create the Knowledge Base

### Via AWS Console

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Build → Built-in Tools → Knowledge Bases**
2. Click **Create knowledge base**
3. Select **Bedrock Managed KB** and click **Next**

   <details>
   <summary>Bedrock Managed KB vs Self-Managed KB</summary>

   - **Bedrock Managed KB** — AWS fully manages the vector store. Simpler, no infrastructure to manage. ✅ Use this for the course.
   - **Self-Managed KB** — You bring your own vector database. More control, more setup.

   </details>

4. **Knowledge base name**: `shopsmart-kb`

5. Expand **Additional configurations**:
   - **Embedding model**: select **Managed embeddings model** (recommended) — AWS manages the embedding model automatically
   - **IAM Permissions**: leave the auto-populated service role name as default — AWS creates the role for you

6. **Data Source** section:
   - **Data source name**: `shopsmart-docs`
   - **Data source type**: Amazon S3
   - **S3 URI**: `s3://shopsmart-knowledge-base-<your-account-id>/`

7. Click **Create knowledge base**

> Creation takes **3–5 minutes**. Wait until status shows **Available** before proceeding.

8. Note down the **Knowledge Base ID** — you will need it in Step 6.

### Verify the Sync

After creation, the Knowledge Base automatically syncs the data source:

1. Open `shopsmart-kb` in the Bedrock console
2. Under **Data sources**, check that `shopsmart-docs` shows sync status as **Available**
3. If the sync failed or you update documents in S3 later, select the data source and click **Sync** to re-trigger

---

## Step 4 — Test the Knowledge Base directly

Before wiring it into Aria, confirm the KB returns good results on its own:

1. In the Knowledge Base detail page, click **Test knowledge base**
2. Try these test queries:
   - `What is the return window for electronics?`
   - `How much does express shipping cost?`
   - `What payment methods are accepted?`
3. You should see relevant document chunks returned with source attribution

---

## Step 5 — Add Knowledge Base Configuration to SSM

Add two parameters so the redeployed agent knows which KB to query. These sit
alongside the `/aria/region` and `/aria/model_id` parameters from Module 03.

| SSM Parameter             | Purpose                             | Value to set              |
|---------------------------|-------------------------------------|---------------------------|
| `/aria/knowledge_base_id` | Bedrock Knowledge Base ID           | your KB ID from Step 3    |
| `/aria/kb_num_results`    | Number of KB chunks retrieved/query | `5`                       |

### Via AWS Console

1. Go to **AWS Console → Systems Manager → Parameter Store → Create parameter**
2. Create each parameter above as a **Standard**, **String** value

<details>
<summary>Via CLI (Optional)</summary>

```bash
export AWS_REGION=us-east-1
export KNOWLEDGE_BASE_ID="<your-kb-id-from-step-3>"

aws ssm put-parameter --name /aria/knowledge_base_id --type String \
  --value "$KNOWLEDGE_BASE_ID" --overwrite --region "$AWS_REGION"

aws ssm put-parameter --name /aria/kb_num_results --type String \
  --value "5" --overwrite --region "$AWS_REGION"
```

</details>

---

## Step 6 — Grant the Execution Role Permission to Query the Knowledge Base

The `AriaAgentExecutionRole` (created in Module 03) can already read SSM. Add
`bedrock:Retrieve` on your KB so the new tool can query it. Without this, the
agent starts but every KB lookup fails with `AccessDeniedException`.

### Via AWS Console

1. Go to **AWS Console → IAM → Roles → `AriaAgentExecutionRole`**
2. Click **Add permissions → Create inline policy**
3. Select the **JSON** tab and paste the policy below
4. Replace `<AWS_REGION>`, `<AWS_ACCOUNT_ID>`, and `<KNOWLEDGE_BASE_ID>`
5. Click **Next**, name it `AriaKnowledgeBaseAccess`, and click **Create policy**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockKnowledgeBaseRetrieve",
      "Effect": "Allow",
      "Action": "bedrock:Retrieve",
      "Resource": "arn:aws:bedrock:<AWS_REGION>:<AWS_ACCOUNT_ID>:knowledge-base/<KNOWLEDGE_BASE_ID>"
    }
  ]
}
```

<details>
<summary>Via CLI (Optional)</summary>

```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export KNOWLEDGE_BASE_ID="<your-kb-id-from-step-3>"

aws iam put-role-policy \
  --role-name AriaAgentExecutionRole \
  --policy-name AriaKnowledgeBaseAccess \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [
      {
        \"Sid\": \"BedrockKnowledgeBaseRetrieve\",
        \"Effect\": \"Allow\",
        \"Action\": \"bedrock:Retrieve\",
        \"Resource\": \"arn:aws:bedrock:${AWS_REGION}:${AWS_ACCOUNT_ID}:knowledge-base/${KNOWLEDGE_BASE_ID}\"
      }
    ]
  }"
```

</details>

<details>
<summary>Why scope it to the KB ARN?</summary>

Granting `bedrock:Retrieve` on the specific Knowledge Base ARN keeps the role
least-privilege instead of allowing broad Bedrock access. If the parameter later
points at a different KB, update the resource ARN accordingly.

</details>

---

## Step 7 — Rebuild the Image and Redeploy (next version)

Rebuild the container with the KB-aware agent and push it to the same ECR repository, then point the Runtime at the new image.

Copy this module code files into the deployment workspace:

```bash
cp modules/module-04-knowledge-base/agent.py aria-agent/agent.py
cp modules/module-04-knowledge-base/config.py aria-agent/config.py
cp modules/module-04-knowledge-base/requirements.txt aria-agent/requirements.txt
cp modules/module-04-knowledge-base/Dockerfile aria-agent/Dockerfile
```

<details>
<summary>What changed from the Module 03 agent</summary>

- **New tool** `retrieve_from_knowledge_base(query)` calls `bedrock-agent-runtime`
  `retrieve` against your KB and returns the matching chunks.
- **`config.py`** now also loads `/aria/knowledge_base_id` and `/aria/kb_num_results`.
- **System prompt** drops the hardcoded FAQ; Aria is told to use the KB tool for
  policy, shipping, and payment questions.
- The simulated order/product tools are unchanged — those become real in Module 05.

</details>

### Build and push the new image

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1
export ECR_REPO=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aria-agent

aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

cd aria-agent
docker build --platform linux/arm64 -t aria-agent .
docker tag aria-agent:latest $ECR_REPO:latest
docker push $ECR_REPO:latest
cd ..
```

Then roll the Runtime onto the new image:

### Via AWS Console

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Runtime**
2. Select `aria` and choose **Update** (or **Edit**)
3. Confirm the **Image URI** is `<your-ecr-repo-uri>:latest` and save
4. Wait until status returns to **Active**

> Runtime reads configuration at cold start, so the updated image picks up the
> new `/aria/knowledge_base_id` parameter automatically.

<details>
<summary>Via CLI (Optional)</summary>

```bash
export RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes \
  --region "$AWS_REGION" \
  --query "agentRuntimes[?agentRuntimeName=='aria'].agentRuntimeId" \
  --output text)

aws bedrock-agentcore control update-agent-runtime \
  --agent-runtime-id "$RUNTIME_ID" \
  --agent-runtime-artifact "{
    \"containerArtifact\": {
      \"containerImage\": { \"uri\": \"$ECR_REPO:latest\" }
    }
  }" \
  --region "$AWS_REGION"
```

</details>

---

## Step 8 — Test the Knowledge-Grounded Agent

Use either the Runtime **Test** tab or the Streamlit UI from Module 03:

- `What is your return policy?`
- `How much does express shipping cost?`
- `What payment methods do you accept?`

Aria should now retrieve answers from the Knowledge Base documents rather than
the (now removed) hardcoded system prompt.

<details>
<summary>Troubleshooting — Aria says the knowledge base is unavailable</summary>

Check the runtime logs:

1. Go to **AWS Console → CloudWatch → Log groups**
2. Open `/aws/bedrock-agentcore/runtimes/<your-runtime-id>-DEFAULT`
3. Choose **Search all log streams** and read from the top

- Startup log shows `knowledge_base_id=<not set>` → the `/aria/knowledge_base_id`
  parameter is missing or the role can't read SSM (recheck Step 7 and the
  Module 03 SSM policy).
- `Knowledge base retrieval failed: ... AccessDeniedException` → missing
  `bedrock:Retrieve` (recheck Step 8).
- `... ResourceNotFoundException` → the parameter points at a KB ID that doesn't
  exist in this region.

Config is read once at cold start — after changing a policy or parameter,
restart the runtime.

</details>

---

## Step 9 — Verify the Answer Really Came from the Knowledge Base

Aria answers policy questions fluently — but how do you *know* the answer came
from the Knowledge Base and not from the model's general knowledge? The
definitive proof is the tool-call log: the Module 04 agent logs every time it
invokes `retrieve_from_knowledge_base`.

After asking a policy question (e.g. `What is your return policy?`), look for
that tool call in the runtime logs.

### Via AWS Console

1. Go to **AWS Console → CloudWatch → Log groups**
2. Open `/aws/bedrock-agentcore/runtimes/<your-runtime-id>-DEFAULT`
3. Choose **Search all log streams** and search for `retrieve_from_knowledge_base`

You should see a line like:

```text
INFO  aria — 🔧 retrieve_from_knowledge_base(query='return policy')
```

If that line appears, the KB tool was invoked — the answer is grounded in your
documents. If it does not appear, Aria answered without the KB.

<details>
<summary>Via CLI (Optional)</summary>

```bash
export AWS_REGION=us-east-1
export RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes \
  --region "$AWS_REGION" \
  --query "agentRuntimes[?agentRuntimeName=='aria'].agentRuntimeId" \
  --output text)

aws logs filter-log-events \
  --region "$AWS_REGION" \
  --log-group-name "/aws/bedrock-agentcore/runtimes/${RUNTIME_ID}-DEFAULT" \
  --filter-pattern "retrieve_from_knowledge_base"
```

</details>

---

<details>
<summary>How the Knowledge Base integrates with Aria</summary>

When a customer asks Aria a policy question:

```
Customer: "Can I return a jacket I bought 3 weeks ago?"
    ↓
Aria calls retrieve_from_knowledge_base("return window jacket")
    → return-policy.md: "Standard items: 30 days from delivery"
    → return-policy.md: "Items must be in original condition with all tags attached"
    ↓
Aria uses the retrieved context to answer precisely
    → "Yes, you're within the 30-day return window. The jacket needs to be
       in original condition with tags attached. Would you like me to
       initiate the return for you?"
```

Aria never makes up policy details — she retrieves them from the official documents.

</details>

---

<details>
<summary>What You Learned</summary>

- How to create an S3 bucket as a document store
- How to create a Bedrock Knowledge Base with a managed vector store
- How to sync documents and test retrieval
- How retrieval-augmented generation (RAG) works in the context of an agent
- How to add a retrieval tool to an existing agent
- The production iteration loop: change the agent, rebuild the image, redeploy a new version
- How to verify an answer is grounded in the KB using the runtime tool-call logs

</details>

---

## Next Step

Aria is grounded in real documents now — but her orders, products, and returns
are still make-believe: hardcoded sample data living inside `agent.py`. She can
only "see" `ORD-1001` and a handful of demo products.

That changes next. In next **Module** you stand up the actual **ShopSmart
backend** — a REST API backed by Lambda and DynamoDB — and wire it to Aria
through **AgentCore Gateway**. The Gateway reads the API's OpenAPI spec and
exposes each operation as a tool the agent discovers automatically. No more
hardcoded tool functions, no fake data: Aria starts querying real orders,
searching the real catalog, and filing real return requests.

This is where Aria stops pretending and starts working.

Proceed to [Module 05 — Gateway](../module-05-gateway/README.md).
