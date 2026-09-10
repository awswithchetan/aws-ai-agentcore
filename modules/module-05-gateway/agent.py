"""
Aria — ShopSmart AI Customer Support Agent
Module 05: Gateway — Connecting Real Tools

Tools are routed through AgentCore Gateway (MCP) instead of being
hardcoded in agent code. The Gateway exposes the ShopSmart REST API
as MCP tools via an OpenAPI spec — the agent discovers them at runtime.

This architecture means:
  - No tool definitions to maintain in agent code
  - Policy (Module 08) and Observability (Module 09) attach to the Gateway
    with no agent code changes needed
  - New API endpoints become available as tools automatically

New capabilities vs Module 04:
  - list_orders      — list all orders for a customer
  - get_order        — get full details of a specific order
  - get_product      — get details of a specific product
  - search_products  — search the product catalog
  - submit_request   — submit a return, exchange, or support ticket

Configuration (SSM parameters — prefix /aria/):
  /aria/model_id          — Bedrock model ID
  /aria/knowledge_base_id — Bedrock Knowledge Base ID
  /aria/kb_num_results    — Number of KB chunks per query
  /aria/region            — AWS region
  /aria/gateway_endpoint  — AgentCore Gateway MCP endpoint URL
"""

import logging

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from strands import Agent, tool
from strands.tools.mcp import MCPClient

from config import cfg

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
- You do not have automatic access to who the customer is yet
- If a customer asks about their orders, politely ask for their customer ID (e.g. C001)
- If a customer provides an order ID directly (e.g. ORD-1001), use get_order directly

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
    AgentCore Runtime entrypoint.

    Connects to the AgentCore Gateway MCP endpoint to discover all
    ShopSmart tools, then runs the agent with those tools plus the
    local Knowledge Base tool.

    Args:
        payload: Contains the user's message under "prompt"
        context: AgentCore context (session_id, etc.)

    Returns:
        dict with "result" key containing Aria's response
    """
    user_message = payload.get("prompt", "")

    if not isinstance(user_message, str) or not user_message.strip():
        return {"error": "Invalid input: 'prompt' must be a non-empty string"}

    # Connect to the Gateway MCP endpoint.
    # The Gateway uses IAM (AWS_IAM) inbound auth, so requests must be signed
    # with SigV4 using the container's IAM execution role credentials.
    # aws_iam_streamablehttp_client handles the signing automatically.
    mcp_client = MCPClient(
        lambda: aws_iam_streamablehttp_client(
            endpoint=cfg.gateway_endpoint,
            aws_region=cfg.region,
            aws_service="bedrock-agentcore",
        )
    )

    with mcp_client:
        # Discover all tools registered on the Gateway
        gateway_tools = mcp_client.list_tools_sync()
        logger.info("Discovered %d tool(s) from Gateway", len(gateway_tools))

        agent = Agent(
            model=cfg.model_id,
            system_prompt=SYSTEM_PROMPT,
            # KB tool is local; Gateway tools come from the MCP endpoint
            tools=[retrieve_from_knowledge_base] + gateway_tools,
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
