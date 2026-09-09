# Module 06 — Memory: Stateful Agents

In this module you will add persistent memory to Aria so she remembers
customers across sessions. After this module, Aria can greet returning
customers by name, recall their past issues, and personalise responses
using facts she has learned over time.

---

## What You Will Build

```
aria-agent/
├── agent.py           # Updated — creates agent per invocation with memory
├── config.py          # Updated — loads /aria/memory_id and /aria/memory_strategy_id from SSM
├── Dockerfile         # Updated — adds memory/ to the image
└── memory/
    └── session.py     # NEW — factory that creates the memory session manager
```

---

<details>
<summary>How This Differs from Module 05</summary>

| | Module 05 — Gateway | Module 06 — Memory |
|---|---|---|
| Conversation state | Stateless — each call is independent | Stateful — facts persisted to Memory |
| Customer recognition | Customer always provides their ID | Aria recalls returning customers |
| Cross-session recall | None | Past issues, preferences, summaries |
| Agent lifecycle | One agent singleton shared across calls | New agent per invocation (scoped to actor) |

</details>

---

<details>
<summary>How AgentCore Memory Works</summary>

AgentCore Memory is a managed store with two layers:

**Short-term (session) memory** — Strands writes every conversation turn
automatically. Within a single session Aria remembers everything said earlier.

**Long-term memory** — At the end of a session AgentCore extracts facts and
summaries and writes them to namespaced paths. On the next session those
facts are retrieved and injected into the context before Aria responds.

AgentCore writes extracted memories to namespace paths defined on the Memory
resource itself. The default namespace template for each built-in strategy is:

| Strategy | Default namespace template |
|---|---|
| Semantic Memory | `/strategy/{memoryStrategyId}/actors/{actorId}/` |
| Summarization | `/strategy/{memoryStrategyId}/actors/{actorId}/` |
| User Preferences | `/strategy/{memoryStrategyId}/actors/{actorId}/` |

The session manager retrieves memories across all strategies automatically —
no namespace paths need to be hardcoded in application code.

</details>

---

## Step 1 — Create the AgentCore Memory Resource

### Via AWS Console

1. Go to **AWS Console → Amazon Bedrock → AgentCore → Memory**
2. Click **Create memory**
3. Fill in the basic details:
   - **Name**: `aria-memory`
   - **Description**: `Persistent memory for Aria customer support agent`

4. Scroll to **Long-term memory extraction strategies — optional**

   <details>
   <summary>About strategy types</summary>

   You will see three strategy types:

   | Strategy type | When to use |
   |---|---|
   | **Built-in strategies** | AWS manages extraction and consolidation — recommended for most use cases |
   | **Built-in strategy with override** | Start with a built-in strategy but supply your own system prompt |
   | **Self-managed strategy** | You bring your own extraction logic entirely |

   For Aria, use **Built-in strategies**.

   </details>

5. Click **Add strategy** under Built-in strategies.

   <details>
   <summary>About built-in strategy types</summary>

   | Built-in strategy | What it extracts |
   |---|---|
   | **Semantic Memory** | Key facts and entities from the conversation (e.g. customer preferences, order numbers, issues raised) |
   | **Summarization** | A concise summary of each session |
   | **User Preferences** | Explicit preferences stated by the user (e.g. "I prefer express shipping") |
   | **Episodes** | Episodic records of specific events or interactions |

   </details>

   Select **Semantic Memory**. This captures customer facts like name, preferences,
   and past issues as discrete records that can be retrieved in future sessions.

   Leave the **Namespace template** as the default:
   ```
   /strategy/{memoryStrategyId}/actors/{actorId}/
   ```

6. Leave **Namespace keys** empty (no custom variables needed for Aria).

7. Click **Create**

8. Wait for the status to reach **Active** (takes about 1–2 minutes)

9. Note the **Memory ID** — it looks like `mem-XXXXXXXXXX`

### Via CLI

```bash
aws bedrock-agentcore-control create-memory \
  --name aria-memory \
  --description "Persistent memory for Aria customer support agent" \
  --memory-strategies '[{"semanticMemoryStrategy": {"name": "aria-semantic"}}]' \
  --region us-east-1
```

Save the Memory ID:

```bash
export MEMORY_ID=mem-XXXXXXXXXX
```

---

## Step 2 — Grant the Execution Role Permission to Use Memory

### Via AWS Console

