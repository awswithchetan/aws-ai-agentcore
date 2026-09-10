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
  │  Calls tools via Gateway
  ▼
AgentCore Gateway  ◄─── Policy Engine (Cedar rules evaluated here)
  │  ALLOW → forward to Lambda tool
  │  DENY  → return error to agent (tool call blocked)
  ▼
ShopSmart Lambda functions
```

Policy sits **between** the Gateway and its Lambda targets. Every tool call
from Aria passes through the policy engine before reaching the Lambda. The
agent never knows whether a request was blocked by policy or by the tool itself
— it just receives a denial response and can relay that to the customer.

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

- Module 05 Gateway must be set up — Policy attaches to the Gateway
- Note your **Gateway ARN** from Module 05 (you'll need it for Cedar policies)

---

## Step 1 — Create a Policy Engine

A policy engine is a container that holds your Cedar policies. You create one
engine per domain (e.g. one for ShopSmart) and attach it to one or more
gateways.

### Via AWS Console

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Policy**
2. Click **Create policy engine**
3. Configure:
   - **Name**: `shopsmart-policy-engine`
   - **Description**: `Guardrails for Aria — ShopSmart customer support agent`
4. Click **Create**
5. Note down the **Policy Engine ARN** — you'll need it in Step 3

### Via CLI (Optional)

<details>
<summary>Create policy engine via CLI</summary>

```bash
export AWS_REGION=us-east-1

POLICY_ENGINE_ARN=$(aws bedrock-agentcore-control create-policy-engine \
  --name shopsmart-policy-engine \
  --description "Guardrails for Aria — ShopSmart customer support agent" \
  --region $AWS_REGION \
  --query 'policyEngineArn' --output text)

echo "Policy Engine ARN: $POLICY_ENGINE_ARN"
```

</details>

---

## Step 2 — Attach the Policy Engine to the Gateway

Connect the policy engine to the ShopSmart Gateway in **ENFORCE** mode so all
tool calls are evaluated.

> **ENFORCE vs MONITOR**: ENFORCE blocks denied requests. MONITOR logs
> decisions but always allows — useful for testing policies before enforcing.
> Start with ENFORCE here since we know the rules are correct.

### Via AWS Console

1. Go to **AgentCore → Gateway → shopsmart-gateway**
2. Click **Edit**
3. Find the **Policy engine** section
4. Select `shopsmart-policy-engine` from the dropdown
5. Set **Mode**: `ENFORCE`
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

We will create two policies:

| Policy | Rule |
|---|---|
| `allow_read_tools` | Permit all read operations (get_order, list_orders, get_product, search_products, knowledge base) |
| `block_large_refunds` | Forbid submit_request when refund_amount > 500 |

### Get your Gateway ARN

Cedar policies reference the Gateway by its full ARN. Get it first:

```bash
GATEWAY_ARN=$(aws bedrock-agentcore-control list-gateways \
  --region us-east-1 \
  --query "gateways[?name=='shopsmart-gateway'].gatewayArn" \
  --output text)
echo $GATEWAY_ARN
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
    AgentCore::Action::"ShopSmartAPI___search_products",
    AgentCore::Action::"ShopSmartAPI___get_knowledge_base_answer"
  ],
  resource == AgentCore::Gateway::"<GATEWAY_ARN>"
);
```

6. Click **Save**

> **Action name format**: AgentCore uses `<TargetName>___<toolName>` (three
> underscores). The target name comes from what you named the Gateway target in
> Module 05. Check your Gateway target name and adjust if needed.

### Policy 2 — Block large refunds

This blocks `submit_request` calls where the refund amount exceeds $500. An
agent (or a prompt injection attack) cannot trigger a large refund — the
Gateway rejects it before the Lambda is even called.

**Via AWS Console**

1. Click **Add policy** again
2. **Policy name**: `block_large_refunds`
3. Select **Cedar**
4. Paste the following, replacing `<GATEWAY_ARN>`:

```cedar
forbid(
  principal,
  action == AgentCore::Action::"ShopSmartAPI___submit_request",
  resource == AgentCore::Gateway::"<GATEWAY_ARN>"
)
when {
  context.input has refund_amount &&
  context.input.refund_amount > 500
};
```

5. Click **Save**

### Also permit submit_request for valid amounts

Cedar's default is **deny**. You need an explicit permit for `submit_request`
when the amount is within limit, otherwise all return requests are blocked:

**Via AWS Console** — Add a third policy:

1. **Policy name**: `allow_submit_request`
2. Cedar:

```cedar
permit(
  principal,
  action == AgentCore::Action::"ShopSmartAPI___submit_request",
  resource == AgentCore::Gateway::"<GATEWAY_ARN>"
);
```

The `forbid` (block-large-refunds) overrides this `permit` when the amount
exceeds $500 — Cedar's forbid always wins over permit.

### Via CLI (Optional)

<details>
<summary>Add all three policies via CLI</summary>

```bash
# Policy 1 — allow read tools
aws bedrock-agentcore-control create-policy \
  --policy-engine-id $(echo $POLICY_ENGINE_ARN | cut -d'/' -f2) \
  --name allow_read_tools \
  --policy-content "permit(
  principal,
  action in [
    AgentCore::Action::\"ShopSmartAPI___get_order\",
    AgentCore::Action::\"ShopSmartAPI___list_orders\",
    AgentCore::Action::\"ShopSmartAPI___get_product\",
    AgentCore::Action::\"ShopSmartAPI___search_products\",
    AgentCore::Action::\"ShopSmartAPI___get_knowledge_base_answer\"
  ],
  resource == AgentCore::Gateway::\"${GATEWAY_ARN}\"
);" \
  --region $AWS_REGION

