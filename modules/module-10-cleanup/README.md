# Module 10 — Cleanup: Remove Course Resources

This final module removes the AWS resources created throughout the ShopSmart
course. Deletion is intentionally destructive: it can permanently remove data,
users, agent resources, and stored container images.

**Do this only when you are finished with the course.** Review every resource
name and Region before deleting. Use the same AWS account and Region you used in
the earlier modules.

## Before you start

Confirm the active AWS identity and Region in the console:

1. Sign in to the **AWS Console** and confirm the account (top-right) and Region
   (e.g. `us-east-1`) match what you used throughout the course.

<details>
<summary>Via CLI (Optional)</summary>

```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws sts get-caller-identity
printf 'Account: %s\nRegion: %s\n' \
  "$AWS_ACCOUNT_ID" "$AWS_REGION"
```

</details>

> The steps below use the course names — `shopsmart-backend`,
> `shopsmart-carrier-browser`, `aria`, `aria-agent`, `shopsmart-gateway`, and
> so on. Substitute your own names if you changed them.

## Step 1 — Delete the CloudFormation stacks first

There are two course stacks:

- `shopsmart-carrier-browser` — private S3 bucket and CloudFront distribution.
- `shopsmart-backend` — DynamoDB, Lambda, API Gateway, and related IAM resources.

### 1a. Empty the carrier website bucket

CloudFormation cannot delete a non-empty S3 bucket, so empty the carrier website
bucket first.

1. Go to **AWS Console → CloudFormation → Stacks → `shopsmart-carrier-browser`**.
2. On the **Outputs** tab, note the `WebsiteBucketName` value.
3. Go to **S3**, open that bucket, select all objects, and choose **Delete**.

> If the stack is already deleted, skip this subsection. If the bucket holds
> anything other than course data, do not empty it.

<details>
<summary>Via CLI (Optional)</summary>

```bash
export CARRIER_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name shopsmart-carrier-browser \
  --query "Stacks[0].Outputs[?OutputKey=='WebsiteBucketName'].OutputValue" \
  --output text --region "$AWS_REGION")

echo "Carrier bucket: $CARRIER_BUCKET"
aws s3 rm "s3://$CARRIER_BUCKET" --recursive --region "$AWS_REGION"
```

</details>

### 1b. Delete both stacks

1. Go to **AWS Console → CloudFormation → Stacks**.
2. Select `shopsmart-carrier-browser`, choose **Delete**, and confirm.
3. Select `shopsmart-backend`, choose **Delete**, and confirm.
4. Wait until both stacks reach **DELETE_COMPLETE** (they disappear from the
   default list). The carrier stack can take several minutes while CloudFront is
   removed; the backend stack removes the orders/products tables and ShopSmart
   API resources.

<details>
<summary>Via CLI (Optional)</summary>

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

# Confirm both stacks are gone
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE \
  --region "$AWS_REGION" \
  --query "StackSummaries[?StackName=='shopsmart-backend' || StackName=='shopsmart-carrier-browser'].[StackName,StackStatus]" \
  --output table
```

</details>

## Step 2 — Remove S3 buckets created outside CloudFormation

These buckets were created manually and are not owned by either stack:

- Lambda deployment bucket, e.g. `shopsmart-lambda-<account-id>`.
- Knowledge Base document bucket, e.g. `shopsmart-knowledge-base-<account-id>`.

1. Go to **AWS Console → S3**.
2. Open each bucket, confirm it contains only course data, select all objects,
   and **Delete** them.
3. Then select the (now empty) bucket and choose **Delete** to remove the bucket.

> Only delete buckets that hold course data exclusively.

<details>
<summary>Via CLI (Optional)</summary>

```bash
export LAMBDA_BUCKET="shopsmart-lambda-$AWS_ACCOUNT_ID"
export KNOWLEDGE_BASE_BUCKET="shopsmart-knowledge-base-$AWS_ACCOUNT_ID"

aws s3 rb "s3://$LAMBDA_BUCKET" --force --region "$AWS_REGION"
aws s3 rb "s3://$KNOWLEDGE_BASE_BUCKET" --force --region "$AWS_REGION"

