# Module 00 — Prerequisites & Setup

This module covers everything you need to install and configure before building Aria. Follow the steps for your operating system.

---

## What You Will Set Up

- Python 3.11+
- AWS CLI v2
- Docker Desktop
- AgentCore CLI
- VS Code
- AWS account and IAM permissions
- Verify everything works

---

## 1. Python 3.11+

### macOS

```bash
# Check if Python is already installed
python3 --version

# Install via Homebrew (recommended)
# First install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python
brew install python@3.11

# Verify
python3 --version
```

### Ubuntu (Linux)

```bash
# Check if Python is already installed
python3 --version

# Update package list
sudo apt update

# Install Python 3.11
sudo apt install -y python3.11 python3.11-venv python3.11-pip

# Set python3.11 as default (optional)
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Verify
python3 --version
```

---

## 2. AWS CLI v2

### macOS

```bash
# Download and install
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /

# Verify
aws --version

# Clean up
rm AWSCLIV2.pkg
```

### Ubuntu (Linux)

```bash
# Download and install
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Verify
aws --version

# Clean up
rm -rf awscliv2.zip aws/
```

---

## 3. Configure AWS Credentials

You need an AWS account with appropriate permissions. If you don't have one, create a free account at [aws.amazon.com](https://aws.amazon.com).

### Using an Existing AWS Admin User (Recommended for Most Learners)

If you already have an AWS account with an admin user configured, you can skip IAM user creation entirely. Just verify your credentials are active:

```bash
aws sts get-caller-identity
```

If this returns your account details, you're good to go — proceed to **Configure AWS CLI** below.

---

<details>
<summary>Create a Dedicated IAM User (Optional — Best Practice)</summary>

If you want a dedicated user with scoped permissions for this course rather than using your admin account:

1. Go to **AWS Console → IAM → Users → Create User**
2. Username: `agentcore-dev`
3. Attach policies:
   - `AmazonBedrockFullAccess`
   - `AmazonDynamoDBFullAccess`
   - `AWSLambda_FullAccess`
   - `AmazonAPIGatewayAdministrator`
   - `AmazonCognitoPowerUser`
   - `AmazonS3FullAccess`
   - `CloudWatchFullAccess`
   - `AmazonEC2ContainerRegistryFullAccess`
   - `IAMFullAccess` *(needed for CloudFormation to create roles)*
4. Create access key → **Application running outside AWS**
5. Note down **Access Key ID** and **Secret Access Key**

> **Note**: For a production environment you would use more granular permissions. For this course, these policies keep setup simple.

</details>

### Configure AWS CLI

```bash
aws configure
```

You will be prompted for:
```
AWS Access Key ID:     <your-access-key-id>
AWS Secret Access Key: <your-secret-access-key>
Default region name:   us-east-1
Default output format: json
```

### Verify AWS CLI is Working

```bash
aws sts get-caller-identity
```

Expected output:
```json
{
    "UserId": "AIDA...",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/agentcore-dev"
}
```

---

## 4. Amazon Bedrock Model Access

Access to Amazon Bedrock foundation models is **enabled by default** — no manual toggle needed. However, for **Anthropic models (Claude)**, AWS requires a one-time use case form the first time you use them in your account.

### Complete the Anthropic First Time Use (FTU) Form

1. Go to **AWS Console → Amazon Bedrock → Model catalog** (ensure region is `us-east-1`)
2. Search for **Claude 3.5 Sonnet** and open it
3. If prompted, fill in the use case form:
   - **Intended use**: "Learning and building AI agents with Amazon Bedrock AgentCore"
   - **Website**: Your GitHub profile, LinkedIn, or personal website URL
4. Submit — access is granted immediately

> This is a one-time step per AWS account. If your account has used Claude before, you can skip this entirely.

<details>
<summary>IAM permissions required for model access</summary>

Your IAM user must have AWS Marketplace permissions for automatic model access to work. These are included if you attached `AmazonBedrockFullAccess` in the previous step. Verify with:

```bash
aws bedrock list-foundation-models \
  --region us-east-1 \
  --query "modelSummaries[?contains(modelId,'claude-3-5-sonnet')].[modelId]" \
  --output table
```

If this command returns results without error, you're good to go.

</details>

---

## 5. Docker Desktop

AgentCore Runtime supports two deployment methods — **Code Zip** (no Docker needed) and **Container Image** (requires Docker). This course primarily uses Code Zip deployment which is simpler and requires no Docker knowledge.

