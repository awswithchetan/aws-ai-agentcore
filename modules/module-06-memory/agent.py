"""
Aria — ShopSmart AI Customer Support Agent
Module 06: Memory — Stateful Agents

Adds persistent memory so Aria remembers customers across sessions.
Tools continue to be routed through AgentCore Gateway (MCP) as set up
in Module 05 — memory is layered on top with no change to tool routing.

New capabilities vs Module 05:
  - Agent is created per invocation, scoped to the customer (actor_id)
  - AgentCore Memory persists facts across sessions
  - Aria recalls returning customers by name and past preferences

Configuration (SSM parameters — prefix /aria/):
  /aria/model_id            — Bedrock model ID
  /aria/knowledge_base_id   — Bedrock Knowledge Base ID
  /aria/kb_num_results      — Number of KB chunks per query
  /aria/region              — AWS region
  /aria/gateway_endpoint    — AgentCore Gateway MCP endpoint URL
  /aria/memory_id           — AgentCore Memory resource ID
  /aria/memory_strategy_id  — AgentCore Memory strategy ID
"""

import logging

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from strands import Agent, tool
from strands.tools.mcp import MCPClient

from config import cfg
from memory.session import get_memory_session_manager

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)
logger.info("Starting Aria with config: %s", cfg)

# ── AWS clients ───────────────────────────────────────────────────────────────

bedrock_agent_runtime = boto3.client(
    "bedrock-agent-runtime",
    region_name=cfg.region,
)

# ── Knowledge Base tool (local — calls Bedrock directly, not via Gateway) ─────

@tool
def retrieve_from_knowledge_base(query: str) -> str:
    """
    Retrieve relevant information from the ShopSmart knowledge base.
    Use this tool to answer questions about return policy, shipping,
    payment methods, store hours, and general FAQs.

    Args:
        query: The customer's question or search query

    Returns:
        Relevant content from ShopSmart's knowledge base documents
    """
    if not cfg.knowledge_base_id:
        return "Knowledge base not configured."

    try:
        response = bedrock_agent_runtime.retrieve(
            knowledgeBaseId=cfg.knowledge_base_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "managedSearchConfiguration": {
                    "numberOfResults": cfg.kb_num_results,
                }
            },
        )
        results = response.get("retrievalResults", [])
        if not results:
            return "No relevant information found in the knowledge base."

        return "\n\n".join([
            r["content"]["text"]
            for r in results
            if r.get("content", {}).get("text")
        ])
    except Exception as e:
        logger.error("Knowledge base retrieval failed: %s", e, exc_info=True)
        return "Knowledge base retrieval is currently unavailable."


# ── System Prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Aria, the AI customer support agent for ShopSmart — a friendly online retail store.

Your role is to help customers with their shopping experience. Be warm, helpful, and concise.

## How to answer questions:
- For policy questions (returns, shipping, payments): use retrieve_from_knowledge_base
- For order questions: use list_orders or get_order
- For product questions: use search_products or get_product
- For return/exchange/complaint requests: use submit_request
- Never make up information — always use the tools to get accurate data
- Keep responses concise and friendly

## Identifying the customer:
- The current customer's ID is injected into your system prompt when they set it in the UI
- If a customer ID is present, use it directly with list_orders — do not ask for it again
- If no customer ID is provided (anonymous session), politely ask for their customer ID (e.g. C001)
- If a customer provides an order ID directly (e.g. ORD-1001), use get_order directly

## Using memory:
- You may have relevant memories about this customer from past conversations
- If memories are available in your context, use them to personalise responses
- For example: greet returning customers by name, recall their preferences

## What you can help with:
- Order status, tracking, and history
- Returns, exchanges, and complaints
- Product search and details
- Return policy, shipping options, payment methods
- Store hours and support contact
"""

# ── AgentCore Runtime Entrypoint ───────────────────────────────────────────────

app = BedrockAgentCoreApp()

@app.entrypoint
def agent_invocation(payload: dict, context) -> dict:
    """
    AgentCore Runtime entrypoint. Called on every agent invocation.

    The agent is created fresh per invocation so memory is scoped correctly
    to the customer (actor_id) and session (session_id). Tools are discovered
    from the AgentCore Gateway via MCP (SigV4-signed).

    Args:
        payload: Contains "prompt" and optionally "customer_id"
        context: AgentCore context (session_id, etc.)

    Returns:
        dict with "result" key containing Aria's response
    """
    user_message = payload.get("prompt", "")

    if not isinstance(user_message, str) or not user_message.strip():
        return {"error": "Invalid input: 'prompt' must be a non-empty string"}

    # customer_id is provided by the customer for now.
    # In Module 07 (Identity) this will come from the verified JWT token.
    customer_id = payload.get("customer_id", "anonymous")
    session_id = getattr(context, "session_id", str(payload.get("session_id", "default")))

    # Inject customer identity into the system prompt so Aria knows who she
    # is talking to.
    if customer_id and customer_id != "anonymous":
        system_prompt = SYSTEM_PROMPT + (
            f"\n\n## Current customer\n"
            f"You are speaking with customer ID: {customer_id}. "
            f"Use any memories you have about this customer to personalise your response. "
            f"Address them by name if you know it from memory."
        )
    else:
        system_prompt = SYSTEM_PROMPT

    # Connect to the Gateway MCP endpoint (IAM SigV4-signed).
    mcp_client = MCPClient(
        lambda: aws_iam_streamablehttp_client(
            endpoint=cfg.gateway_endpoint,
            aws_region=cfg.region,
            aws_service="bedrock-agentcore",
        )
    )

    with mcp_client:
        gateway_tools = mcp_client.list_tools_sync()
        logger.info("Discovered %d tool(s) from Gateway", len(gateway_tools))

        agent = Agent(
            model=cfg.model_id,
            system_prompt=system_prompt,
            tools=[retrieve_from_knowledge_base] + gateway_tools,
            session_manager=get_memory_session_manager(
                session_id=session_id,
                actor_id=customer_id,
            ),
        )

        result = agent(user_message)

    message = result.message
    if isinstance(message, dict):
        for block in message.get("content", []):
            if isinstance(block, dict) and "text" in block:
                return {"result": block["text"]}

    return {"result": str(message)}


if __name__ == "__main__":
    app.run()