# If you used different names, list buckets and remove only the intended ones
aws s3api list-buckets --query 'Buckets[].Name' --output table
```

</details>

## Step 3 — Delete the Aria Runtime

The Runtime must be removed before deleting its ECR image repository or its
execution-role permissions.

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Runtime**.
2. Select the `aria` runtime, confirm it is the course runtime, and choose
   **Delete**.
3. If you created multiple `aria` versions or endpoints, remove each course
   runtime/endpoint.

<details>
<summary>Via CLI (Optional)</summary>

```bash
export RUNTIME_ID=$(aws bedrock-agentcore-control list-agent-runtimes \
  --region "$AWS_REGION" \
  --query "agentRuntimes[?agentRuntimeName=='aria'].agentRuntimeId" \
  --output text)

echo "Runtime ID: $RUNTIME_ID"

aws bedrock-agentcore-control delete-agent-runtime \
  --agent-runtime-id "$RUNTIME_ID" \
  --region "$AWS_REGION"
```

</details>

## Step 4 — Remove the Gateway and Policy resources

Policy is attached to the Gateway, so remove the Policy configuration and
policies before deleting the Gateway.

1. Open **Amazon Bedrock → AgentCore → Policy**.
2. Open `shopsmart_policy_engine`.
3. Delete the policies created in Module 08:
   `allow_read_tools`, `limit_refund_amount`, and `allow_non_refund_requests`.
4. Detach the policy engine from `shopsmart-gateway`.
5. Delete `shopsmart_policy_engine`.
6. Open **AgentCore → Gateways**, select `shopsmart-gateway`, and delete it.
7. Confirm the Gateway service role is no longer used by another application.

<details>
<summary>Via CLI (Optional) — discovery commands</summary>

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

</details>

> The Browser feature does not add a persistent custom Browser resource in this
> course. `browser_session(...)` uses the system Browser Tool and creates a
> short-lived session per lookup; those sessions stop automatically. There is no
> separate Browser resource to delete.

## Step 5 — Delete Memory resources

1. Go to **Amazon Bedrock → AgentCore → Memory**.
2. Find `aria-memory`, verify its ID, and choose **Delete**.

<details>
<summary>Via CLI (Optional)</summary>

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

</details>

## Step 6 — Delete the Knowledge Base

1. Go to **Amazon Bedrock → Knowledge bases**.
2. Find `shopsmart-kb`, verify its ID, and choose **Delete**.

After deletion, verify whether the managed vector-store resources created for
the Knowledge Base have been removed. If you selected a self-managed vector store
instead, delete its OpenSearch Serverless collection and associated
security/network policies only after confirming they belong to this course.

Also remove the Knowledge Base service role if it was created only for this
course. In **IAM → Roles**, identify it from the Knowledge Base details before
deleting it; do not delete a shared role.

<details>
<summary>Via CLI (Optional)</summary>

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

</details>

## Step 7 — Delete the Cognito resources

Cognito deletion permanently removes the ShopSmart test users and User Pool.
Delete the hosted domain first, then the app client, then the User Pool.

1. Go to **Amazon Cognito → User pools** and open your ShopSmart user pool.
2. Under **App integration → Domain**, delete the hosted domain.
3. Under **App integration → App clients**, delete the `shopsmart-streamlit`
   client (and any other course clients).
4. Return to the user pool overview and choose **Delete user pool**.

<details>
<summary>Via CLI (Optional)</summary>

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

</details>

> If the domain was configured with a full URL, use only the domain prefix when
> deleting it.

## Step 8 — Remove ECR images and repository

1. Go to **AWS Console → Amazon ECR → Repositories**.
2. Open `aria-agent`, confirm it belongs to this course, and review its images.
3. Select the repository and choose **Delete** (this removes all images in it).

<details>
<summary>Via CLI (Optional)</summary>

```bash
# Verify first
aws ecr describe-repositories \
  --repository-names aria-agent \
  --region "$AWS_REGION"

aws ecr list-images \
  --repository-name aria-agent \
  --region "$AWS_REGION" \
  --output table

# Then delete the repository and all images
aws ecr delete-repository \
  --repository-name aria-agent \
  --force \
  --region "$AWS_REGION"
```

</details>

## Step 9 — Remove SSM parameters

Delete only the `/aria/` parameters created for this course. Review them first —
the prefix may be shared by another application.

1. Go to **AWS Console → Systems Manager → Parameter Store**.
2. Filter by the `/aria` prefix and review the parameters.
3. If they belong only to ShopSmart, select them and choose **Delete**.

<details>
<summary>Via CLI (Optional)</summary>

Review the parameters first:

```bash
aws ssm get-parameters-by-path \
  --path /aria \
  --recursive \
  --with-decryption \
  --region "$AWS_REGION" \
  --query 'Parameters[].Name' \
  --output table
