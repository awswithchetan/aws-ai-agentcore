# Module 02 — Your First Agent with Harness

In this module you will create **Aria** — ShopSmart's AI customer support agent — using the AgentCore managed Harness. By the end, Aria will be running in the cloud, answering customer questions via a Streamlit chat UI.

The Harness is the fastest path to a running agent. You define three things — model, system prompt, and instructions — and AgentCore handles all orchestration, compute, memory, networking, and observability underneath.

---

## What You Will Build

A basic version of Aria that can:
- Greet customers by name
- Answer ShopSmart FAQ questions (return policy, shipping, store hours)
- Handle follow-up questions within the same conversation session

No tools or database connections yet — that comes in Module 04 (Gateway). This module focuses purely on getting Aria alive and responding.

---

## Step 1 — Create the IAM Execution Role

The Harness needs an IAM role to invoke Bedrock models and write logs. Create this once.

### Via AWS Console

1. Go to **AWS Console → IAM → Roles → Create role**
2. **Trusted entity type**: AWS service
3. **Use case**: scroll down and select **Amazon Bedrock AgentCore** — this automatically configures the correct trust policy
4. Click **Next**
5. Attach these managed policies:
   - `AmazonBedrockFullAccess`
   - `BedrockAgentCoreFullAccess`
   - `CloudWatchLogsFullAccess`
6. Click **Next**
7. **Role name**: `AriaAgentExecutionRole`
8. Click **Create role**
9. Note down the **Role ARN**

### Via CLI (Optional)

```bash
# Create trust policy
cat > trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Service": "bedrock-agentcore.amazonaws.com"
    },
    "Action": "sts:AssumeRole"
  }]
}
EOF

# Create role
aws iam create-role \
  --role-name AriaAgentExecutionRole \
  --assume-role-policy-document file://trust-policy.json

# Attach policies
aws iam attach-role-policy \
  --role-name AriaAgentExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess

aws iam attach-role-policy \
  --role-name AriaAgentExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess

# Get Role ARN
aws iam get-role \
  --role-name AriaAgentExecutionRole \
  --query "Role.Arn" \
  --output text

# Clean up
rm trust-policy.json
```

---

## Step 2 — Create the Harness

### Via AWS Console

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Harnesses**
2. Click **Create harness**
3. Choose **Advanced create harness**

   <details>
   <summary>Quick create vs Advanced create</summary>

   - **Quick create** — minimal setup, AWS picks sensible defaults for everything. Good for a quick test but gives you no control.
   - **Advanced create** — lets you configure model, system prompt, execution role, memory, tools, identity, environment, and more. We use this throughout the course.

   </details>

4. Configure:
   - **Harness name**: `aria-harness`
   - **Model**: Claude Sonnet 4.6 (default — keep as is)
   - **System prompt**: paste the system prompt from the section below
   - **Execution role**: select `AriaAgentExecutionRole`

5. Leave all other settings as default
6. Click **Create harness**
7. Wait until status shows **READY** (takes ~1 minute)
8. Note down the **Harness ARN**

### Via CLI (Optional)

```bash
# Replace <YOUR_ACCOUNT_ID> with your AWS account ID
aws bedrock-agentcore-control create-harness \
  --harness-name "aria-harness" \
  --execution-role-arn "arn:aws:iam::<YOUR_ACCOUNT_ID>:role/AriaAgentExecutionRole" \
  --region us-east-1

# Poll until status is READY
aws bedrock-agentcore-control get-harness \
  --harness-id "aria-harness" \
  --region us-east-1
```

---

## Aria's System Prompt (Module 02 Version)

This is Aria's initial system prompt — no tools yet, FAQ knowledge only. It will evolve as we add capabilities in later modules.

```
You are Aria, the AI customer support agent for ShopSmart — a friendly online retail store.

Your role is to help customers with their shopping experience. Be warm, helpful, and concise.

## What you can help with (in this version):
- Answer questions about ShopSmart's policies and services
- Greet returning customers by name when they introduce themselves
- Handle follow-up questions in the same conversation

## ShopSmart FAQ Knowledge:

**Return Policy:**
- Items can be returned within 30 days of delivery
- Items must be in original condition with tags attached
- Return shipping is free for defective items; $5.99 for change-of-mind returns
- Refunds are processed within 3-5 business days after the return is received

**Shipping:**
- Standard shipping: 5-7 business days, free on orders over $50
- Express shipping: 2-3 business days, $9.99
- Same-day delivery: available in select cities, $14.99
- International shipping: available to 30 countries, rates vary by destination

**Store Hours (Customer Support):**
- Live support: Monday–Friday, 9 AM–6 PM EST
- Email support: 24/7, responses within 4 hours
- AI support (that's you!): 24/7

**Payment Methods:**
- Visa, Mastercard, American Express, Discover
- PayPal, Apple Pay, Google Pay
- ShopSmart Gift Cards

## Tone guidelines:
- Be friendly but professional
- Keep responses concise — 2-3 sentences for simple questions
- If you don't know something, say so honestly and suggest the customer contact live support
- Never make up information about specific orders, products, or account details
```

---

## Step 3 — Test via AWS Console

Before connecting the Streamlit UI, test Aria directly in the console:

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Harnesses**
2. Select your `aria` harness
3. Click the **Test** tab
4. Type a message: `Hi, what is your return policy?`

Try a few more:
- `How long does standard shipping take?`
- `What payment methods do you accept?`
- `My name is Sarah. Can you help me?`

---

## Step 4 — Run the Streamlit Chat UI

```bash
# Use the base harness ARN — NOT the endpoint ARN
# Correct:   arn:aws:bedrock-agentcore:us-east-1:<account>:harness/aria-XXXXXXXX
# Incorrect: arn:aws:bedrock-agentcore:us-east-1:<account>:harness/aria-XXXXXXXX/harness-endpoint/DEFAULT

export ARIA_HARNESS_ARN="arn:aws:bedrock-agentcore:us-east-1:<YOUR_ACCOUNT_ID>:harness/aria-harness-XXXXXXXX"
export AWS_REGION="us-east-1"

streamlit run streamlit-ui/app.py
```

Open your browser at `http://localhost:8501` and chat with Aria.

> The repo also includes [`invoke_aria.py`](invoke_aria.py) — a terminal-based script to invoke Aria directly via boto3 without the UI.

---

<details>
<summary>What You Learned</summary>

- What the AgentCore Harness is and how it differs from writing your own agent loop
- How to create an IAM execution role for the Harness
- How to create a Harness via console and CLI
- How to write an effective system prompt
- How to invoke the Harness via Python SDK (streaming responses)
- How to connect a Streamlit chat UI to the Harness

</details>

---

## Cleanup

The `aria-harness` agent has served its purpose. Delete it before moving to Module 03 to avoid unnecessary charges.

### Via AWS Console

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Harnesses**
2. Select `aria-harness`
3. Click **Actions → Delete**
4. Confirm deletion

### Via CLI (Optional)

```bash
aws bedrock-agentcore-control delete-harness \
  --harness-id "aria-harness" \
  --region us-east-1
```

> The IAM role `AriaAgentExecutionRole` can be kept — we will reuse it in Module 04 for the Runtime agent.

---

## Next Step

Proceed to [Module 03 — Knowledge Base](../module-03-knowledge-base/README.md) where you will create the ShopSmart Knowledge Base, upload the FAQ documents, and connect it to Aria so she retrieves accurate information dynamically instead of relying on a hardcoded system prompt.
