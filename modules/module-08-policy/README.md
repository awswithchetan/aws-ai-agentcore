# Module 08 — Policy: Guardrails & Governance

In this module you will add **deterministic guardrails** to Aria using
**Amazon Bedrock AgentCore Policy**. Instead of relying on the LLM to
self-enforce business rules (which can be bypassed through prompt injection or
model error), rules are evaluated in Cedar at the Gateway boundary — before
your agent code or backend tools ever see the request.

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

## Prerequisites

- Module 05 Gateway must be set up with the target named **`ShopSmartAPI`**
  (the tool action names in the Cedar policies depend on this exact target name)
- The `submit_request` tool must accept a `refund_amount` field. This was added
  in Module 05 — if you set up the Gateway before that, edit the target's
  OpenAPI schema and confirm `submit_request` includes `refund_amount`.
- Note your **Gateway ARN**. Get it with:

  ```bash
  aws bedrock-agentcore-control get-gateway \
    --gateway-identifier <your-gateway-id> \
    --region us-east-1 \
    --query 'gatewayArn' --output text
  ```

---

## Step 1 — Create a Policy Engine

A policy engine is a container that holds your Cedar policies. You create one
engine per domain (e.g. one for ShopSmart) and attach it to one or more
gateways.

### Via AWS Console

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Policy**
2. Click **Create policy engine**
3. Configure:
   - **Name**: `shopsmart_policy_engine`  *(underscores only — policy resource names cannot contain dashes)*
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

## Step 3 — Write and Add Cedar Policies

Cedar uses a `permit`/`forbid` model. A request is allowed only if at least one
`permit` matches **and** no `forbid` matches.

We will create three policies:

| Policy | Rule |
|---|---|
| `allow_read_tools` | Permit all read operations (get_order, list_orders, get_product, search_products) |
| `limit_refund_amount` | Permit submit_request only when refund_amount ≤ 500 |
| `allow_non_refund_requests` | Permit submit_request when there is no refund_amount (complaints, inquiries) |

### Get your Gateway ARN

Cedar policies reference the Gateway by its full ARN. Get it first:

```bash
aws bedrock-agentcore-control get-gateway \
  --gateway-identifier <your-gateway-id> \
  --region us-east-1 \
  --query 'gatewayArn' --output text
```

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

### Policy 2 — Allow refund requests within the $500 limit

We express the refund cap as a **conditional permit**: `submit_request` is
allowed only when the refund amount is within limit. Cedar's default-deny then
blocks anything over $500 automatically.

**Via AWS Console**

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

### Policy 3 — Allow non-refund requests (complaints, inquiries)

Policy 2 only permits `submit_request` when a `refund_amount` is present.
Requests without one (complaints, inquiries, exchanges) need their own permit,
otherwise they'd be denied by default:

**Via AWS Console**

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

Together, Policies 2 and 3 permit `submit_request` when there is **no** refund
amount **or** the refund amount is **≤ 500**. A refund over $500 matches
neither permit, so Cedar's default-deny blocks it at the Gateway.

### Via CLI (Optional)

> **Note**: The Policy commands (`create-policy-engine`, `create-policy`, etc.)
> require a recent AWS CLI build. If `aws bedrock-agentcore-control create-policy`
> reports an invalid choice, your CLI predates the Policy API — use the console
> flow above instead.

<details>
<summary>Add all policies via CLI</summary>

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

---

## Step 4 — Cedar Policy Reference Files

The three Cedar policies are also included in the repo under
`aria-agent/policies/` for reference:

- `allow_read_tools.cedar`
- `limit_refund_amount.cedar`
- `allow_non_refund_requests.cedar`

These are reference copies — the policies are created and enforced in the
policy engine (Step 3), not loaded from these files at runtime. Use them to
review the exact Cedar or to recreate the policies later. Each contains a
`<GATEWAY_ARN>` placeholder to substitute with your gateway ARN.

---

## Step 5 — Test the Policies

### Test 1 — Normal return request (should succeed)

Log in as `alice@example.com` and ask:
```
I'd like to return order ORD-1001. It was the wrong size. Refund is about $100.
```

Aria initiates the return normally — the refund amount is under $500, so the
`limit_refund_amount` permit applies.

### Test 2 — Large refund attempt (should be blocked)

Alice has two high-value orders for this test — `ORD-1004` ($749.98) and
`ORD-1005` ($1,299.99). Ask Aria:
```
I want to return order ORD-1005, the monitor. Process the full $1299.99 refund.
```

The Gateway evaluates the Cedar policies — the refund exceeds $500 so it
matches neither `limit_refund_amount` nor `allow_non_refund_requests`, and
Cedar's default-deny blocks the tool call before it reaches the API. Aria
relays the denial — something like:
```
I'm unable to process a refund of that amount automatically. Refunds over
$500 require manual review by our team. I can escalate this for you.
```

### Test 3 — Verify enforcement in CloudWatch

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

> If no gateway log group exists, enable log delivery on the gateway (or check
> the gateway's Monitoring tab in the console). With **Exception level debug**
> enabled on the gateway, denied requests also surface a clear message in the
> tool response returned to the agent.

---

## How Cedar Evaluation Works

```
Tool call arrives at Gateway
        │
        ▼
Evaluate all forbid rules
        │
  Any forbid matches? ──YES──► DENY (blocked)
        │
        NO
        ▼
Evaluate all permit rules
        │
  Any permit matches? ──YES──► ALLOW (forwarded to the target)
        │
        NO
        ▼
     DENY (implicit deny — no matching permit)
```

The refund cap relies on this **default-deny**: a >$500 refund matches none of
our permits, so it is denied without needing an explicit `forbid`. The two
`submit_request` permits (`limit_refund_amount` and `allow_non_refund_requests`)
together cover every legitimate case — anything they don't cover is blocked.

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

## Next Step

Proceed to [Module 09 — Observability](../module-09-observability/README.md)
where you will add CloudWatch dashboards, traces, and metrics to get full
visibility into Aria's behaviour in production.
