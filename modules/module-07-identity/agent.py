"""
Aria — ShopSmart AI Customer Support Agent
Module 07: Identity — Auth Done Right

Replaces the Module 06 manual customer_id payload with verified JWT identity.
AgentCore Runtime validates the Cognito JWT before forwarding the Authorization
header to this code. We decode it to extract the customer's sub, name, and email.

New capabilities vs Module 06:
  - Customer identity comes from a verified Cognito JWT — not from the payload
  - customer_id = JWT sub claim (matches DynamoDB customerId)
  - customer name and email come directly from the JWT — no need to rely on memory
  - Unauthenticated requests are rejected by the Runtime before reaching this code

Configuration (SSM parameters — same prefix /aria/):
  /aria/model_id              — Bedrock model ID
  /aria/knowledge_base_id     — Bedrock Knowledge Base ID
  /aria/kb_num_results        — Number of KB chunks per query
  /aria/region                — AWS region
  /aria/api_base_url          — ShopSmart API base URL
  /aria/memory_id             — AgentCore Memory resource ID
  /aria/memory_strategy_id    — AgentCore Memory strategy ID
"""

import logging
import os

import boto3
import requests
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool

from config import cfg
from identity.jwt import extract_identity
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

# ── Tools — Knowledge Base ────────────────────────────────────────────────────

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

        context = "\n\n".join([
            result["content"]["text"]
            for result in results
            if result.get("content", {}).get("text")
        ])

        return context

    except Exception as e:
        logger.error("Knowledge base retrieval failed: %s", e, exc_info=True)
        return "Knowledge base retrieval is currently unavailable."


# ── Tools — Orders ────────────────────────────────────────────────────────────

