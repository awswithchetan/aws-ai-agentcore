# Module 02 — Your First Agent

In this module you build the first version of **Aria**, ShopSmart's AI customer
support agent, and run it entirely on your own machine. No AWS infrastructure to
provision, no containers, no deployment — just a Python file you can read, run,
and change in minutes.

The goal is to see clearly what an AI agent actually *is* before we start
externalizing its pieces into managed Amazon Bedrock AgentCore capabilities.
An agent is three things wired together in a loop:

1. **A model** — the reasoning engine (Claude, via Amazon Bedrock).
2. **A system prompt** — Aria's persona, rules, and knowledge.
3. **Tools** — functions the model can call to fetch real data or take actions.

That's it. Everything else in this course — Runtime, Gateway, Knowledge Base,
Memory, Identity, Policy, Browser — is about taking these three pieces and
making them production-grade.

---

## What You Will Build

A single self-contained agent file:

```
modules/module-02-first-agent/
├── agent.py          # Aria: model + system prompt + tools + a local chat loop
└── requirements.txt  # Just Strands and boto3
```

Aria in this module can:

- Answer ShopSmart FAQ questions (returns, shipping, payments) from her system prompt
- Look up orders, products, and the product catalog
- Check "live" carrier tracking for a shipment
- Start a return, exchange, or complaint

To keep the module self-contained, the tools are **simulated** — they return
hardcoded data with the *same shape* the real ShopSmart APIs return later. This
lets you focus on the agent itself, not on backend plumbing.

