# Module 10 — Cleanup: Remove Course Resources

This final module removes the AWS resources created throughout the ShopSmart
course. The commands below are intentionally destructive: they can permanently
delete data, users, agent resources, and stored container images.

**Run these steps only when you are finished with the course.** Review every
resource name and Region before executing a command. Use the same AWS account
and Region used in the earlier modules.

## Before you start

Set the course values and confirm the active AWS identity:

```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws sts get-caller-identity
printf 'Account: %s\nRegion: %s\n' \
  "$AWS_ACCOUNT_ID" "$AWS_REGION"
```

> The commands use `shopsmart-backend`, `shopsmart-carrier-browser`, `aria`,
> `aria-agent`, `shopsmart-gateway`, and the resource names from this course.
> Replace them if you used different names.

## Step 1 — Delete the CloudFormation stacks first

There are two course stacks:

- `shopsmart-carrier-browser` — private S3 bucket and CloudFront distribution.
- `shopsmart-backend` — DynamoDB, Lambda, API Gateway, and related IAM
  resources.

### 1a. Empty the carrier website bucket

CloudFormation cannot delete a non-empty S3 bucket. Retrieve its name from the
stack, remove the uploaded website files, and then delete the stack:

```bash
export CARRIER_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name shopsmart-carrier-browser \
  --query "Stacks[0].Outputs[?OutputKey=='WebsiteBucketName'].OutputValue" \
  --output text --region "$AWS_REGION")

echo "Carrier bucket: $CARRIER_BUCKET"
aws s3 rm "s3://$CARRIER_BUCKET" --recursive --region "$AWS_REGION"
```

If the stack has already been deleted, skip this subsection. If the bucket is
used for anything other than this course, do not run the `aws s3 rm` command.

### 1b. Delete both stacks

```bash
aws cloudformation delete-stack \
  --stack-name shopsmart-carrier-browser \
  --region "$AWS_REGION"

aws cloudformation delete-stack \
  --stack-name shopsmart-backend \
  --region "$AWS_REGION"

aws cloudformation wait stack-delete-complete \
  --stack-name shopsmart-carrier-browser \
  --region "$AWS_REGION"

aws cloudformation wait stack-delete-complete \
  --stack-name shopsmart-backend \
  --region "$AWS_REGION"
```

The carrier stack may take several minutes while CloudFront is removed. The
backend stack removes the orders/products tables and ShopSmart API resources.
Confirm both stacks are gone before continuing.

```bash
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE \
  --region "$AWS_REGION" \
  --query "StackSummaries[?StackName=='shopsmart-backend' || StackName=='shopsmart-carrier-browser'].[StackName,StackStatus]" \
  --output table
```

## Step 2 — Remove S3 buckets created outside CloudFormation

The following buckets were created manually and are not owned by either stack:

- Lambda deployment bucket, for example `shopsmart-lambda-$AWS_ACCOUNT_ID`.
- Knowledge Base document bucket, for example
  `shopsmart-knowledge-base-$AWS_ACCOUNT_ID`.

Only run these commands if the buckets contain course data exclusively:

```bash
export LAMBDA_BUCKET="shopsmart-lambda-$AWS_ACCOUNT_ID"
export KNOWLEDGE_BASE_BUCKET="shopsmart-knowledge-base-$AWS_ACCOUNT_ID"

aws s3 rb "s3://$LAMBDA_BUCKET" --force --region "$AWS_REGION"
aws s3 rb "s3://$KNOWLEDGE_BASE_BUCKET" --force --region "$AWS_REGION"
```

If you used different bucket names, list buckets and remove only the intended
ones:

```bash
aws s3api list-buckets \
  --query 'Buckets[].Name' \
  --output table
```

## Step 3 — Delete the Aria Runtime

The Runtime must be removed before deleting its ECR image repository or its
execution-role permissions.

```bash
export RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes \
  --region "$AWS_REGION" \
  --query "agentRuntimes[?agentRuntimeName=='aria'].agentRuntimeId" \
  --output text)

echo "Runtime ID: $RUNTIME_ID"
```

If the command returns a Runtime ID, confirm it is the course Runtime, then
execute:

```bash
aws bedrock-agentcore-control delete-agent-runtime \
  --agent-runtime-id "$RUNTIME_ID" \
  --region "$AWS_REGION"
```

If you created multiple `aria` versions or endpoints, inspect them in the
AgentCore console and remove each course Runtime/endpoint as appropriate.

## Step 4 — Remove the Gateway and Policy resources

Policy is attached to the Gateway, so remove the Policy configuration and
policies before deleting the Gateway. Use the console when resource IDs are
unclear:

