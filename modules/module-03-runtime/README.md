# Module 03 — Runtime

In Module 02 you built Aria as a self-contained Strands agent and ran her in your
terminal. In this module you deploy that **same agent** onto Amazon Bedrock
AgentCore Runtime — managed, scalable, observable hosting — with the smallest
possible change to the code.

The point of this module is to learn Runtime *in isolation*. Aria's tools are
still simulated and her FAQ knowledge is still inline in the system prompt; we
change nothing about her behavior. The only meaningful difference from Module 02
is the entrypoint: a local CLI loop becomes a `BedrockAgentCoreApp` entrypoint
that Runtime calls on every request.

Once she's deployed, you'll test her two ways — the built-in Runtime **Test**
console, then the ShopSmart Streamlit chat UI.

This is the agent that evolves through the rest of the course. Every subsequent
module rebuilds and redeploys this same agent with one new capability — starting
with a real Knowledge Base in Module 04.

---

## What You Will Build

```
aria-agent/
├── agent.py          # The Module 02 agent + a BedrockAgentCoreApp entrypoint
├── config.py         # Loads model + region from SSM (no KB yet)
├── requirements.txt  # Strands + the AgentCore Runtime SDK
├── Dockerfile        # Container image (recommended — framework-agnostic)
└── .dockerignore     # Keeps the build context clean
```

<details>
<summary>How this differs from Module 02</summary>

| | Module 02 — Local agent | Module 03 — Runtime |
|---|---|---|
| Where it runs | Your laptop | AgentCore Runtime (managed cloud) |
| Entry point | CLI chat loop | `BedrockAgentCoreApp` entrypoint |
| Config | Env vars in your shell | SSM Parameter Store |
| Scaling & sessions | None | Managed by Runtime |
| Tools | Simulated (hardcoded data) | **Still simulated** — unchanged |
| FAQ knowledge | Inline in system prompt | **Still inline** — unchanged |

Everything about Aria's *behavior* is identical to Module 02. We're only
changing how she is hosted and invoked. The simulated pieces become real in
later modules (Knowledge Base in 04, real tools via Gateway in 05, and so on).

Two deployment options are covered: **Docker (recommended)** and zip.
Docker is preferred because it works identically regardless of which agent
framework you use — swap `requirements.txt` and `agent.py` for LangChain,
CrewAI, or any other framework without touching the deployment pipeline.

</details>

---

## Step 1 — Copy the Module 03 Agent Files into the Deployment Workspace

The repository keeps `aria-agent/` as the active deployment directory. It is a
generated workspace that accumulates capability files from later modules, so
first copy the complete Module 03 snapshot into it.

Run from the repository root:

```bash
cp modules/module-03-runtime/agent.py aria-agent/agent.py
cp modules/module-03-runtime/config.py aria-agent/config.py
cp modules/module-03-runtime/requirements.txt aria-agent/requirements.txt
cp modules/module-03-runtime/Dockerfile aria-agent/Dockerfile
```

Review the copied files in `aria-agent/` before deploying:

- [`agent.py`](agent.py) — the Module 02 agent with a `BedrockAgentCoreApp` entrypoint
- [`config.py`](config.py) — loads model + region from SSM
- [`requirements.txt`](requirements.txt) — Module 03 dependencies
- [`Dockerfile`](Dockerfile) — Module 03 container definition

> Open `agent.py` and compare it to your Module 02 file. The tools, data, and
> system prompt are identical — the new parts are the `app = BedrockAgentCoreApp()`
> line and the `@app.entrypoint` function near the bottom.

---

## Step 2 — Externalize Configuration to SSM Parameter Store

This is where we begin *productionalizing* the Module 02 agent. In Module 02 the
model ID lived in the code (an `ARIA_MODEL_ID` env var with a default). For a
deployed service, values that change over time — the model, the region, and
later the Knowledge Base ID — belong in configuration, not baked into the
container image. We externalize them into **SSM Parameter Store** so you can
change them without rebuilding or redeploying.

Aria reads these parameters once at container startup (see `config.py`).
Parameters live under the `/aria/` prefix:

