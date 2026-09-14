# Module 04 — Runtime

In this module you will build the **real Aria** — a production-grade AI customer support agent written in Python using Strands Agents, deployed on AgentCore Runtime, and connected to the Knowledge Base created in Module 03.

This is the agent that evolves through the rest of the course. Every subsequent module adds a new capability to this same agent.

---

## What You Will Build

```
aria-agent/
├── agent.py          # Aria agent code (Strands + BedrockAgentCoreApp)
├── config.py         # Runtime and Knowledge Base configuration
├── requirements.txt  # Module 04 Python dependencies
├── Dockerfile        # Container image (recommended — framework-agnostic)
└── .dockerignore     # Keeps the build context clean
```

<details>
<summary>How This Differs from Module 02</summary>

| | Module 02 — Harness | Module 04 — Runtime |
|---|---|---|
| Agent loop | Managed by AgentCore | You write it in Python |
| FAQ knowledge | Hardcoded in system prompt | Retrieved from Knowledge Base |
| Framework | Black box | Strands Agents |
| Deployment | Console config only | Python code + zip deploy |
| Production ready | No | Yes |

Two deployment options are covered: **Docker (recommended)** and zip.
Docker is preferred because it works identically regardless of which agent
framework you use — swap `requirements.txt` and `agent.py` for LangChain,
CrewAI, or any other framework without touching the deployment pipeline.

</details>

---

## Step 1 — Prepare the Module 04 Agent Snapshot

The repository keeps `aria-agent/` as the active deployment directory. Because it is a generated workspace that accumulates capability directories from later modules, first copy the complete Module 04 snapshot into `aria-agent/`. This ensures the image contains only the Runtime and Knowledge Base capabilities introduced here.

Run from the repository root:

```bash
cp modules/module-04-runtime/agent.py aria-agent/agent.py
cp modules/module-04-runtime/config.py aria-agent/config.py
cp modules/module-04-runtime/requirements.txt aria-agent/requirements.txt
cp modules/module-04-runtime/Dockerfile aria-agent/Dockerfile
```

Review the copied files in `aria-agent/` before deploying:

- [`agent.py`](agent.py) — Aria agent code
- [`config.py`](config.py) — Runtime and Knowledge Base configuration
- [`requirements.txt`](requirements.txt) — Module 04 dependencies
- [`Dockerfile`](Dockerfile) — Module 04 container definition

---

## Step 1b — Add ECR Permissions to the Execution Role

### Via AWS Console

1. Go to **AWS Console → IAM → Roles → `AriaAgentExecutionRole`**
2. Click **Add permissions → Attach policies**
3. Search for `AmazonEC2ContainerRegistryReadOnly`
4. Select it and click **Add permissions**

### Via CLI (Optional)

```bash
aws iam attach-role-policy \
  --role-name AriaAgentExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly
```

<details>
<summary>Why this permission is needed</summary>

`AmazonEC2ContainerRegistryReadOnly` grants exactly three permissions:
`ecr:GetAuthorizationToken`, `ecr:BatchGetImage`, and `ecr:GetDownloadUrlForLayer`.
These are the minimum required for AgentCore to pull a container image — nothing more.

The `AriaAgentExecutionRole` from Module 02 didn't need ECR permissions because
the Harness had no container to pull. Now that we deploy a container image, this
is required.

</details>

---

## Step 2 — Add Configuration to SSM Parameter Store

Aria loads all dynamic configuration from SSM Parameter Store at container startup.
This separates configuration from code — you can change the model or Knowledge Base
ID without rebuilding or redeploying the container.

Parameters are stored under the `/aria/` prefix:

| SSM Parameter             | Purpose                             | Value to set                     |
|---------------------------|-------------------------------------|----------------------------------|
| `/aria/region`            | AWS region                          | e.g. `us-east-1`                 |
| `/aria/model_id`          | Bedrock model to use                | `us.anthropic.claude-sonnet-4-6` |
| `/aria/knowledge_base_id` | Bedrock Knowledge Base ID           | your KB ID from Module 03        |
| `/aria/kb_num_results`    | Number of KB chunks retrieved/query | `5`                              |

### Via AWS Console

1. Go to **AWS Console → Systems Manager → Parameter Store → Create parameter**
2. For each row in the table above:
   - **Name**: the full path (e.g. `/aria/model_id`)
   - **Tier**: Standard
   - **Type**: String
   - **Value**: as shown in the table
3. Click **Create parameter** and repeat for all four

### Via CLI (Optional)

```bash
export KNOWLEDGE_BASE_ID="<your-kb-id-from-module-03>"
export AWS_REGION=us-east-1

bash aria-agent/scripts/put_ssm_params.sh
```

<details>
<summary>Why SSM instead of environment variables?</summary>

- Model upgrades and KB replacements are configuration changes, not code changes
- Changing an env var requires a container redeploy; changing an SSM parameter does not
- SSM gives you an audit trail (who changed what, when) out of the box
- SSM SecureString can be used for sensitive values without Secrets Manager overhead