@tool
def list_customer_orders(customer_id: str) -> str:
    """
    List all orders for a customer.
    Use this when a customer asks about their orders, order history,
    or wants to know what they have ordered.

    Args:
        customer_id: The customer's ID (e.g. C001)

    Returns:
        List of orders for the customer
    """
    try:
        response = requests.get(
            f"{cfg.api_base_url}/orders",
            params={"customerId": customer_id},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        orders = data.get("orders", [])
        if not orders:
            return f"No orders found for customer {customer_id}."
        return str(orders)
    except Exception as e:
        logger.error("list_customer_orders failed: %s", e, exc_info=True)
        return "Unable to retrieve orders at this time. Please try again."


@tool
def get_order_details(order_id: str) -> str:
    """
    Get full details of a specific order including status, items, tracking,
    and any support requests.
    Use this when a customer asks about a specific order.

    Args:
        order_id: The order ID (e.g. ORD-1001)

    Returns:
        Full order details
    """
    try:
        response = requests.get(
            f"{cfg.api_base_url}/orders/{order_id}",
            timeout=10,
        )
        if response.status_code == 404:
            return f"Order {order_id} not found."
        response.raise_for_status()
        return str(response.json())
    except Exception as e:
        logger.error("get_order_details failed: %s", e, exc_info=True)
        return "Unable to retrieve order details at this time. Please try again."


# ── Tools — Products ──────────────────────────────────────────────────────────

@tool
def get_product_details(product_id: str) -> str:
    """
    Get details of a specific product including name, price, description,
    availability, and rating.

    Args:
        product_id: The product ID (e.g. P001)

    Returns:
        Full product details
    """
    try:
        response = requests.get(
            f"{cfg.api_base_url}/products/{product_id}",
            timeout=10,
        )
        if response.status_code == 404:
            return f"Product {product_id} not found."
        response.raise_for_status()
        return str(response.json())
    except Exception as e:
        logger.error("get_product_details failed: %s", e, exc_info=True)
        return "Unable to retrieve product details at this time. Please try again."


@tool
def search_products(keyword: str = "", category: str = "") -> str:
    """
    Search the ShopSmart product catalog by keyword or category.
    At least one of keyword or category must be provided.

    Args:
        keyword:  Search term to match against product name and description
        category: Filter by category (bags, electronics, kitchen, footwear, sports)

    Returns:
        List of matching products
    """
    if not keyword and not category:
        return "Please provide a keyword or category to search."

    try:
        params = {}
        if keyword:
            params["q"] = keyword
        if category:
            params["category"] = category

        response = requests.get(
            f"{cfg.api_base_url}/products",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        products = data.get("products", [])
        if not products:
            return "No products found matching your search."
        return str(products)
    except Exception as e:
        logger.error("search_products failed: %s", e, exc_info=True)
        return "Unable to search products at this time. Please try again."


# ── Tools — Support Requests ──────────────────────────────────────────────────

@tool
def submit_support_request(order_id: str, request_type: str, reason: str) -> str:
    """
    Submit a support request for an order — return, exchange, complaint, or inquiry.
    Use this when a customer wants to return an item, raise a complaint,
    or ask about a specific order.

    Args:
        order_id:     The order ID the request is for (e.g. ORD-1001)
        request_type: One of: return, exchange, complaint, inquiry
        reason:       Customer's reason or description of the issue

    Returns:
        Confirmation with ticket ID
    """
    try:
        response = requests.post(
            f"{cfg.api_base_url}/requests",
            json={
                "orderId": order_id,
                "requestType": request_type,
                "reason": reason,
            },
            timeout=10,
        )
        if response.status_code == 404:
            return f"Order {order_id} not found. Please check the order ID."
        if response.status_code == 400:
            return f"Invalid request: {response.json().get('error', 'Bad request')}"
        response.raise_for_status()
        data = response.json()
        return data.get("message", str(data))
    except Exception as e:
        logger.error("submit_support_request failed: %s", e, exc_info=True)
        return "Unable to submit your request at this time. Please try again."


# ── System Prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Aria, the AI customer support agent for ShopSmart — a friendly online retail store.

Your role is to help customers with their shopping experience. Be warm, helpful, and concise.

## How to answer questions:
- For policy questions (returns, shipping, payments): use retrieve_from_knowledge_base
- For order questions: use list_customer_orders or get_order_details
- For product questions: use search_products or get_product_details
- For return/exchange/complaint requests: use submit_support_request
- Never make up information — always use the tools to get accurate data
- Keep responses concise and friendly

## Identifying the customer:
- The current customer's identity is injected into your system prompt from a verified JWT token
- Use the customer ID directly with list_customer_orders — do not ask for it
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

# ── Tools list ─────────────────────────────────────────────────────────────────

TOOLS = [
    retrieve_from_knowledge_base,
    list_customer_orders,
    get_order_details,
    get_product_details,
    search_products,
    submit_support_request,
]

# ── AgentCore Runtime Entrypoint ───────────────────────────────────────────────

app = BedrockAgentCoreApp()

@app.entrypoint
def agent_invocation(payload: dict, context) -> dict:
    """
    AgentCore Runtime entrypoint.

    Module 07 change: customer identity is now extracted from the verified
    JWT in the Authorization header instead of the request payload.

    Args:
        payload: Contains "prompt"
        context: AgentCore RequestContext — carries request headers including Authorization

    Returns:
        dict with "result" key containing Aria's response
    """
    user_message = payload.get("prompt", "")

    if not isinstance(user_message, str) or not user_message.strip():
        return {"error": "Invalid input: 'prompt' must be a non-empty string"}

    # Extract verified identity from the JWT forwarded by the Runtime.
    # The Runtime has already validated the token — we just decode the payload.
    identity = extract_identity(context)
    session_id = getattr(context, "session_id", "default")

    logger.info(
        "Invocation — customer_id=%s name=%s authenticated=%s session_id=%s",
        identity.customer_id, identity.name, identity.is_authenticated, session_id,
    )

    # Build customer context block for the system prompt.
    # Name and email come directly from the verified JWT — always accurate.
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

    agent = Agent(
        model=cfg.model_id,
        system_prompt=system_prompt,
        tools=TOOLS,
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
