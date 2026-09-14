"""
Aria — ShopSmart AI Customer Support Agent
Module 09: Browser — Live carrier tracking

Replaces the manual customer_id payload with verified JWT identity.
AgentCore Runtime validates the Cognito JWT before forwarding the Authorization
header to this code. We decode it to extract the customer's identity.

Tools continue to be routed through AgentCore Gateway (MCP) as set up in
Module 05, and memory is scoped per customer as set up in Module 06.

New capabilities vs Module 06:
  - Customer identity comes from a verified Cognito JWT — not from the payload
  - customer_id = custom:customer_id claim (matches DynamoDB customerId)
  - customer name and email come directly from the JWT
  - Unauthenticated requests are rejected by the Runtime before reaching this code

Configuration (SSM parameters — prefix /aria/):
  /aria/model_id            — Bedrock model ID
  /aria/knowledge_base_id   — Bedrock Knowledge Base ID
  /aria/kb_num_results      — Number of KB chunks per query
  /aria/region              — AWS region
  /aria/gateway_endpoint    — AgentCore Gateway MCP endpoint URL
  /aria/memory_id           — AgentCore Memory resource ID
  /aria/memory_strategy_id  — AgentCore Memory strategy ID
  /aria/carrier_tracking_url — CloudFront URL for the simulated carrier site
"""

import logging

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from strands import Agent, tool
from strands.tools.mcp import MCPClient

from config import cfg
from identity.jwt import extract_identity
from memory.session import get_memory_session_manager
from tools.browser import check_carrier_tracking

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
                "vectorSearchConfiguration": {
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
- For the latest carrier status or delivery estimate: first get the order's trackingNumber, then use check_carrier_tracking
- When reporting carrier tracking results, always include the exact `Tracking ID` returned by check_carrier_tracking as a separate line; never omit or paraphrase it
- For return/exchange/complaint requests: use submit_request
- Never make up information — always use the tools to get accurate data
- Keep responses concise and friendly

## Identifying the customer:
- The current customer's identity is injected into your system prompt from a verified JWT token
- Use the customer ID directly with list_orders — do not ask for it
- If customer ID is "anonymous", the session is unauthenticated — politely ask them to log in

## Using memory:
- You may have relevant memories about this customer from past conversations
- If memories are available in your context, use them to personalise responses
- You already know the customer's name from the JWT — no need to ask

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

    Customer identity is extracted from the verified JWT (forwarded via the
    custom id-token header). Tools are discovered from the AgentCore Gateway
    via MCP (SigV4-signed). Memory is scoped per customer.

    Args:
        payload: Contains "prompt"
        context: AgentCore RequestContext — carries forwarded request headers

    Returns:
        dict with "result" key containing Aria's response
    """
    user_message = payload.get("prompt", "")

    if not isinstance(user_message, str) or not user_message.strip():
        return {"error": "Invalid input: 'prompt' must be a non-empty string"}

    # Extract verified identity from the JWT forwarded by the Runtime.
    identity = extract_identity(context)
    session_id = getattr(context, "session_id", "default")

    logger.info(
        "Invocation — customer_id=%s name=%s authenticated=%s session_id=%s",
        identity.customer_id, identity.name, identity.is_authenticated, session_id,
    )

    # Build customer context block for the system prompt.
    if identity.is_authenticated:
        customer_context = (
            f"\n\n## Current customer\n"
            f"Customer ID: {identity.customer_id}\n"
            f"Name: {identity.display_name}\n"
            f"Email: {identity.email}\n\n"
            f"Address them by name. Use their customer ID directly with tools — do not ask for it."
        )
    else:
        customer_context = (
            "\n\n## Current customer\n"
            "This is an anonymous session — the customer is not logged in.\n"
            "Politely let them know they need to log in to access order information."
        )

    system_prompt = SYSTEM_PROMPT + customer_context

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
            tools=[retrieve_from_knowledge_base, check_carrier_tracking] + gateway_tools,
            session_manager=get_memory_session_manager(
                session_id=session_id,
                actor_id=identity.customer_id,
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
