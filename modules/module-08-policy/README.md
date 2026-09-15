# Module 08 — Policy: Guardrails & Governance

In this module you will add **deterministic guardrails** to Aria using
**Amazon Bedrock AgentCore Policy**. Instead of relying on the LLM to
self-enforce business rules (which can be bypassed through prompt injection or
model error), rules are evaluated at the Gateway boundary — before your agent
code or backend tools ever see the request.

The rules are written in **Cedar**, an open-source policy language (the same
language behind Amazon Verified Permissions) that expresses authorization as
explicit `permit`/`forbid` statements. AgentCore Policy evaluates these Cedar
policies on every tool call and returns a simple allow or deny decision.

By the end of this module, Aria enforces these rules deterministically:
- Read operations (get order, list orders, search products) are always allowed
- Return requests (`submit_request`) are blocked when the refund amount exceeds
  $500 — regardless of what the LLM decides
- All policy enforcement decisions are logged to CloudWatch

---

## What AgentCore Policy Does

```
Streamlit UI
  │  Bearer token + prompt
  ▼
AgentCore Runtime (aria)
  │  Calls tools via Gateway (MCP)
  ▼
AgentCore Gateway  ◄─── Policy Engine (Cedar rules evaluated here)
  │  ALLOW → forward request to the target
  │  DENY  → return error to agent (tool call blocked)
  ▼
ShopSmart REST API (API Gateway → Lambda → DynamoDB)
```

Policy sits **between** the AgentCore Gateway and its target. Every tool call
from Aria is evaluated against the Cedar policies *before* the Gateway forwards
the request to the target. If a rule denies the call, the request never reaches
the backend at all — and the agent just receives a denial it can relay to the
customer.

<details>
<summary>Why Cedar instead of prompt-based guardrails?</summary>

| | Prompt-based rules | Cedar policy |
|---|---|---|
| Bypass risk | High — LLM can be manipulated | None — evaluated outside agent code |
| Consistency | Probabilistic | Deterministic — same input always same result |
| Audit trail | None | Every decision logged to CloudWatch |
| Change management | Redeploy agent | Update policy only — no redeploy |
| Latency | Extra LLM tokens | Sub-millisecond evaluation |

</details>

---

## Step 1 — Create a Policy Engine

A policy engine is a container that holds your Cedar policies. You create one
engine per domain (e.g. one for ShopSmart) and attach it to one or more
gateways.

### Via AWS Console

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Policy**
2. Click **Create policy engine**
3. Configure:
   - **Name**: `shopsmart_policy_engine`
   - **Description**: `Guardrails for Aria — ShopSmart customer support agent`
4. Click **Create**
5. Note down the **Policy Engine ARN** — you'll need it in Step 3

### Via CLI (Optional)

<details>
<summary>Create policy engine via CLI</summary>

```bash
export AWS_REGION=us-east-1

POLICY_ENGINE_ARN=$(aws bedrock-agentcore-control create-policy-engine \
  --name shopsmart_policy_engine \
  --description "Guardrails for Aria — ShopSmart customer support agent" \
  --region $AWS_REGION \
  --query 'policyEngineArn' --output text)

echo "Policy Engine ARN: $POLICY_ENGINE_ARN"
```

</details>

---

## Step 2 — Attach the Policy Engine to the Gateway

Connect the policy engine to the ShopSmart Gateway with **enforcement enabled**
so all tool calls are evaluated and denied requests are blocked.

### Grant the Gateway role permission to use the policy engine

The Gateway's execution role needs three Policy actions: `GetPolicyEngine` (read
the engine when it's attached), and `AuthorizeAction` plus
`PartiallyAuthorizeActions` (evaluate Cedar policies on each tool call). Add them
to the role you created for the Module 05 Gateway (e.g. `ShopSmartGatewayRole`).

**Via AWS Console**

1. Go to **IAM → Roles → ShopSmartGatewayRole**
2. Click **Add permissions → Create inline policy**
3. Switch to the **JSON** editor and paste, replacing `<POLICY_ENGINE_ARN>` with
   your ARN from Step 1 and `<GATEWAY_ARN>` with your Gateway ARN:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PolicyEngineConfiguration",
      "Effect": "Allow",
      "Action": "bedrock-agentcore:GetPolicyEngine",
      "Resource": "<POLICY_ENGINE_ARN>"
    },
    {
      "Sid": "PolicyEngineAuthorization",
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:AuthorizeAction",
        "bedrock-agentcore:PartiallyAuthorizeActions"
      ],
      "Resource": [
        "<POLICY_ENGINE_ARN>",
        "<GATEWAY_ARN>"
      ]
    }
  ]
}
```

4. Name it `ShopSmartGatewayPolicyEngineAccess` and click **Create policy**

<details>
<summary>Via CLI</summary>

```bash
export AWS_REGION=us-east-1
export GATEWAY_ROLE=ShopSmartGatewayRole   # the role attached to your Gateway
export POLICY_ENGINE_ARN=<your-policy-engine-arn>
export GATEWAY_ARN=<your-gateway-arn>

