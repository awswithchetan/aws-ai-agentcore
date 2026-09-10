#!/bin/bash
# Build, tag, and push the Aria agent image to ECR.
# Assumes AWS_ACCOUNT_ID, AWS_REGION, ECR_REPO are already set in your shell,
# and you are already logged in to ECR.
set -e

cd aria-agent

docker build --platform linux/arm64 -t aria-agent .
docker tag aria-agent:latest "$ECR_REPO:latest"
docker push "$ECR_REPO:latest"

cd ..
echo "✓ Build and push complete"
