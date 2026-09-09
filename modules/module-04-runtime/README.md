# Module 04 — Runtime

In this module you will build the **real Aria** — a production-grade AI customer support agent written in Python using Strands Agents, deployed on AgentCore Runtime, and connected to the Knowledge Base created in Module 03.

This is the agent that evolves through the rest of the course. Every subsequent module adds a new capability to this same agent.

---

## What You Will Build

```
aria-agent/
├── agent.py          # Aria agent code (Strands + BedrockAgentCoreApp)
├── requirements.txt  # Python dependencies
├── Dockerfile        # Container image (recommended — framework-agnostic)
└── .dockerignore     # Keeps the build context clean
```

Two deployment options are covered: **Docker (recommended)** and zip.
Docker is preferred because it works identically regardless of which agent
framework you use — swap `requirements.txt` and `agent.py` for LangChain,
CrewAI, or any other framework without touching the deployment pipeline.

---

## How This Differs from Module 02

| | Module 02 — Harness | Module 04 — Runtime |
|---|---|---|
| Agent loop | Managed by AgentCore | You write it in Python |
| FAQ knowledge | Hardcoded in system prompt | Retrieved from Knowledge Base |
| Framework | Black box | Strands Agents |
| Deployment | Console config only | Python code + zip deploy |
| Production ready | No | Yes |

---

## Step 1 — Create the Agent Code

The agent code lives in the `aria-agent/` folder at the root of the repo:

- [`aria-agent/agent.py`](../../aria-agent/agent.py) — Aria agent code
- [`aria-agent/requirements.txt`](../../aria-agent/requirements.txt) — Python dependencies

Open `aria-agent/agent.py` in VS Code and review the structure before deploying.

---

## Step 1b — Add ECR Permissions to the Execution Role

The `AriaHarnessExecutionRole` created in Module 02 does not have ECR permissions — it didn't need them for the Harness. Now that we are deploying a container image, AgentCore Runtime needs to pull the image from ECR. Add the permission before deploying.

### Via AWS Console

1. Go to **AWS Console → IAM → Roles → `AriaHarnessExecutionRole`**
2. Click **Add permissions → Attach policies**
3. Search for `AmazonEC2ContainerRegistryReadOnly`
4. Select it and click **Add permissions**

### Via CLI (Optional)

```bash
aws iam attach-role-policy \
  --role-name AriaHarnessExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly
```

> `AmazonEC2ContainerRegistryReadOnly` grants exactly three permissions:
> `ecr:GetAuthorizationToken`, `ecr:BatchGetImage`, and `ecr:GetDownloadUrlForLayer`.
> These are the minimum required for AgentCore to pull a container image — nothing more.

---

## Step 2 — Externalize Configuration to SSM Parameter Store

Aria loads all dynamic configuration from AWS Systems Manager (SSM) Parameter
Store at container startup. This separates **configuration** from **code** —
you can change the model, Knowledge Base ID, or retrieval tuning without
rebuilding or redeploying the container.

This is a standard production practice. Take a few minutes to explore the
SSM console before creating the parameters — it's worth understanding what
you're working with.

> **What is SSM Parameter Store?**
> A managed key-value store for configuration data. Parameters are versioned,
> audited (who changed what, when), and can be encrypted (SecureString).
> Free tier covers standard parameters — all four below qualify.
> Console: **AWS Console → Systems Manager → Parameter Store**

Parameters are stored under the `/aria/` prefix:

| SSM Parameter             | Purpose                             | Value to set                     |
|---------------------------|-------------------------------------|----------------------------------|
| `/aria/region`            | AWS region                          | e.g. `us-east-1`                 |
| `/aria/model_id`          | Bedrock model to use                | `us.anthropic.claude-sonnet-4-6` |
| `/aria/knowledge_base_id` | Bedrock Knowledge Base ID           | your KB ID from Module 03        |
| `/aria/kb_num_results`    | Number of KB chunks retrieved/query | `5`                              |

### Create parameters via AWS Console

1. Go to **AWS Console → Systems Manager → Parameter Store → Create parameter**
2. For each row in the table above:
   - **Name**: the full path (e.g. `/aria/model_id`)
   - **Tier**: Standard
   - **Type**: String
   - **Value**: as shown in the table
3. Click **Create parameter** and repeat for all four

Spend a moment exploring the parameter detail page — notice the **History**
tab that tracks every change with a timestamp. This is the audit trail you
get for free.

### Update a parameter later (e.g. model upgrade)

1. Go to **Parameter Store**, find `/aria/model_id`
2. Click **Edit**, update the value, save
3. Restart the AgentCore Runtime — config is read once at cold start

No code change. No image rebuild. No redeployment.

### Automate it (optional)

A script is provided if you want to create or update all parameters at once:

```bash
export KNOWLEDGE_BASE_ID="<your-kb-id-from-module-03>"
export AWS_REGION=us-east-1

bash aria-agent/scripts/put_ssm_params.sh
```

See [`aria-agent/scripts/put_ssm_params.sh`](../../aria-agent/scripts/put_ssm_params.sh)
for the full script.

### Local development (no SSM required)

Set `SSM_ENABLED=false` to skip SSM entirely and use env vars instead:

```bash
export SSM_ENABLED=false
export KNOWLEDGE_BASE_ID=kb-XXXXXXXXXX
export AWS_REGION=us-east-1
# MODEL_ID and KB_NUM_RESULTS have built-in defaults
```

---

## Step 3 — Deploy to AgentCore Runtime

### Option A — Docker (Recommended)

Docker is the recommended approach. It is framework-agnostic — you can swap
the agent framework at any point without changing the deployment pipeline.

#### 3a. Create an ECR repository

```bash
aws ecr create-repository \
  --repository-name aria-agent \
  --region us-east-1
```

Note the `repositoryUri` from the output — you will use it in the next step.

#### 3b. Build and push the image

```bash
# Set your values
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1
export ECR_REPO=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aria-agent

# Authenticate Docker to ECR
aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build and push
# AgentCore Runtime microVM only supports arm64. If your machine is amd64
# (Intel/AMD), install QEMU once to enable cross-platform builds:
#   docker run --privileged --rm tonistiigi/binfmt --install arm64
cd aria-agent
docker build --platform linux/arm64 -t aria-agent .
docker tag aria-agent:latest $ECR_REPO:latest
docker push $ECR_REPO:latest
cd ..
```

#### 3c. Deploy via AWS Console

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Runtime → Create agent runtime**
2. Configure:
   - **Agent runtime name**: `aria`
   - **Description**: ShopSmart AI customer support agent
   - **Deployment method**: Container image
   - **Image URI**: `<your-ecr-repo-uri>:latest`
3. **Environment variables**: add `AWS_REGION` only (e.g. `us-east-1`). All other config is loaded from SSM at startup.
4. **Execution role**: select `AriaHarnessExecutionRole` (created in Module 02)
5. Click **Create agent runtime**
6. Wait until status shows **Active**
7. Note down the **Agent Runtime ARN** and **Endpoint URL**

#### 3c. Deploy via CLI (Optional)

```bash
aws bedrock-agentcore control create-agent-runtime \
  --agent-runtime-name "aria" \
  --description "ShopSmart AI customer support agent" \
  --agent-runtime-artifact "{
    \"containerArtifact\": {
      \"containerImage\": {
        \"uri\": \"$ECR_REPO:latest\"
      }
    }
  }" \
  --environment-variables "AWS_REGION=$AWS_REGION" \
  --network-configuration '{"networkMode": "PUBLIC"}' \
  --execution-role-arn "arn:aws:iam::<YOUR_ACCOUNT_ID>:role/AriaHarnessExecutionRole" \
  --region us-east-1
```

---

### Option B — Zip (Simpler, no Docker required)

Use this if you want to get started quickly without a Docker setup.

#### Via AWS Console

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Runtime → Create agent runtime**
2. Configure:
   - **Agent runtime name**: `aria`
   - **Description**: ShopSmart AI customer support agent
   - **Deployment method**: Code (zip file)
   - **Runtime**: Python 3.11
   - **Entrypoint file**: `agent.py`
3. **Upload code**:
   - Zip the `aria-agent/` folder contents
   - Upload the zip file
4. **Execution role**: select `AriaHarnessExecutionRole` (created in Module 02)
5. Click **Create agent runtime**
6. Wait until status shows **Active**
7. Note down the **Agent Runtime ARN** and **Endpoint URL**

#### Via CLI (Optional)

```bash
# From repo root
cd aria-agent
zip -r ../aria-agent.zip .
cd ..

# Upload and deploy
aws bedrock-agentcore control create-agent-runtime \
  --agent-runtime-name "aria" \
  --description "ShopSmart AI customer support agent" \
  --agent-runtime-artifact '{
    "codeArtifact": {
      "runtimeArtifact": {
        "s3Location": {
          "uri": "s3://<YOUR_BUCKET>/aria-agent.zip"
        }
      }
    }
  }' \
  --network-configuration '{"networkMode": "PUBLIC"}' \
  --execution-role-arn "arn:aws:iam::<YOUR_ACCOUNT_ID>:role/AriaHarnessExecutionRole" \
  --region us-east-1
```

---

## Step 4 — Test via AWS Console

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Runtime**
2. Select `aria` and click the **Test** tab
3. Try these prompts:
   - `What is your return policy?`
   - `How much does express shipping cost?`
   - `What payment methods do you accept?`

Aria should now retrieve answers from the Knowledge Base documents rather than a hardcoded system prompt.

---

## Step 5 — Update Streamlit UI

Update the Streamlit app to invoke the Runtime agent instead of the Harness.

```bash
export ARIA_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:<YOUR_ACCOUNT_ID>:runtime/aria-XXXXXXXX"
export AWS_REGION="us-east-1"
streamlit run streamlit-ui/app.py
```

---

## What You Learned

- How AgentCore Runtime works — isolated execution environment for your agent code
- How to structure a Strands agent with `BedrockAgentCoreApp`
- How the `@app.entrypoint` decorator wires your function into the Runtime
- How to use SSM Parameter Store to externalize configuration from code
- Why separating config from code matters for production rollouts
- How to package an agent as a Docker image and push it to ECR
- Why Docker is the framework-agnostic choice for production deployments
- How to connect the Knowledge Base as a retrieval tool

---

## Next Step

Proceed to [Module 05 — Gateway](../module-05-gateway/README.md) where you will connect Aria to real backend tools — Lambda functions for order lookup, product search, and return requests.