aws iam put-role-policy \
  --role-name "$GATEWAY_ROLE" \
  --policy-name ShopSmartGatewayPolicyEngineAccess \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [
      {
        \"Sid\": \"PolicyEngineConfiguration\",
        \"Effect\": \"Allow\",
        \"Action\": \"bedrock-agentcore:GetPolicyEngine\",
        \"Resource\": \"${POLICY_ENGINE_ARN}\"
      },
      {
        \"Sid\": \"PolicyEngineAuthorization\",
        \"Effect\": \"Allow\",
        \"Action\": [
          \"bedrock-agentcore:AuthorizeAction\",
          \"bedrock-agentcore:PartiallyAuthorizeActions\"
        ],
        \"Resource\": [\"${POLICY_ENGINE_ARN}\", \"${GATEWAY_ARN}\"]
      }
    ]
  }" \
  --region $AWS_REGION
```

</details>

### Attach the engine


### Via AWS Console

1. Go to **AgentCore → Gateway → shopsmart-gateway**
2. Click **Edit**
3. Find the **Policy engine** section
4. Select `shopsmart_policy_engine` from the dropdown
5. Under **Enforcement mode**, choose **Enable enforcement**
6. Click **Save**

### Via CLI (Optional)

<details>
<summary>Attach policy engine via CLI</summary>

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1

GATEWAY_ID=$(aws bedrock-agentcore-control list-gateways \
  --region $AWS_REGION \
  --query "gateways[?name=='shopsmart-gateway'].gatewayId" \
  --output text)

aws bedrock-agentcore-control update-gateway \
  --gateway-id $GATEWAY_ID \
  --policy-engine-configuration "{
    \"policyEngineArn\": \"${POLICY_ENGINE_ARN}\",
    \"attachMode\": \"ENFORCE\"
  }" \
  --region $AWS_REGION
```

</details>

---

## Step 3 — Add and Test Cedar Policies

Cedar uses a `permit`/`forbid` model. A request is allowed only if at least one
`permit` matches **and** no `forbid` matches.

> These policies reference the Gateway tool actions by name, so they assume the
> Module 05 Gateway target is named `ShopSmartAPI`. If you used a different
> target name, adjust the action IDs in the Cedar below to match.

You'll add the policies in two groups and test each group's effect before moving
on, so you can see exactly what each policy does:

| Policy | Rule |
|---|---|
| `allow_read_tools` | Permit all read operations (get_order, list_orders, get_product, search_products) |
| `limit_refund_amount` | Permit submit_request only when refund_amount ≤ 500 |
| `allow_non_refund_requests` | Permit submit_request when there is no refund_amount (complaints, inquiries) |

> Test through the Streamlit UI (logged in as `alice@example.com`), the same way
> you tested Modules 05–07.

### Get your Gateway ARN

Cedar policies reference the Gateway by its full ARN. Get it first:

```bash
aws bedrock-agentcore-control get-gateway \
  --gateway-identifier <your-gateway-id> \
  --region us-east-1 \
  --query 'gatewayArn' --output text
```

Create the three policies below via the console. Prefer the CLI? Use the
collapsible script to create all three at once, then run the tests shown under
each policy.

<details>
<summary>Add all policies via CLI</summary>

The Policy commands require a recent AWS CLI build. If
`aws bedrock-agentcore-control create-policy` reports an invalid choice, your
CLI predates the Policy API — use the console flow instead.