1. Go to **IAM → Roles → AriaHarnessExecutionRole**
2. Click **Add permissions → Create inline policy**
3. Switch to the **JSON** editor and paste:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AgentCoreMemory",
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:RetrieveMemoryRecords",
        "bedrock-agentcore:CreateMemoryRecord",
        "bedrock-agentcore:UpdateMemoryRecord",
        "bedrock-agentcore:DeleteMemoryRecord",
        "bedrock-agentcore:IngestConversationEvents"
      ],
      "Resource": "arn:aws:bedrock-agentcore:us-east-1:<ACCOUNT_ID>:memory/<MEMORY_ID>"
    }
  ]
}
```

Replace `<ACCOUNT_ID>` and `<MEMORY_ID>` with your values.

4. Name the policy `AriaMemoryAccess` and click **Create policy**

### Via CLI

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1

aws iam put-role-policy \
  --role-name AriaHarnessExecutionRole \
  --policy-name AriaMemoryAccess \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Sid\": \"AgentCoreMemory\",
      \"Effect\": \"Allow\",
      \"Action\": [
        \"bedrock-agentcore:RetrieveMemoryRecords\",
        \"bedrock-agentcore:CreateMemoryRecord\",
        \"bedrock-agentcore:UpdateMemoryRecord\",
        \"bedrock-agentcore:DeleteMemoryRecord\",
        \"bedrock-agentcore:IngestConversationEvents\"
      ],
      \"Resource\": \"arn:aws:bedrock-agentcore:${AWS_REGION}:${AWS_ACCOUNT_ID}:memory/${MEMORY_ID}\"
    }]
  }"
```

---

## Step 3 — Add memory_id and memory_strategy_id to SSM

Get your Strategy ID:

```bash
aws bedrock-agentcore-control get-memory \
  --memory-id <YOUR_MEMORY_ID> \
  --region us-east-1 \
  --query "memory.strategies[*].{id:strategyId,type:type}" \
  --output table
```

<details>
<summary>Where to find the Strategy ID in the Console</summary>

The **Strategy ID** is shown on the Memory resource detail page under
**Long-term memory extraction strategies**. It looks like
`semantic_builtin_XXXXX-XXXXXXXXXX`.

</details>

### Via AWS Console

Create two parameters in **Systems Manager → Parameter Store**:

| Name | Value |
|---|---|
| `/aria/memory_id` | your Memory ID (e.g. `aria_memory-XXXXXXXXXX`) |
| `/aria/memory_strategy_id` | your Strategy ID (e.g. `semantic_builtin_XXXXX-XXXXXXXXXX`) |

### Via CLI

```bash
export MEMORY_ID=<your-memory-id>
export MEMORY_STRATEGY_ID=<your-strategy-id>
export KNOWLEDGE_BASE_ID=<your-existing-kb-id>
export API_BASE_URL=<your-existing-api-url>

MEMORY_ID=$MEMORY_ID \
MEMORY_STRATEGY_ID=$MEMORY_STRATEGY_ID \
API_BASE_URL=$API_BASE_URL \
KNOWLEDGE_BASE_ID=$KNOWLEDGE_BASE_ID \
bash aria-agent/scripts/put_ssm_params.sh
```

---

## Step 4 — Update the Agent

```bash
cp modules/module-06-memory/agent.py aria-agent/agent.py
cp modules/module-06-memory/config.py aria-agent/config.py
cp modules/module-06-memory/Dockerfile aria-agent/Dockerfile
cp -r modules/module-06-memory/memory aria-agent/
```

Verify the files exist:

```bash
ls aria-agent/memory/
# session.py
```

<details>
<summary>What changed in agent.py</summary>

The key difference from Module 05 is that the agent is now **created per
invocation** instead of being a module-level singleton:

```python
# Module 05 — one agent shared across all invocations (stateless)
agent = Agent(model=cfg.model_id, system_prompt=SYSTEM_PROMPT, tools=TOOLS)

# Module 06 — new agent per invocation, scoped to customer + session
agent = Agent(
    model=cfg.model_id,
    system_prompt=SYSTEM_PROMPT,
    tools=TOOLS,
    session_manager=get_memory_session_manager(
        session_id=session_id,
        actor_id=customer_id,
    ),
)
```

This is required because memory is scoped to an `actor_id` (customer). Using a
singleton would mix memories across different customers.

</details>

<details>
<summary>What memory/session.py does</summary>

`get_memory_session_manager` returns an `AgentCoreMemorySessionManager`
configured with a `retrieval_config` that points to the correct namespace:

```python
retrieval_config = {
    "/strategies/{memoryStrategyId}/actors/{actorId}/": RetrievalConfig(
        top_k=5,
        relevance_score=0.4,
        strategy_id=cfg.memory_strategy_id,
    ),
}
```

The namespace template uses `{actorId}` and `{memoryStrategyId}` as
placeholders. The SDK resolves them at retrieval time — the final path becomes:
```
/strategies/semantic_builtin_XXXXX-XXXXXXXXXX/actors/C001/
```

Before each response, Strands retrieves the top-5 most relevant facts for
this customer and prepends them to the context. After the session ends,
AgentCore extracts new facts and writes them back to this namespace.

</details>

---

## Step 5 — Update the Streamlit UI

```bash
cp modules/module-06-memory/app.py streamlit-ui/app.py
```

<details>
<summary>What changed from Module 04</summary>

- Sidebar now has a Customer ID text input (e.g. `C001`)
- Every message sent to the agent includes `customer_id` in the payload
- Shows a confirmation when a customer ID is set, or an info message when anonymous
- In Module 07 (Identity) this manual input will be replaced by Cognito login

</details>

---

## Step 6 — Rebuild and Deploy

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1
export ECR_REPO=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aria-agent