Several pieces here are deliberately simulated or inlined; each one becomes a
real, managed AgentCore capability in a later module. There's a recap mapping
every piece to its module in the [recap at the end](#recap-simulate-now-make-it-real-later).

---

## Step 1 — Anatomy of the agent

Open [`agent.py`](agent.py) and read it top to bottom. It's intentionally short.
The parts to notice:

**The tools.** Each function decorated with `@tool` becomes something the model
can call. The docstring matters — the model reads it to decide *when* to use the
tool, so it's effectively part of the prompt:

```python
@tool
def get_order(order_id: str) -> dict:
    """
    Look up the full details of a single order by its order ID.
    Use this when a customer gives you an order ID (e.g. "ORD-1001") ...
    """
    ...
```

**The system prompt.** This defines Aria's persona, the rules she follows
(including the ShopSmart return/shipping/payment policies), and how she should
use her tools. Notice the policy rules are just *text* here — in Module 08 they
become enforced Policy.

**The agent.** The whole thing is assembled in a few lines — a model, the system
prompt, and the list of tools:

```python
agent = Agent(
    model=BedrockModel(model_id=MODEL_ID, region_name=REGION),
    system_prompt=SYSTEM_PROMPT,
    tools=[get_order, list_orders, get_product,
           search_products, submit_request, check_carrier_tracking],
)
```

Strands runs the reasoning loop for you: the model decides whether to call a
tool, Strands runs it, feeds the result back, and repeats until Aria has a final
answer.

---

## Step 2 — Run Aria locally

From the repository root, activate the course virtual environment (created in
Module 00) and set your Region. The default model is a **US cross-region
inference profile**, so use a US Region such as `us-east-1`:

```bash
source .venv/bin/activate
export AWS_REGION=us-east-1

python modules/module-02-first-agent/agent.py
```

> Aria still needs network access to Amazon Bedrock for the model — that's the
> only thing that isn't local. The tools and data all live in `agent.py`.
> If you haven't confirmed Bedrock Claude access, revisit
> [Module 00 — Prerequisites](../module-00-prerequisites/README.md).

You'll get a chat prompt in your terminal. Type a message and press Enter; type
`exit` or `quit` to stop.

---

## Step 3 — Talk to Aria and watch the tools fire

Try these, one at a time:

```text
What is your return policy?
What's the status of order ORD-1002?
Where is my package for order ORD-1001?
Do you sell headphones?
Show me all orders for customer C001
I want to return order ORD-1001 because it arrived damaged
```

Above each response you'll see log lines showing which tools Aria called, for
example:

```text
INFO  aria — 🔧 get_order(order_id='ORD-1001')
INFO  aria — 🔧 check_carrier_tracking(tracking_number='UPS1234567890')
```

That two-step chain — look up the order to get its tracking number, then check
tracking — is Aria reasoning across multiple tools on her own. This is the
behavior that Gateway (Module 05) and Browser (Module 09) later make real.

<details>
<summary>Sample data you can reference</summary>

**Orders (customer C001 — Alice Johnson):**

| Order | Status | Tracking |
|-------|--------|----------|
| `ORD-1001` | delivered | `UPS1234567890` |
| `ORD-1002` | shipped   | `FDX9876543210` |

**Products:** `P001` Backpack, `P002` Headphones, `P003` Water Bottle,
`P004` Running Shoes, `P005` Bluetooth Speaker, `P006` Yoga Mat.

The full dataset (15 orders across customers C001–C003) arrives with the real
backend in Module 05.

</details>

---

## Step 4 — Experiment

Because everything is local and in one file, this is the best place in the
course to experiment. Try:

- Editing the system prompt (e.g. change the return window) and re-running — see
  how Aria's answers change.
- Asking about an order that doesn't exist (`ORD-9999`) — see how she handles a
  tool returning an error.
- Adding a new simulated product to `_PRODUCTS` and searching for it.

There's no build step and no redeploy — save the file and run again.

### Try a different model

By default Aria uses `us.anthropic.claude-sonnet-4-6`. You don't need to edit
the code to change it — the model ID is read from the `ARIA_MODEL_ID`
environment variable, so you can point Aria at a different model and compare
behavior, speed, or cost.

First, discover which Claude models are available in your Region. The default is
a **cross-region inference profile** (note the `us.` prefix), so list inference
profiles rather than base foundation models:

<details>
<summary>List available model IDs via CLI</summary>

```bash
# Claude inference profiles in your Region (these have the "us." / "global." prefix)
aws bedrock list-inference-profiles \
  --region "$AWS_REGION" \
  --query "inferenceProfileSummaries[?contains(inferenceProfileId,'claude')].[inferenceProfileId,inferenceProfileName]" \
  --output table
```

> **Base model vs. inference profile.** `aws bedrock list-foundation-models`
> shows *base* model IDs (e.g. `anthropic.claude-...`). Many current Claude
> models are only available through an **inference profile** — an ID prefixed
> with `us.` or `global.` that routes requests across Regions. If you use a base
> model ID that requires a profile, the call fails with an error about
> on-demand throughput. When in doubt, use a `us.` profile ID from the command
> above, and keep `AWS_REGION` set to a US Region.

</details>

Then run Aria with your chosen model — no code change required:

```bash
export ARIA_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
python modules/module-02-first-agent/agent.py
```

> Model availability changes over time and varies by account and Region, so
> treat the command above as the source of truth rather than any specific ID
> listed here. Whichever model you pick must be enabled for your account (see
> [Module 00 — Prerequisites](../module-00-prerequisites/README.md)).

---

<details>
<summary>What You Learned</summary>

- What an AI agent is: a model, a system prompt, and tools in a reasoning loop
- How the `@tool` decorator turns a plain Python function into an agent capability
- Why tool docstrings are part of the prompt
- How an agent chains multiple tools to answer one question
- How to run and test an agent locally against Amazon Bedrock

</details>

---

## Recap: simulate now, make it real later

Now that you've seen Aria work, here's the payoff. Every simulated or inlined
piece in this module maps to a real AgentCore capability you add in a later
module — without changing how the agent fundamentally works:

| In this module (simulated / inline)        | Becomes (real capability)        | Module |
|--------------------------------------------|----------------------------------|:------:|
| The agent running locally                  | **Runtime** (managed, scalable)  |   03   |
| FAQ knowledge inlined in the system prompt | **Knowledge Base**               |   04   |
| `get_order`, `search_products`, `submit_request`, … | **Gateway** (real REST APIs) |   05   |
| (no memory — forgets between runs)         | **Memory**                       |   06   |
| "What's your customer ID?"                 | **Identity** (login → JWT)       |   07   |
| Policy rules written in the system prompt  | **Policy** (enforced guardrails) |   08   |
| `check_carrier_tracking` returning canned data | **Browser** (drives a real site) |   09   |

Each later module is essentially "replace one simulated piece with a managed
capability."

---

## Next Step

You now have a working agent, but it only runs on your laptop, its knowledge is
baked into the prompt, and its data is faked. Over the next modules you'll
externalize each piece into a managed AgentCore capability.

First up: deploy this exact agent — unchanged — onto AgentCore **Runtime**, so
it runs as a managed, scalable cloud service.

Proceed to [Module 03 — Runtime](../module-03-runtime/README.md).
