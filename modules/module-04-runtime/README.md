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

## Step 2 — Set the Knowledge Base ID

Before deploying, set the Knowledge Base ID from Module 03 as an environment variable. The agent reads this at runtime:

```bash
export KNOWLEDGE_BASE_ID="<your-kb-id-from-module-03>"
```

Or add it to a `.env` file in `aria-agent/`:

```
KNOWLEDGE_BASE_ID=kb-XXXXXXXXXX
AWS_REGION=us-east-1
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
cd aria-agent
docker build -t aria-agent .
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
3. **Environment variables**: add `KNOWLEDGE_BASE_ID` and `AWS_REGION`
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
  --environment-variables "KNOWLEDGE_BASE_ID=$KNOWLEDGE_BASE_ID,AWS_REGION=$AWS_REGION" \
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
- How to package an agent as a Docker image and push it to ECR
- Why Docker is the framework-agnostic choice for production deployments
- How to connect the Knowledge Base as a retrieval tool

---

## Next Step

Proceed to [Module 05 — Gateway](../module-05-gateway/README.md) where you will connect Aria to real backend tools — Lambda functions for order lookup, product search, and return requests.