```

If `/aria` is used only by ShopSmart, remove all of them:

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

</details>

## Step 10 — Clean IAM roles and policies

Only delete IAM resources after confirming no other workload uses them. The
course roles are:

- `AriaAgentExecutionRole` — used by the Runtime.
- The Gateway service role created for `shopsmart-gateway`.
- The Knowledge Base service role created for `shopsmart-kb`.
- `ShopSmartLambdaRole` — normally removed with the backend stack.

1. Go to **AWS Console → IAM → Roles** and open `AriaAgentExecutionRole`.
2. Review its inline and attached policies to confirm it is course-only.
3. Delete the inline policies added in Modules 05–09 (e.g. `Gateway_Permissions`,
   `AriaMemoryAccess`, `AriaRuntimeConfigAccess`, `AriaKnowledgeBaseAccess`).
4. Detach `AmazonEC2ContainerRegistryReadOnly` and the other managed policies.
5. Delete the role.
6. Repeat the review-then-delete for the Gateway and Knowledge Base service
   roles if they were created only for this course.

> Do not delete a role that is shared or still referenced by any Runtime,
> Gateway, Knowledge Base, or other application.

<details>
<summary>Via CLI (Optional)</summary>

Review the role's policies first:

```bash
aws iam list-role-policies \
  --role-name AriaAgentExecutionRole \
  --output table

aws iam list-attached-role-policies \
  --role-name AriaAgentExecutionRole \
  --output table
```

If it is course-only, remove the inline policies, detach the managed policies,
and delete the role (policy names may differ if you chose your own):

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

</details>

## Step 11 — Remove CloudWatch logs

Runtime logs are not removed automatically when a Runtime is deleted.

1. Go to **AWS Console → CloudWatch → Log groups**.
2. Filter by `/aws/bedrock-agentcore/runtimes/aria-`.
3. Confirm the log groups belong to this course, then select and **Delete** them.

> Transaction Search and account-level CloudWatch/X-Ray settings may be shared
> with other applications; leave them enabled unless you intentionally want to
> change account-wide observability configuration.

<details>
<summary>Via CLI (Optional)</summary>

```bash
# List the course log groups
aws logs describe-log-groups \
  --log-group-name-prefix /aws/bedrock-agentcore/runtimes/aria- \
  --region "$AWS_REGION" \
  --query 'logGroups[].logGroupName' \
  --output table

# Delete each confirmed course log group
aws logs delete-log-group \
  --log-group-name <course-runtime-log-group> \
  --region "$AWS_REGION"
```

</details>

## Final verification

Confirm the main course resources are gone:

1. **CloudFormation** — no `shopsmart-*` stacks remain.
2. **Bedrock → AgentCore → Runtime / Gateways** — no `aria` / `shopsmart-gateway`.
3. **ECR → Repositories** — no `aria-agent`.

<details>
<summary>Via CLI (Optional)</summary>

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

</details>

Congratulations! This completes the ShopSmart AgentCore course.

---

## Course Summary

Over the course you built **Aria**, ShopSmart's AI customer support agent, one
capability at a time — starting from a single local Python file and ending with
a production-grade agent running on Amazon Bedrock AgentCore. Each module
externalized a simulated or hardcoded piece into a managed capability:

| AgentCore capability | What it gave Aria | Module |
|----------------------|-------------------|:------:|
| **Runtime** | Managed, scalable cloud hosting for the agent | 03 |
| **Knowledge Base** | Grounded answers retrieved from ShopSmart's real policy documents | 04 |
| **Gateway** | Real order, product, and return tools from the ShopSmart REST API (via MCP) | 05 |
| **Memory** | The ability to remember customers and context across sessions | 06 |
| **Identity** | Authenticated customers via Cognito, with verified identity passed to the agent | 07 |
| **Policy** | Enforced guardrails on what Aria is allowed to do | 08 |
| **Browser** | The ability to read live carrier tracking pages that have no API | 09 |

Aria began (Module 02) as a self-contained agent with simulated tools and an
inline FAQ. By the end she was a deployed, authenticated, governed agent that
retrieves real knowledge, calls real backend APIs, remembers her customers, and
even operates a live website — all assembled from composable AgentCore building
blocks.

Thank you for building along. 🎉