| SSM Parameter    | Purpose              | Value to set                     |
|------------------|----------------------|----------------------------------|
| `/aria/region`   | AWS region           | e.g. `us-east-1`                 |
| `/aria/model_id` | Bedrock model to use | `us.anthropic.claude-sonnet-4-6` |

### Via AWS Console

1. Go to **AWS Console → Systems Manager → Parameter Store → Create parameter**
2. For each row in the table above:
   - **Name**: the full path (e.g. `/aria/model_id`)
   - **Tier**: Standard
   - **Type**: String
   - **Value**: as shown in the table
3. Click **Create parameter** and repeat for both

<details>
<summary>Via CLI (Optional)</summary>

```bash
export AWS_REGION=us-east-1

aws ssm put-parameter --name /aria/region --type String \
  --value "$AWS_REGION" --overwrite --region "$AWS_REGION"

aws ssm put-parameter --name /aria/model_id --type String \
  --value "us.anthropic.claude-sonnet-4-6" --overwrite --region "$AWS_REGION"
```

</details>

<details>
<summary>How to retrieve or validate the model ID</summary>

The default model ID is `us.anthropic.claude-sonnet-4-6` — a cross-region
inference profile (note the `us.` prefix). To use a different model, or confirm
the ID is valid in your region, list the available Claude inference profiles:

```bash
aws bedrock list-inference-profiles \
  --region us-east-1 \
  --query "inferenceProfileSummaries[?contains(inferenceProfileId, 'claude')].inferenceProfileId" \
  --output table
```

</details>

<details>
<summary>Why SSM instead of environment variables?</summary>

- Model upgrades are configuration changes, not code changes.
- Changing an env var requires a container redeploy; changing an SSM parameter does not.
- SSM gives you an audit trail (who changed what, when) out of the box.

To update a parameter later: edit it in Parameter Store, then restart the
Runtime — config is read once at cold start. No code change, no image rebuild.

</details>

<details>
<summary>Local development (no SSM required)</summary>

Set `SSM_ENABLED=false` to skip SSM entirely and use env vars instead:

```bash
export SSM_ENABLED=false
export AWS_REGION=us-east-1
# MODEL_ID has a built-in default
```

</details>

---

## Step 3 — Create the ECR Repository

AgentCore Runtime pulls Aria's container image from Amazon Elastic Container
Registry (ECR). Create the repository now — before the execution role — so that
when we grant the role permission to pull images, the repository it pulls from
already exists.

### Via AWS Console

1. Go to **AWS Console → Amazon ECR → Repositories → Create repository**
2. **Visibility settings**: Private
3. **Repository name**: `aria-agent`
4. Leave the other settings at their defaults
5. Click **Create**
6. Note the repository **URI** (e.g. `<account>.dkr.ecr.us-east-1.amazonaws.com/aria-agent`)

<details>
<summary>Via CLI (Optional)</summary>

```bash
aws ecr create-repository \
  --repository-name aria-agent \
  --region us-east-1
```

Note the `repositoryUri` from the output.

</details>

---

## Step 4 — Create the Agent Execution IAM Role

AgentCore Runtime needs an IAM role to invoke Bedrock models, pull the container
image from ECR, read configuration from SSM, and write logs. Create it once here
— every later module reuses this same role, adding permissions as new
capabilities are introduced.

### Via AWS Console

1. Go to **AWS Console → IAM → Roles → Create role**
2. **Trusted entity type**: AWS service
3. **Use case**: scroll down and select **Amazon Bedrock AgentCore** — this automatically configures the correct trust policy
4. Click **Next**
5. Attach these managed policies:
   - `AmazonBedrockFullAccess` — invoke Bedrock models
   - `BedrockAgentCoreFullAccess` — Runtime operations
   - `CloudWatchLogsFullAccess` — write logs
   - `AmazonEC2ContainerRegistryReadOnly` — pull the image from the ECR repo you just created