1. Open **Amazon Bedrock → AgentCore → Policy**.
2. Open `shopsmart_policy_engine`.
3. Delete the policies created in Module 08:
   `allow_read_tools`, `limit_refund_amount`, and
   `allow_non_refund_requests`.
4. Detach the policy engine from `shopsmart-gateway`.
5. Delete `shopsmart_policy_engine`.
6. Open **AgentCore → Gateways**, select `shopsmart-gateway`, and delete it.
7. Confirm the Gateway service role is no longer used by another application.

Optional discovery commands:

```bash
aws bedrock-agentcore-control list-gateways \
  --region "$AWS_REGION" \
  --query "gateways[?name=='shopsmart-gateway'].[gatewayId,name,gatewayArn]" \
  --output table

aws bedrock-agentcore-control list-policy-engines \
  --region "$AWS_REGION" \
  --query "items[?name=='shopsmart_policy_engine']" \
  --output table
```

The Browser feature does not add a persistent custom Browser resource in this
course. `browser_session(...)` uses the system Browser Tool and creates a
short-lived session per lookup; those sessions stop automatically. There is no
separate Browser resource to delete.

## Step 5 — Delete Memory and Harness resources

### Memory

Find the Memory created as `aria-memory`, verify its ID, and delete it:

```bash
aws bedrock-agentcore-control list-memories \
  --region "$AWS_REGION" \
  --query "memories[?name=='aria-memory'].[memoryId,name,status]" \
  --output table

export MEMORY_ID=<your-aria-memory-id>
aws bedrock-agentcore-control delete-memory \
  --memory-id "$MEMORY_ID" \
  --region "$AWS_REGION"
```

### Harness

Module 02 normally deletes `aria_harness` before Module 03. If it still exists:

```bash
aws bedrock-agentcore-control list-harnesses \
  --region "$AWS_REGION" \
  --query "harnesses[?name=='aria_harness']" \
  --output table

aws bedrock-agentcore-control delete-harness \
  --harness-id <your-harness-id> \
  --region "$AWS_REGION"
```

If your AWS CLI does not expose these list operations, use the AgentCore
console to locate and delete the named resource.

## Step 6 — Delete the Knowledge Base

The Knowledge Base was created in Amazon Bedrock as `shopsmart-kb`. First
verify the ID, then delete it from the Bedrock Knowledge Bases page:

```bash
aws bedrock-agent list-knowledge-bases \
  --region "$AWS_REGION" \
  --query "knowledgeBaseSummaries[?name=='shopsmart-kb'].[knowledgeBaseId,name,status]" \
  --output table

export KNOWLEDGE_BASE_ID=<your-shopsmart-kb-id>
aws bedrock-agent delete-knowledge-base \
  --knowledge-base-id "$KNOWLEDGE_BASE_ID" \
  --region "$AWS_REGION"
```

After deletion, verify whether the managed vector-store resources created for
the Knowledge Base have been removed. If you selected a self-managed vector
store instead, delete its OpenSearch Serverless collection and associated
security/network policies only after confirming they belong to this course.

Also remove the Knowledge Base service role if it was created only for this
course. In **IAM → Roles**, identify it from the Knowledge Base details before
deleting it; do not delete a shared role.

## Step 7 — Delete the Cognito resources

Cognito deletion permanently removes the ShopSmart test users and User Pool.
Delete the hosted domain first, then the User Pool client and User Pool.

```bash
export USER_POOL_ID=<your-shopsmart-user-pool-id>
export COGNITO_DOMAIN_PREFIX=<your-cognito-domain-prefix>

aws cognito-idp delete-user-pool-domain \
  --user-pool-id "$USER_POOL_ID" \
  --domain "$COGNITO_DOMAIN_PREFIX" \
  --region "$AWS_REGION"

aws cognito-idp list-user-pool-clients \
  --user-pool-id "$USER_POOL_ID" \
  --region "$AWS_REGION" \
  --query 'UserPoolClients[].{Id:ClientId,Name:ClientName}' \
  --output table

export CLIENT_ID=<your-shopsmart-streamlit-client-id>
aws cognito-idp delete-user-pool-client \
  --user-pool-id "$USER_POOL_ID" \
  --client-id "$CLIENT_ID" \
  --region "$AWS_REGION"

aws cognito-idp delete-user-pool \
  --user-pool-id "$USER_POOL_ID" \
  --region "$AWS_REGION"
```

If you created more than one app client, delete each course client before the
pool. If the domain was configured with a full URL, use only the domain prefix
for `delete-user-pool-domain`.

## Step 8 — Remove ECR images and repository

The course uses the `aria-agent` ECR repository. Verify it before deleting it:

```bash
aws ecr describe-repositories \
  --repository-names aria-agent \
  --region "$AWS_REGION"

aws ecr list-images \
  --repository-name aria-agent \
  --region "$AWS_REGION" \
  --output table
```

Then remove the repository and all images:

```bash
aws ecr delete-repository \
  --repository-name aria-agent \
  --force \
  --region "$AWS_REGION"
```

## Step 9 — Remove SSM parameters

Delete only the `/aria/` parameters created for this course. Review the list
first because the prefix may be shared by another application:

```bash
aws ssm get-parameters-by-path \
  --path /aria \
  --recursive \
  --with-decryption \
  --region "$AWS_REGION" \
  --query 'Parameters[].Name' \
  --output table
```

If `/aria` is used only by ShopSmart, remove all parameters:

```bash
PARAMETERS=$(aws ssm get-parameters-by-path \
  --path /aria \
  --recursive \
  --region "$AWS_REGION" \
  --query 'Parameters[].Name' \
  --output text)

if [ -n "$PARAMETERS" ]; then
  aws ssm delete-parameters \
    --names $PARAMETERS \
    --region "$AWS_REGION"
fi
```

Otherwise, delete only the known course parameters:

```bash
aws ssm delete-parameters \
  --names \
    /aria/model_id \
    /aria/knowledge_base_id \
    /aria/kb_num_results \
    /aria/region \
    /aria/gateway_endpoint \
    /aria/memory_id \
    /aria/memory_strategy_id \
    /aria/cognito_user_pool_id \
    /aria/cognito_client_id \
    /aria/cognito_domain \
    /aria/carrier_tracking_url \
  --region "$AWS_REGION"
```

## Step 10 — Clean IAM roles and policies

Only delete IAM resources after confirming no other workload uses them.
Review the IAM console first:

- `AriaAgentExecutionRole` — used by the Harness and Runtime.
- The Gateway service role created for `shopsmart-gateway`.
- The Knowledge Base service role created for `shopsmart-kb`.
- `ShopSmartLambdaRole` — normally removed with the backend stack.

List the execution role policies before removing them:

```bash
aws iam list-role-policies \
  --role-name AriaAgentExecutionRole \
  --output table

aws iam list-attached-role-policies \
  --role-name AriaAgentExecutionRole \
  --output table
```

If `AriaAgentExecutionRole` is used only by this course, remove the inline
policies added in Modules 05–09, detach the ECR managed policy, and then delete
the role. Policy names may differ if you chose different names:

```bash
aws iam delete-role-policy \
  --role-name AriaAgentExecutionRole \
  --policy-name Gateway_Permissions

aws iam delete-role-policy \
  --role-name AriaAgentExecutionRole \
  --policy-name AriaMemoryAccess

aws iam detach-role-policy \
  --role-name AriaAgentExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly

aws iam delete-role --role-name AriaAgentExecutionRole
```

Do not run the role deletion if the role is shared or if any Runtime, Gateway,
Knowledge Base, or other application still references it.

## Step 11 — Remove CloudWatch logs and local artifacts

Runtime logs are not removed automatically when a Runtime is deleted. Locate
the course log groups and delete only the matching groups:

```bash
aws logs describe-log-groups \
  --log-group-name-prefix /aws/bedrock-agentcore/runtimes/aria- \
  --region "$AWS_REGION" \
  --query 'logGroups[].logGroupName' \
  --output table
```

For each confirmed course log group:

```bash
aws logs delete-log-group \
  --log-group-name <course-runtime-log-group> \
  --region "$AWS_REGION"
```

Transaction Search and account-level CloudWatch/X-Ray settings may be shared
with other applications; leave them enabled unless you intentionally want to
change account-wide observability configuration.

Optional local cleanup from the repository root:

```bash
find . -type d -name __pycache__ -prune -exec rm -rf {} +
rm -f shopsmart-backend/lambdas/*.zip
rm -f aria-agent.zip

docker image rm aria-agent:latest 2>/dev/null || true
```

## Final verification

Use these checks to confirm that the main course resources are gone:

```bash
aws cloudformation list-stacks --region "$AWS_REGION" \
  --query "StackSummaries[?contains(StackName, 'shopsmart')].[StackName,StackStatus]" \
  --output table

aws bedrock-agentcore-control list-agent-runtimes \
  --region "$AWS_REGION" --output table

aws bedrock-agentcore-control list-gateways \
  --region "$AWS_REGION" --output table

aws ecr describe-repositories \
  --repository-names aria-agent \
  --region "$AWS_REGION" 2>&1 || true
```

A deleted resource may remain visible briefly while AWS finishes asynchronous
cleanup. Check the relevant service console again after a few minutes.


Congratulations ! This completes the ShopSmart AgentCore course.
