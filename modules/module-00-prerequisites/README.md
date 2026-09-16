# Module 00 — Prerequisites

## Overview

This module prepares your local workstation and AWS account before you build
Aria, ShopSmart’s customer-support agent. It follows a simple setup flow:

1. Prepare a Linux, macOS, or Ubuntu (Windows/WSL2) workstation.
2. Install the local tools with the supplied script.
3. Configure and verify AWS CLI access.
4. Confirm Bedrock model access and Python dependencies.

The installer in this directory installs local software only. It does **not**
create AWS resources, IAM users, AgentCore resources, or course infrastructure.

## Prerequisites

### 1. AWS account

You need an AWS account with permission to use Amazon Bedrock AgentCore and to create the course resources. The course creates CloudFormation stacks, Lambda
functions, DynamoDB tables, API Gateway resources, Cognito resources, S3 buckets, ECR resources, IAM roles, AgentCore resources, and CloudWatch logs.

For learning purposes, an administrator identity is the simplest option. For a shared or production account, use a dedicated identity with least-privilege
permissions instead. Never commit access keys or place them in the repository.

### 2. Local workstation

Supported setup options:

- Linux: Ubuntu/Debian or Amazon Linux/RHEL-like distributions.
- macOS: Intel or Apple Silicon.
- Windows: WSL2 with Ubuntu is recommended. Run the commands from the WSL2
  terminal, not from Windows PowerShell.

Windows users can install WSL2 from an elevated PowerShell prompt:

```powershell
wsl --install -d Ubuntu --name "<name-of-your-vm>"
```

To connect to your VM (anytime later):

```bash
wsl -d <name-of-your-vm>
```

### 3. Required tools

The installer checks or installs:

- Git
- Python 3.11 or newer and `venv`
- AWS CLI v2
- Docker Engine or Docker Desktop
- `curl`, `zip`, `unzip`, and `jq`
- Course Python dependencies, including Boto3, Streamlit, and AgentCore SDKs

## Step 1 — Clone the repository

Clone the repository and enter its root directory:

```bash
git clone https://github.com/awswithchetan/aws-ai-agentcore.git
cd aws-ai-agentcore
```

If you already cloned it, update it instead:

```bash
git pull
```

## Step 2 — Install the required tools

Run the installer from the repository root:

```bash
bash modules/module-00-prerequisites/install-prerequisites.sh
```

The script detects macOS or Linux and is safe to rerun. It installs local packages, creates `.venv`, and installs the root `requirements.txt` for the course UI and local helper tools. Agent-specific dependencies are installed later from the active module snapshot before building or packaging the Runtime agent.

To intentionally rerun every installation step, use:

```bash
bash modules/module-00-prerequisites/install-prerequisites.sh --reset
```

The state file is local, ignored by Git, and contains no credentials.

### Docker notes

On macOS, the script installs Docker Desktop if Docker is missing. Open Docker Desktop and wait until the daemon is running before building containers.

On Linux, the script installs and starts Docker Engine. If your user is added to the `docker` group, log out and back in or run:

```bash
newgrp docker
```

On an x86_64 host, AgentCore Runtime container builds target ARM64. Register QEMU/binfmt before the first ARM64 build:

```bash
docker run --privileged --rm tonistiigi/binfmt --install arm64
```

Verify that Docker is usable without `sudo`:

```bash
docker version
docker info
docker run --rm hello-world
```

## Step 3 — Activate the Python environment

The installer creates `.venv` in the repository root. Activate it whenever you
open a new terminal:

```bash
source .venv/bin/activate
```

You should see `(.venv)` in your shell prompt. Verify the key Python tools:

```bash
python --version
pip --version
streamlit --version
```

If the environment is not setup by the installer, you can set it up manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Step 4 — Configure AWS CLI access

If you already have working AWS credentials, verify them first:

```bash
aws sts get-caller-identity
```

If that command fails, configure a profile:

```bash
aws configure
```

Provide:

```text
AWS Access Key ID:     <your-access-key-id>
AWS Secret Access Key: <your-secret-access-key>
Default region name:   us-east-1
Default output format: json
```

Verify the identity and select the course Region:

```bash
aws sts get-caller-identity
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION="$AWS_REGION"
```

> The course examples use `us-east-1`. AgentCore Browser, Runtime, Bedrock models, and other services must be available in the Region you select. Keep one Region consistently throughout the course.

## Step 5 — Confirm Bedrock model access

The course uses Anthropic Claude through Amazon Bedrock. Model availability and first-time-use requirements vary by account and Region.

1. Open the **Amazon Bedrock** console for your AWS region.
2. Open **Model catalog** and locate the Claude model used by the course.
3. Complete any first-time-use or model-access request shown by the console.
4. Confirm your identity can list foundation models:

```bash
aws bedrock list-foundation-models \
  --region "$AWS_REGION" \
  --query "modelSummaries[?contains(modelId,'claude')].[modelId,providerName]" \
  --output table
```

A successful command confirms API access. It does not guarantee that every specific model invocation is permitted; test the selected model when you reach
Module 02.

## Step 6 — Verify the complete setup

Run this checklist from the activated virtual environment:

```bash
python --version                 # 3.11+
aws --version                    # AWS CLI v2
aws sts get-caller-identity      # account and identity

git --version
docker --version
docker info
streamlit --version

python -c "import boto3, bedrock_agentcore, strands; print('Python dependencies OK')"
```

If Docker is not needed for your current path, `docker info` may be skipped;
Module 03 and later container deployment instructions require it.

## Setup checklist

| Item | Required | Verified |
|---|---:|---:|
| AWS account and permissions | Yes | ☐ |
| AWS CLI v2 and credentials | Yes | ☐ |
| Region selected consistently | Yes | ☐ |
| Bedrock Claude access | Yes | ☐ |
| Python 3.11+ and virtual environment | Yes | ☐ |
| Docker running | Module 03+ container path | ☐ |
| Git | Yes | ☐ |
| VS Code | Recommended | ☐ |

## Troubleshooting

### `aws sts get-caller-identity` fails

Run `aws configure`, confirm the selected profile with
`echo "$AWS_PROFILE"`, and verify the credentials belong to the intended AWS
account.

### Docker permission denied on Linux

Run `newgrp docker`, start the service with `sudo systemctl start docker`, or
log out and back in after the installer adds your user to the Docker group.

### Docker `exec format error` during an ARM64 build

Register binfmt/QEMU and bootstrap Buildx:

```bash
docker run --privileged --rm tonistiigi/binfmt --install arm64
docker buildx inspect --bootstrap
```

### Python dependency installation fails

Confirm Python is 3.11+, upgrade pip, and rerun the installer from the
repository root:

```bash
python -m pip install --upgrade pip
bash modules/module-00-prerequisites/install-prerequisites.sh
```

## Next step

Proceed to [Module 01 — AgentCore Platform Overview](../module-01-platform-overview/README.md).