6. Click **Next**
7. **Role name**: `AriaAgentExecutionRole`
8. Click **Create role**
9. Open the new role and choose **Add permissions → Create inline policy** to add
   SSM read access for the `/aria/` parameters from Step 2:
   - Select the **JSON** tab and paste the policy below
   - Replace `<AWS_REGION>` and `<AWS_ACCOUNT_ID>`
   - Click **Next**, name it `AriaRuntimeConfigAccess`, and click **Create policy**
10. Note down the **Role ARN**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SSMReadAriaConfig",
      "Effect": "Allow",
      "Action": [
        "ssm:GetParametersByPath",
        "ssm:GetParameters",
        "ssm:GetParameter"
      ],
      "Resource": [
        "arn:aws:ssm:<AWS_REGION>:<AWS_ACCOUNT_ID>:parameter/aria",
        "arn:aws:ssm:<AWS_REGION>:<AWS_ACCOUNT_ID>:parameter/aria/*"
      ]
    }
  ]
}
```

<details>
<summary>Via CLI (Optional)</summary>

```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create trust policy
cat > trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Service": "bedrock-agentcore.amazonaws.com" },
    "Action": "sts:AssumeRole"
  }]
}
EOF

# Create the role
aws iam create-role \
  --role-name AriaAgentExecutionRole \
  --assume-role-policy-document file://trust-policy.json

# Attach the managed policies
for POLICY in \
  arn:aws:iam::aws:policy/AmazonBedrockFullAccess \
  arn:aws:iam::aws:policy/BedrockAgentCoreFullAccess \
  arn:aws:iam::aws:policy/CloudWatchLogsFullAccess \
  arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly; do
  aws iam attach-role-policy --role-name AriaAgentExecutionRole --policy-arn "$POLICY"
done

# Add the SSM read inline policy
aws iam put-role-policy \
  --role-name AriaAgentExecutionRole \
  --policy-name AriaRuntimeConfigAccess \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [
      {
        \"Sid\": \"SSMReadAriaConfig\",
        \"Effect\": \"Allow\",
        \"Action\": [
          \"ssm:GetParametersByPath\",
          \"ssm:GetParameters\",
          \"ssm:GetParameter\"
        ],
        \"Resource\": [
          \"arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/aria\",
          \"arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/aria/*\"
        ]
      }
    ]
  }"

# Get the Role ARN
aws iam get-role --role-name AriaAgentExecutionRole --query "Role.Arn" --output text