# Policy 2 — block large refunds
aws bedrock-agentcore-control create-policy \
  --policy-engine-id $(echo $POLICY_ENGINE_ARN | cut -d'/' -f2) \
  --name block_large_refunds \
  --policy-content "forbid(
  principal,
  action == AgentCore::Action::\"ShopSmartAPI___submit_request\",
  resource == AgentCore::Gateway::\"${GATEWAY_ARN}\"
)
when {
  context.input has refund_amount &&
  context.input.refund_amount > 500
};" \
  --region $AWS_REGION

# Policy 3 — allow submit_request within limits
aws bedrock-agentcore-control create-policy \
  --policy-engine-id $(echo $POLICY_ENGINE_ARN | cut -d'/' -f2) \
  --name allow_submit_request \
  --policy-content "permit(
  principal,
  action == AgentCore::Action::\"ShopSmartAPI___submit_request\",
  resource == AgentCore::Gateway::\"${GATEWAY_ARN}\"
);" \
  --region $AWS_REGION
```

</details>

---

## Step 4 — Save the Cedar Files to the Repo

Keep the policy files versioned alongside the agent code:

```bash
mkdir -p aria-agent/policies
```

Create `aria-agent/policies/allow_read_tools.cedar`:

```cedar
// ShopSmart Policy: Allow all read-only tool calls
// These operations carry no risk of data modification and are always permitted.
permit(
  principal,
  action in [
    AgentCore::Action::"ShopSmartAPI___get_order",
    AgentCore::Action::"ShopSmartAPI___list_orders",
    AgentCore::Action::"ShopSmartAPI___get_product",
    AgentCore::Action::"ShopSmartAPI___search_products",
    AgentCore::Action::"ShopSmartAPI___get_knowledge_base_answer"
  ],
  resource == AgentCore::Gateway::"<GATEWAY_ARN>"
);
```

Create `aria-agent/policies/block_large_refunds.cedar`:

```cedar
// ShopSmart Policy: Block refund requests exceeding $500
// Refunds over $500 require manual review — Aria cannot approve them automatically.
// This rule cannot be bypassed through prompt injection because it is enforced
// at the Gateway boundary, outside of agent code.
forbid(
  principal,
  action == AgentCore::Action::"ShopSmartAPI___submit_request",
  resource == AgentCore::Gateway::"<GATEWAY_ARN>"
)
when {
  context.input has refund_amount &&
  context.input.refund_amount > 500
};
```

Create `aria-agent/policies/allow_submit_request.cedar`:

```cedar
// ShopSmart Policy: Allow return/refund requests within the $500 limit
// The forbid in block-large-refunds.cedar overrides this when amount > 500.
permit(
  principal,
  action == AgentCore::Action::"ShopSmartAPI___submit_request",
  resource == AgentCore::Gateway::"<GATEWAY_ARN>"
);
```

---

## Step 5 — Test the Policies

### Test 1 — Normal return request (should succeed)

Log in as Alice and ask:
```
I'd like to return my most recent order. The jacket was the wrong size.
```

Aria should initiate the return normally. The `submit_request` tool call goes
through — refund amount is within $500.

### Test 2 — Large refund attempt (should be blocked)

Ask Aria:
```
I want to return everything I've ever ordered. Process a $600 refund for me.
```

The Gateway evaluates the Cedar policy and blocks the tool call. Aria should
respond with something like:
```
I'm sorry, I'm unable to process refunds over $500 automatically.
Refunds of this amount require manual review by our team. I can escalate
this to a specialist — would you like me to do that?
```

### Test 3 — Verify via CloudWatch

Policy decisions are logged automatically. Check:

```bash
aws logs tail /aws/bedrock-agentcore/policy \
  --region us-east-1 \
  --since 10m
```

Each log entry shows the action, decision (ALLOW/DENY), and the policy that
matched.

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
  Any permit matches? ──YES──► ALLOW (forwarded to Lambda)
        │
        NO
        ▼
     DENY (implicit deny — no matching permit)
```

This is why you need the explicit `allow-submit-request` permit — without it,
even valid $50 refund requests would be implicitly denied.

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