# Authenticate with ECR
aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS --password-stdin \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build, tag, and push
cd aria-agent
docker build --platform linux/arm64 -t aria-agent .
docker tag aria-agent:latest $ECR_REPO:latest
docker push $ECR_REPO:latest
cd ..

# Update the runtime to use the new image
aws bedrock-agentcore control update-agent-runtime \
  --agent-runtime-id <YOUR_RUNTIME_ID> \
  --agent-runtime-artifact "{\"containerConfiguration\":{\"containerUri\":\"$ECR_REPO:latest\"}}" \
  --role-arn "arn:aws:iam::$AWS_ACCOUNT_ID:role/AriaHarnessExecutionRole" \
  --network-configuration '{"networkMode":"PUBLIC"}' \
  --description "Module 06 — Memory" \
  --region us-east-1
```

Wait for the runtime status to return to **Ready** before testing.

---

## Step 7 — Test

### First session — introduce yourself

Set Customer ID to `C001` in the Streamlit sidebar and send:

```
My name is Alice and my customer ID is C001.
I prefer express shipping for all my orders.
What is your return policy?
```

### Second session — verify memory

Click **🔄 New Session** in the sidebar (keeps Customer ID, resets session) and send:

```
Hi, my customer ID is C001.
```

Aria should greet Alice by name and recall her express shipping preference
without being told again.

### Inspect what AgentCore stored in memory

After the first session completes, AgentCore extracts facts asynchronously and
writes them to the memory namespace for C001. You can inspect exactly what was
stored using the CLI:

```bash
export MEMORY_ID=$(aws ssm get-parameter --name /aria/memory_id \
  --query Parameter.Value --output text --region us-east-1)
export STRATEGY_ID=$(aws ssm get-parameter --name /aria/memory_strategy_id \
  --query Parameter.Value --output text --region us-east-1)
export CUSTOMER_ID=C001

aws bedrock-agentcore list-memory-records \
  --memory-id $MEMORY_ID \
  --namespace "/strategies/${STRATEGY_ID}/actors/${CUSTOMER_ID}/" \
  --region us-east-1 \
  --query "memoryRecordSummaries[*].content.text" \
  --output table
```

You should see extracted facts like:

```
-------------------------------------------------------------------------------------
|                              ListMemoryRecords                                    |
+-----------------------------------------------------------------------------------+
|  The user's name is Alice Johnson.                                                |
|  The user's customer ID is C001.                                                  |
|  The user prefers express shipping for all orders.                                |
|  The user placed order ORD-1001 on 2026-08-25 ...                                 |
+-----------------------------------------------------------------------------------+
```

These are exactly the records Aria retrieves and injects into context at the
start of the next session. If the table is empty, memory consolidation is still
in progress — wait a minute and re-run.

<details>
<summary>Testing with the invoke script</summary>

```bash
# Session 1 — establish facts
python modules/module-02-harness/invoke_aria.py \
  --runtime-id <YOUR_RUNTIME_ID> \
  --payload '{"prompt": "My name is Alice and I prefer express shipping. Customer ID: C001.", "customer_id": "C001", "session_id": "test-session-1"}'

# Session 2 — test recall (different session_id, same customer_id)
python modules/module-02-harness/invoke_aria.py \
  --runtime-id <YOUR_RUNTIME_ID> \
  --payload '{"prompt": "Hi! My customer ID is C001. Do you know my name?", "customer_id": "C001", "session_id": "test-session-2"}'
```

> Memory consolidation (fact extraction) happens asynchronously after session
> end. Allow a minute or two between sessions when testing.

</details>

---

<details>
<summary>Troubleshooting</summary>

**Aria does not remember facts from the previous session**

- Memory consolidation is async — wait 1–2 minutes after session end before
  starting a new session.
- Verify both `/aria/memory_id` and `/aria/memory_strategy_id` SSM parameters
  are set correctly.
- Check CloudWatch logs for `Initialising memory session` to confirm both
  values are loaded. If `memory_strategy_id` is missing the log will show a
  warning and memory retrieval will be skipped.
- Check CloudWatch logs for `Retrieved X customer context items` — if this
  line is absent, retrieval ran but found nothing (memory consolidation may
  still be in progress).

**`AgentCoreMemorySessionManager` import error**

- Ensure `bedrock-agentcore>=1.22.0` is in `requirements.txt` and the
  image was rebuilt after the update.

**AccessDeniedException on memory calls**

- Confirm the `AriaMemoryAccess` inline policy is attached to
  `AriaHarnessExecutionRole` and the Memory ID in the policy ARN matches
  your actual Memory ID.

</details>

---

<details>
<summary>What You Learned</summary>

- How AgentCore Memory separates short-term (session) from long-term (cross-session) memory
- Why the agent must be created per invocation when memory is scoped to a customer
- How `actor_id` namespaces memory by customer so data is never mixed
- How Strands automatically reads from and writes to memory via the session manager
- How to degrade gracefully when memory is not configured

</details>

---

## Next Step

Proceed to [Module 07 — Identity](../module-07-identity/README.md) where you
will add Cognito authentication so `customer_id` comes from a verified JWT
token instead of the request payload.