Install Docker if you want to explore container-based deployment in the advanced modules, or skip this step for now.

First, check if Docker is already installed:

```bash
docker --version
docker ps
```

If both commands return without error, Docker is already installed — skip to Step 6.

### macOS

1. Download Docker Desktop from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)
2. Open the `.dmg` file and drag Docker to Applications
3. Launch Docker Desktop and wait for it to start (whale icon in menu bar)

```bash
# Verify
docker --version
docker ps
```

### Ubuntu (Linux / WSL)

```bash
# Install Docker Engine
sudo apt update
sudo apt install -y ca-certificates curl gnupg

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin

# Add your user to docker group (so you don't need sudo)
sudo usermod -aG docker $USER
newgrp docker

# Start Docker service
sudo systemctl enable docker
sudo systemctl start docker

# Verify
docker --version
docker ps
```

<details>
<summary>WSL note</summary>

If `sudo systemctl start docker` fails in WSL, use this instead:
```bash
sudo service docker start
```

</details>

---

## 6. VS Code

### macOS

```bash
# Install via Homebrew
brew install --cask visual-studio-code

# Or download from https://code.visualstudio.com
```

### Ubuntu (Linux)

```bash
# Install via snap
sudo snap install --classic code

# Or via apt
wget -qO- https://packages.microsoft.com/keys/microsoft.asc | \
  gpg --dearmor > packages.microsoft.gpg
sudo install -D -o root -g root -m 644 packages.microsoft.gpg \
  /etc/apt/keyrings/packages.microsoft.gpg
echo "deb [arch=amd64,arm64,armhf signed-by=/etc/apt/keyrings/packages.microsoft.gpg] \
  https://packages.microsoft.com/repos/code stable main" | \
  sudo tee /etc/apt/sources.list.d/vscode.list > /dev/null
sudo apt update
sudo apt install -y code
```

### Recommended VS Code Extensions

Install these from the Extensions panel (`Ctrl+Shift+X` / `Cmd+Shift+X`):

- **Python** (Microsoft)
- **AWS Toolkit** (Amazon Web Services)
- **YAML** (Red Hat)
- **Docker** (Microsoft)

---

## 7. Python Virtual Environment & Dependencies

A virtual environment keeps this project's Python packages isolated from the rest of your system. Create it once and activate it every time you work on the project.

```bash
# Navigate to the repo root
cd /home/chetan/aws-ai-agentcore   # adjust path if different

# Create the virtual environment
python3 -m venv .venv

# Activate it — you'll see (.venv) appear in your terminal prompt
source .venv/bin/activate          # macOS / Linux / WSL

# Install all course dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

> **Every time you open a new terminal**, activate the environment before running any Python commands:
> ```bash
> source .venv/bin/activate
> ```
> You'll know it's active when you see `(.venv)` at the start of your terminal prompt.

---

## 8. Verify AgentCore CLI

```bash
agentcore --version
```

If this returns a version number, the CLI is installed and working. You will create your first harness in Module 02.

---

## 9. Verification Checklist

Run through this checklist before moving to Module 02:

```bash
# Python
python3 --version          # Should be 3.11+

# AWS CLI
aws --version              # Should be 2.x
aws sts get-caller-identity  # Should return your account details

# Docker
docker --version           # Should be 24+
docker ps                  # Should return empty list (not an error)

# Streamlit
streamlit --version        # Should return version number

# Bedrock model access (should return without error)
aws bedrock list-foundation-models \
  --region us-east-1 \
  --query "modelSummaries[?contains(modelId,'claude')].[modelId]" \
  --output table
# Should return Claude model IDs
```

---

## Summary

| Tool | Purpose | Verified |
|------|---------|---------|
| Python 3.11+ | Agent code, Lambda, Streamlit UI | ☐ |
| AWS CLI v2 | Deploy and manage AWS resources | ☐ |
| AWS credentials | Authenticate with AWS | ☐ |
| Bedrock model access | Anthropic FTU form (one-time, first-time accounts only) | ☐ |
| Docker | Required only if deploying agents as container images (advanced modules) | ☐ |
| VS Code | IDE | ☐ |
| Python venv + deps | Isolated Python environment | ☐ |

---

## Next Step

Proceed to [Module 02 — Your First Agent with Harness](../module-02-harness/README.md)
