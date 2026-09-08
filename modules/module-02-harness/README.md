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
2. **Trusted entity**: AWS service → **bedrock-agentcore.amazonaws.com**
3. Attach these managed policies:
   - `AmazonBedrockFullAccess`
   - `CloudWatchLogsFullAccess`
4. Role name: `AriaHarnessExecutionRole`
5. Click **Create role**
6. Note down the **Role ARN** — you will need it in the next step

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
  --role-name AriaHarnessExecutionRole \
  --assume-role-policy-document file://trust-policy.json

# Attach policies
aws iam attach-role-policy \
  --role-name AriaHarnessExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess

aws iam attach-role-policy \
  --role-name AriaHarnessExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess

# Get Role ARN
aws iam get-role \
  --role-name AriaHarnessExecutionRole \
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
3. Configure:
   - **Harness name**: `aria`
   - **Execution role**: `AriaHarnessExecutionRole` (select from dropdown)
   - **Model provider**: Amazon Bedrock
   - **Model**: Claude Sonnet 4 (default)
   - **System prompt**: paste the system prompt from the section below
4. Click **Create harness**
5. Wait until status shows **READY** (takes ~1 minute)
6. Note down the **Harness ARN**

### Via CLI (Optional)

```bash
# Replace <YOUR_ACCOUNT_ID> with your AWS account ID
aws bedrock-agentcore-control create-harness \
  --harness-name "aria" \
  --execution-role-arn "arn:aws:iam::<YOUR_ACCOUNT_ID>:role/AriaHarnessExecutionRole" \
  --region us-east-1

# Poll until status is READY
aws bedrock-agentcore-control get-harness \
  --harness-id "aria" \
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
5. Aria should respond with the return policy from the system prompt

Try a few more:
- `How long does standard shipping take?`
- `What payment methods do you accept?`
- `My name is Sarah. Can you help me?`

---

## Step 4 — Invoke via Python (invoke_aria.py)

A simple Python script to invoke Aria from the command line. This is the foundation the Streamlit UI will build on.

```bash
# From the repo root, with venv activated
python modules/module-02-harness/invoke_aria.py
```

See [invoke_aria.py](invoke_aria.py) for the full script.

---

## Step 5 — Run the Streamlit Chat UI

```bash
# Set your Harness ARN as an environment variable
export ARIA_HARNESS_ARN="arn:aws:bedrock-agentcore:us-east-1:<YOUR_ACCOUNT_ID>:harness/aria-XyZ123"
export AWS_REGION="us-east-1"

# Run the UI
streamlit run streamlit-ui/app.py
```

Open your browser at `http://localhost:8501` and chat with Aria.

---

## Step 6 — Local Development with agentcore dev (Optional)

The AgentCore CLI provides a local dev server with a built-in browser-based agent inspector — useful for iterating on the system prompt quickly:

```bash
# From the aria-agent directory
cd aria-agent
agentcore dev
```

This opens the agent inspector in your browser where you can:
- Chat with Aria
- Inspect traces of every model call
- Override harness settings on the fly without redeploying

---

## What You Learned

- What the AgentCore Harness is and how it differs from writing your own agent loop
- How to create an IAM execution role for the Harness
- How to create a Harness via console and CLI
- How to write an effective system prompt
- How to invoke the Harness via Python SDK (streaming responses)
- How to connect a Streamlit chat UI to the Harness

---

## Next Step

In [Module 03 — Runtime](../module-03-runtime/README.md) you will learn about the AgentCore Runtime that powers the Harness under the hood — microVM isolation, sessions, versioning, and rollback.