```bash
# The create-policy call needs the policy engine ID (not the full ARN).
POLICY_ENGINE_ID=$(aws bedrock-agentcore-control list-policy-engines \
  --region $AWS_REGION \
  --query "items[?name=='shopsmart_policy_engine'].policyEngineId" \
  --output text)

# Policy 1 — allow read tools
aws bedrock-agentcore-control create-policy \
  --policy-engine-id $POLICY_ENGINE_ID \
  --name allow_read_tools \
  --policy-content "permit(
  principal,
  action in [
    AgentCore::Action::\"ShopSmartAPI___get_order\",
    AgentCore::Action::\"ShopSmartAPI___list_orders\",
    AgentCore::Action::\"ShopSmartAPI___get_product\",
    AgentCore::Action::\"ShopSmartAPI___search_products\"
  ],
  resource == AgentCore::Gateway::\"${GATEWAY_ARN}\"
);" \
  --region $AWS_REGION

# Policy 2 — allow refund requests within the $500 limit
aws bedrock-agentcore-control create-policy \
  --policy-engine-id $POLICY_ENGINE_ID \
  --name limit_refund_amount \
  --policy-content "permit(
  principal,
  action == AgentCore::Action::\"ShopSmartAPI___submit_request\",
  resource == AgentCore::Gateway::\"${GATEWAY_ARN}\"
)
when {
  context.input has refund_amount && context.input.refund_amount <= 500
};" \
  --region $AWS_REGION

# Policy 3 — allow non-refund requests (complaints, inquiries)
aws bedrock-agentcore-control create-policy \
  --policy-engine-id $POLICY_ENGINE_ID \
  --name allow_non_refund_requests \
  --policy-content "permit(
  principal,
  action == AgentCore::Action::\"ShopSmartAPI___submit_request\",
  resource == AgentCore::Gateway::\"${GATEWAY_ARN}\"
)
when {
  !(context.input has refund_amount)
};" \
  --region $AWS_REGION
```

</details>

### Policy 1 — Allow read tools

This permits all read-only tool calls unconditionally.

**Via AWS Console**

1. Go to **AgentCore → Policy → shopsmart-policy-engine**
2. Click **Add policy**
3. **Policy name**: `allow_read_tools`
4. Select **Cedar** as the policy language
5. Paste the following Cedar, replacing `<GATEWAY_ARN>` with your actual ARN:

```cedar
permit(
  principal,
  action in [
    AgentCore::Action::"ShopSmartAPI___get_order",
    AgentCore::Action::"ShopSmartAPI___list_orders",
    AgentCore::Action::"ShopSmartAPI___get_product",
    AgentCore::Action::"ShopSmartAPI___search_products"
  ],
  resource == AgentCore::Gateway::"<GATEWAY_ARN>"
);
```

6. Click **Save**

> **Action name format**: AgentCore names each tool `<TargetName>___<toolName>`
> (three underscores). With the target named `ShopSmartAPI`, the actions are
> `ShopSmartAPI___get_order`, etc. If your target has a different name, adjust
> these accordingly.

**Test it** — logged in as Alice:

1. Read tool is allowed:
   ```
   What are my orders?
   ```
   Aria lists Alice's orders. The read tools are now permitted; if you skipped
   this policy, the same request would be denied by Cedar's default-deny.

2. Write tool is still denied:
   ```
   I'd like to return order ORD-1001. It was the wrong size.
   ```
   This calls `submit_request`, which no policy permits yet — so Cedar's
   default-deny blocks it at the Gateway and Aria can't complete the return.
   This confirms that only the actions you explicitly permit are allowed. You
   add the `submit_request` permits next.

### Policies 2 & 3 — Allow return requests (the refund cap)

These two policies work as a pair to govern `submit_request`, so add both before
testing:

- `limit_refund_amount` permits a return **when the refund is ≤ $500**.
- `allow_non_refund_requests` permits requests with **no refund amount**
  (complaints, inquiries, exchanges).

Because Cedar is default-deny, a request is allowed only if one of these permits
matches. Together they cover every legitimate `submit_request`; a refund over
$500 matches neither, so it is blocked.

**Policy 2 — `limit_refund_amount`**

We express the refund cap as a **conditional permit**: `submit_request` is
allowed only when the refund amount is within limit.

Via AWS Console:

1. Click **Add policy**
2. **Policy name**: `limit_refund_amount`
3. Select **Cedar**
4. Paste, replacing `<GATEWAY_ARN>`:

```cedar
permit(
  principal,
  action == AgentCore::Action::"ShopSmartAPI___submit_request",
  resource == AgentCore::Gateway::"<GATEWAY_ARN>"
)
when {
  context.input has refund_amount && context.input.refund_amount <= 500
};
```

5. Click **Save**

> Keep the presence check and the comparison on the same `&&` expression
> (`has refund_amount && refund_amount <= 500`). Cedar requires this to safely
> access an optional attribute.

**Policy 3 — `allow_non_refund_requests`**

Requests without a `refund_amount` (complaints, inquiries, exchanges) need their
own permit, otherwise they'd be denied by default.

Via AWS Console:

1. Click **Add policy**
2. **Policy name**: `allow_non_refund_requests`
3. Select **Cedar**
4. Paste, replacing `<GATEWAY_ARN>`:

```cedar
permit(
  principal,
  action == AgentCore::Action::"ShopSmartAPI___submit_request",
  resource == AgentCore::Gateway::"<GATEWAY_ARN>"
)
when {
  !(context.input has refund_amount)
};
```

5. Click **Save**

**Test the return flow** — logged in as Alice:

1. Small refund, within limit (should succeed):
   ```
   I'd like to return order ORD-1001. It was the wrong size. The refund is about $100.
   ```
   The refund is under $500, so `limit_refund_amount` permits it and Aria
   initiates the return.

2. Complaint with no refund (should succeed):
   ```
   I want to file a complaint about the packaging on order ORD-1001.
   ```
   There's no `refund_amount`, so `allow_non_refund_requests` permits it.

3. Large refund, over the limit (should be blocked):
   ```
   I want to return order ORD-1004 and get the full refund of $519.96.
   ```
   ORD-1004 totals $519.96 — over $500. The request matches neither
   `submit_request` permit, so Cedar's default-deny blocks the tool call before
   it reaches the API. Aria relays the denial — something like:
   ```
   I'm unable to process a refund of that amount automatically. Refunds over
   $500 require manual review by our team. I can escalate this for you.
   ```

<details>
<summary>Verify enforcement in CloudWatch</summary>

Policy decisions are logged to the gateway's CloudWatch log group. Find and
tail it:

```bash
# Find the gateway log group (name includes your gateway ID)
aws logs describe-log-groups \
  --region us-east-1 \
  --query "logGroups[?contains(logGroupName, 'gateway')].logGroupName" \
  --output text

# Tail it (substitute the group name from above)
aws logs tail <gateway-log-group> --region us-east-1 --since 10m
```

If no gateway log group exists, enable log delivery on the gateway (or check
the gateway's Monitoring tab in the console). With **Exception level debug**
enabled on the gateway, denied requests also surface a clear message in the
tool response returned to the agent.

</details>

---

<details>
<summary>Cedar policy reference files</summary>

The three Cedar policies are also included in the repo under
`aria-agent/policies/` (`allow_read_tools.cedar`, `limit_refund_amount.cedar`,
`allow_non_refund_requests.cedar`). These are reference copies — the policies
are created and enforced in the policy engine above, not loaded from these
files at runtime. Each contains a `<GATEWAY_ARN>` placeholder to substitute
with your gateway ARN.

</details>

---

## What You Achieved

Aria now enforces a real business rule — the $500 refund cap — as a
deterministic guardrail that lives outside the agent, exactly how production
systems separate policy from application logic. The LLM can no longer be
talked into an over-limit refund through clever prompting, because the decision
is made by the Cedar policy engine at the Gateway boundary, not by the model.

This is the same pattern teams rely on in production: authorization rules are
declarative, versioned, and auditable; they change without redeploying the
agent; and every allow/deny is logged for compliance. You've moved a critical
control out of "the model should probably not do this" territory and into an
enforced, reviewable policy — the difference between hoping an agent behaves and
guaranteeing it.

---

<details>
<summary>Cedar Quick Reference</summary>

```cedar
// Permit — allow this action
permit(principal, action == AgentCore::Action::"Target___tool", resource == AgentCore::Gateway::"<arn>");

// Forbid with condition on tool input
forbid(principal, action == AgentCore::Action::"Target___tool", resource == AgentCore::Gateway::"<arn>")
when { context.input has fieldName && context.input.fieldName > 100 };

// Check if field exists before using it (prevents errors on optional fields)
context.input has fieldName && context.input.fieldName == "value"

// Check principal tags (e.g. OAuth scopes/roles from JWT)
principal.hasTag("scope") && principal.getTag("scope") like "*write*"

// Multiple actions in one permit
action in [AgentCore::Action::"Target___tool1", AgentCore::Action::"Target___tool2"]
```

Action naming: `<GatewayTargetName>___<toolName>` (three underscores)

</details>

<details>
<summary>What You Learned</summary>

- How AgentCore Policy sits at the Gateway boundary, outside agent code
- How to create a policy engine and attach it to a Gateway
- Cedar's permit/forbid model and implicit deny default
- How to guard tool inputs (`context.input`) with conditions
- Why Cedar-based guardrails are stronger than prompt-based rules
- How to test and verify policy enforcement via CloudWatch

</details>

---

## Next step

Proceed to [Module 09 — Browser](../module-09-browser/README.md)
where you will use AgentCore Browser and a managed Chrome session to check live
carrier tracking information.