# Clean up
rm trust-policy.json
```

</details>

<details>
<summary>Why these permissions</summary>

- **`AmazonEC2ContainerRegistryReadOnly`** grants `ecr:GetAuthorizationToken`,
  `ecr:BatchGetImage`, and `ecr:GetDownloadUrlForLayer` — the minimum needed for
  AgentCore to pull the container image. (It applies account-wide; in real
  production you might scope image pulls to the specific repository.)
- **SSM read** (`GetParametersByPath` / `GetParameters` / `GetParameter`) lets the
  agent load its configuration at startup. Module 03 only calls
  `GetParametersByPath`, but the other two are included so later modules that fetch
  individual parameters work without a policy change. Two resource ARNs are
  required: `parameter/aria` matches the path itself, and `parameter/aria/*`
  matches the individual parameters under it.

Module 02 ran Aria locally and needed no role at all. Module 04 later extends this
same role with `bedrock:Retrieve` when the Knowledge Base is introduced.

</details>

---

## Step 5 — Build, Push, and Deploy to AgentCore Runtime

This course uses **Docker** as the deployment method throughout. A Zip-based
alternative is included in the collapsible section at the end of this step.

#### 5a. Build and push the image

You created the `aria-agent` ECR repository in Step 3. Now build the image and
push it there:

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1
export ECR_REPO=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aria-agent

# Authenticate Docker to ECR
aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build and push (aria-agent/ was populated in Step 1)
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

#### 5b. Create the Runtime via AWS Console

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Runtime → Create agent runtime**
2. Configure:
   - **Agent runtime name**: `aria`
   - **Compute**: leave the default **MicroVM**
   - **Additional details** (expand): set **Description** to `ShopSmart AI customer support agent`
   - **Agent source**: choose **ECR Container** (not S3 source)
   - **Image URI**: `<your-ecr-repo-uri>:latest`
   - **Permissions**: select **Use another role** and choose `AriaAgentExecutionRole`
   - **Environment variables** (under **Advanced configurations**): add `AWS_REGION` (e.g. `us-east-1`)
3. Click **Create agent runtime**
4. Wait until status shows **Active**
5. Note down the **Agent Runtime ARN**

<details>
<summary>5c. Create the Runtime via CLI (Optional)</summary>

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

</details>

<details>
<summary>Alternative — Deploy with Zip (no Docker required)</summary>

The rest of this course assumes a Docker-based deployment. Use this Zip option
only if you cannot use Docker; some later modules may reference container-specific
steps you'll need to adapt.

#### Via AWS Console

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Runtime → Create agent runtime**
2. Configure:
   - **Agent runtime name**: `aria`
   - **Deployment method**: Code (zip file)
   - **Runtime**: Python 3.11
   - **Entrypoint file**: `agent.py`
3. Zip the `aria-agent/` folder contents and upload
4. **Execution role**: select `AriaAgentExecutionRole`
5. Click **Create agent runtime**
6. Wait until status shows **Active**
7. Note down the **Agent Runtime ARN**

#### Via CLI (Optional)

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

</details>

---

## Step 6 — Test with the Runtime console

The quickest way to confirm the deployment works is the built-in Test tab:

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Runtime**
2. Select `aria` and click the **Test** tab
3. Try these prompts:
   - `What is your return policy?`
   - `What's the status of order ORD-1002?`
   - `Where is my package for order ORD-1001?`

Aria answers exactly as she did locally in Module 02 — the FAQ comes from her
system prompt, and the order/tracking answers come from the simulated tools.

> The tools are still simulated, so Aria only "knows" the sample orders
> (`ORD-1001`, `ORD-1002`) and products baked into `agent.py`. We connect real
> data through Gateway in Module 05.

<details>
<summary>Troubleshooting — check CloudWatch logs</summary>

If the Test tab returns an error:

1. Go to **AWS Console → CloudWatch → Log groups**
2. Open `/aws/bedrock-agentcore/runtimes/<your-runtime-id>-DEFAULT`
3. Choose **Search all log streams** and read from the top

On startup Aria logs its resolved config, e.g.
`Starting Aria with config: AgentConfig(region='us-east-1', model_id='us.anthropic.claude-sonnet-4-6')`.
Configuration is read once at container cold start; after changing an IAM policy
or SSM parameter, restart the runtime so the new values take effect.

</details>

---

## Step 7 — Test with the Streamlit chat UI

Now interact with the deployed agent through the ShopSmart chat UI — the same
interface a customer would use.

```bash
cp modules/module-03-runtime/app.py streamlit-ui/app.py

export ARIA_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:<YOUR_ACCOUNT_ID>:runtime/aria-XXXXXXXX"
export AWS_REGION="us-east-1"
streamlit run streamlit-ui/app.py
```

Open your browser at `http://localhost:8501` and chat with Aria. The UI invokes
your Runtime endpoint via `invoke_agent_runtime` — the agent is now genuinely
running in the cloud, not on your laptop.

---

<details>
<summary>What You Learned</summary>

- How AgentCore Runtime works — managed, isolated hosting for your agent code
- How the same local agent becomes a deployable one by adding a `BedrockAgentCoreApp` entrypoint
- How the `@app.entrypoint` decorator wires your function into the Runtime
- How to use SSM Parameter Store to externalize configuration from code
- How to package an agent as a Docker image and push it to ECR
- Why Docker is the framework-agnostic choice for production deployments
- Two ways to test a deployed agent: the Runtime console and a Streamlit UI

</details>

---

## Next Step

Aria is deployed, but her knowledge is still hardcoded in the system prompt.
Next you'll move that knowledge into a real, searchable **Knowledge Base**, then
rebuild and redeploy Aria to retrieve from it.

Proceed to [Module 04 — Knowledge Base](../module-04-knowledge-base/README.md).