To update a parameter later (e.g. model upgrade):
1. Go to Parameter Store, find `/aria/model_id`
2. Click **Edit**, update the value, save
3. Restart the AgentCore Runtime — config is read once at cold start

No code change. No image rebuild. No redeployment.

</details>

<details>
<summary>Local development (no SSM required)</summary>

Set `SSM_ENABLED=false` to skip SSM entirely and use env vars instead:

```bash
export SSM_ENABLED=false
export KNOWLEDGE_BASE_ID=kb-XXXXXXXXXX
export AWS_REGION=us-east-1
# MODEL_ID and KB_NUM_RESULTS have built-in defaults
```

</details>

---

## Step 3 — Deploy to AgentCore Runtime

### Option A — Docker (Recommended)

#### 3a. Create an ECR repository

```bash
aws ecr create-repository \
  --repository-name aria-agent \
  --region us-east-1
```

Note the `repositoryUri` from the output.

#### 3b. Build and push the image

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1
export ECR_REPO=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aria-agent

# Authenticate Docker to ECR
aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build and push
cp modules/module-04-runtime/agent.py aria-agent/agent.py
cp modules/module-04-runtime/config.py aria-agent/config.py
cp modules/module-04-runtime/requirements.txt aria-agent/requirements.txt
cp modules/module-04-runtime/Dockerfile aria-agent/Dockerfile
cd aria-agent
docker build --platform linux/arm64 -t aria-agent .
docker tag aria-agent:latest $ECR_REPO:latest
docker push $ECR_REPO:latest
cd ..
```

<details>
<summary>Note on linux/arm64</summary>

AgentCore Runtime microVM only supports arm64. If your machine is amd64 (Intel/AMD),
install QEMU once to enable cross-platform builds:

```bash
docker run --privileged --rm tonistiigi/binfmt --install arm64
```

</details>

#### 3c. Create the Runtime via AWS Console

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Runtime → Create agent runtime**
2. Configure:
   - **Agent runtime name**: `aria`
   - **Description**: ShopSmart AI customer support agent
   - **Deployment method**: Container image
   - **Image URI**: `<your-ecr-repo-uri>:latest`
3. **Environment variables**: add `AWS_REGION` only (e.g. `us-east-1`)
4. **Execution role**: select `AriaAgentExecutionRole`
5. Click **Create agent runtime**
6. Wait until status shows **Active**
7. Note down the **Agent Runtime ARN**

#### 3c. Create the Runtime via CLI (Optional)

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
  --execution-role-arn "arn:aws:iam::<YOUR_ACCOUNT_ID>:role/AriaAgentExecutionRole" \
  --region us-east-1
```

---

### Option B — Zip (Simpler, no Docker required)

#### Via AWS Console

1. Run the Module 04 snapshot copy commands from Step 1 so `aria-agent/` contains the Module 04 files.
2. Go to **AWS Console → Amazon Bedrock → AgentCore → Runtime → Create agent runtime**
3. Configure:
   - **Agent runtime name**: `aria`
   - **Deployment method**: Code (zip file)
   - **Runtime**: Python 3.11
   - **Entrypoint file**: `agent.py`
4. Zip the `aria-agent/` folder contents and upload
5. **Execution role**: select `AriaAgentExecutionRole`
6. Click **Create agent runtime**
7. Wait until status shows **Active**
8. Note down the **Agent Runtime ARN**

#### Via CLI (Optional)

Before creating the zip, run the Module 04 snapshot copy commands from Step 1 so `aria-agent/` contains the Module 04 files.

```bash
cd aria-agent
zip -r ../aria-agent.zip agent.py config.py requirements.txt
cd ..

aws bedrock-agentcore control create-agent-runtime \
  --agent-runtime-name "aria" \
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
  --execution-role-arn "arn:aws:iam::<YOUR_ACCOUNT_ID>:role/AriaAgentExecutionRole" \
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

```bash
cp modules/module-04-runtime/app.py streamlit-ui/app.py

export ARIA_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:<YOUR_ACCOUNT_ID>:runtime/aria-XXXXXXXX"
export AWS_REGION="us-east-1"
streamlit run streamlit-ui/app.py
```

---

<details>
<summary>What You Learned</summary>

- How AgentCore Runtime works — isolated execution environment for your agent code
- How to structure a Strands agent with `BedrockAgentCoreApp`
- How the `@app.entrypoint` decorator wires your function into the Runtime
- How to use SSM Parameter Store to externalize configuration from code
- Why separating config from code matters for production rollouts
- How to package an agent as a Docker image and push it to ECR
- Why Docker is the framework-agnostic choice for production deployments
- How to connect the Knowledge Base as a retrieval tool

</details>

---

## Next Step

Proceed to [Module 05 — Gateway](../module-05-gateway/README.md) where you will connect Aria to real backend tools — Lambda functions for order lookup, product search, and return requests.
