"""
Aria — ShopSmart AI Customer Support Agent
Module 04: Knowledge Base

This is the Module 03 agent with one change: the ShopSmart FAQ is no longer
inlined in the system prompt. Instead, Aria retrieves policy, shipping, and
payment answers from a Bedrock Knowledge Base via a new tool,
`retrieve_from_knowledge_base`.

The order/product/tracking tools are still simulated (they become real via
Gateway in Module 05). This module is about externalizing *knowledge*, and
about the production loop: change the agent, rebuild the image, redeploy.

Configuration (model, region, KB id, KB result count) is loaded from SSM
Parameter Store at startup (see config.py). Set SSM_ENABLED=false to run
locally with env vars.
"""

import logging

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

from config import cfg

# ── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
)
logger = logging.getLogger("aria")
logger.info("Starting Aria with config: %s", cfg)

# ── AWS clients ───────────────────────────────────────────────────────────────

bedrock_agent_runtime = boto3.client(
    "bedrock-agent-runtime",
    region_name=cfg.region,
)

# ── Simulated data (still simulated — real via Gateway in Module 05) ────────────

_PRODUCTS = {
    "P001": {
        "productId": "P001",
        "name": "Classic Blue Backpack",
        "category": "bags",
        "price": 49.99,
        "description": "Durable 30L backpack with padded laptop compartment, "
                       "water bottle pockets, and ergonomic straps. Available "
                       "in blue, black, and grey.",
        "inStock": True,
        "rating": 4.5,
        "reviewCount": 238,
    },
    "P002": {
        "productId": "P002",
        "name": "Wireless Noise-Cancelling Headphones",
        "category": "electronics",
        "price": 129.99,
        "description": "Over-ear headphones with 30-hour battery life, active "
                       "noise cancellation, and foldable design. Includes USB-C "
                       "charging cable and carry pouch.",
        "inStock": True,
        "rating": 4.7,
        "reviewCount": 512,
    },
    "P003": {
        "productId": "P003",
        "name": "Stainless Steel Water Bottle",
        "category": "kitchen",
        "price": 24.99,
        "description": "32oz double-walled vacuum insulated bottle. Keeps drinks "
                       "cold for 24 hours and hot for 12 hours. Leak-proof lid. "
                       "BPA free.",
        "inStock": True,
        "rating": 4.8,
        "reviewCount": 891,
    },
    "P004": {
        "productId": "P004",
        "name": "Running Shoes — Men's",
        "category": "footwear",
        "price": 89.99,
        "description": "Lightweight mesh running shoes with responsive foam "
                       "cushioning and breathable upper. Sizes 7–13. Available "
                       "in white/blue and black/orange.",
        "inStock": True,
        "rating": 4.3,
        "reviewCount": 167,
    },
    "P005": {
        "productId": "P005",
        "name": "Portable Bluetooth Speaker",
        "category": "electronics",
        "price": 59.99,
        "description": "Compact waterproof speaker with 360-degree sound, "
                       "12-hour playtime, and built-in microphone. IPX7 water "
                       "resistance rating.",
        "inStock": False,
        "rating": 4.4,
        "reviewCount": 324,
    },
    "P006": {
        "productId": "P006",
        "name": "Yoga Mat — Non-Slip",
        "category": "sports",
        "price": 34.99,
        "description": "6mm thick eco-friendly TPE yoga mat with alignment lines "
                       "and carrying strap. Non-slip surface on both sides. "
                       "183cm x 61cm.",
        "inStock": True,
        "rating": 4.6,
        "reviewCount": 445,
    },
}

_ORDERS = {
    "ORD-1001": {
        "orderId": "ORD-1001",
        "customerId": "C001",
        "customerName": "Alice Johnson",
        "customerEmail": "alice@example.com",
        "status": "delivered",
        "orderDate": "2026-09-01",
        "deliveryDate": "2026-09-06",
        "items": [
            {"productId": "P001", "name": "Classic Blue Backpack", "quantity": 1, "price": 49.99},
            {"productId": "P003", "name": "Stainless Steel Water Bottle", "quantity": 2, "price": 24.99},
        ],
        "total": 99.97,
        "shippingAddress": "123 Maple Street, Austin, TX 78701",
        "trackingNumber": "UPS1234567890",
    },
    "ORD-1002": {
        "orderId": "ORD-1002",
        "customerId": "C001",
        "customerName": "Alice Johnson",
        "customerEmail": "alice@example.com",
        "status": "shipped",
        "orderDate": "2026-09-13",
        "estimatedDelivery": "2026-09-18",
        "items": [
            {"productId": "P002", "name": "Wireless Noise-Cancelling Headphones", "quantity": 1, "price": 129.99},
        ],
        "total": 129.99,
        "shippingAddress": "123 Maple Street, Austin, TX 78701",
        "trackingNumber": "FDX9876543210",
    },
}

_TRACKING = {
    "UPS1234567890": {
        "trackingNumber": "UPS1234567890",
        "carrier": "UPS",
        "status": "Delivered",
        "lastUpdate": "2026-09-06 14:22",
        "location": "Austin, TX",
        "detail": "Left at front door.",
    },
    "FDX9876543210": {
        "trackingNumber": "FDX9876543210",
        "carrier": "FedEx",
        "status": "In Transit",
        "lastUpdate": "2026-09-16 08:10",
        "location": "Dallas, TX",
        "detail": "Departed FedEx facility — on track for estimated delivery.",
    },
}


# ── Knowledge Base tool (NEW in Module 04) ──────────────────────────────────────

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
    logger.info("🔧 retrieve_from_knowledge_base(query=%r)", query)
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


# ── Simulated tools (unchanged from Module 03) ──────────────────────────────────

@tool
def get_order(order_id: str) -> dict:
    """
    Look up the full details of a single order by its order ID.

    Use this when a customer gives you an order ID (e.g. "ORD-1001") and asks
    about that order's status, contents, total, or delivery.

    Args:
        order_id: The order identifier, e.g. "ORD-1001"

    Returns:
        The order record, or an error message if the order is not found.
    """
    logger.info("🔧 get_order(order_id=%r)", order_id)
    order = _ORDERS.get(order_id.strip().upper())
    if not order:
        return {"error": f"Order {order_id} not found"}
    return order


@tool
def list_orders(customer_id: str) -> dict:
    """
    List all orders belonging to a customer.

    Use this when a customer asks about "my orders" and has given you their
    customer ID (e.g. "C001").

    Args:
        customer_id: The customer identifier, e.g. "C001"

    Returns:
        A dict with the list of orders and a count.
    """
    logger.info("🔧 list_orders(customer_id=%r)", customer_id)
    orders = [o for o in _ORDERS.values() if o["customerId"] == customer_id.strip().upper()]
    return {"orders": orders, "count": len(orders)}


@tool
def get_product(product_id: str) -> dict:
    """
    Get the details of a single product by its product ID.

    Args:
        product_id: The product identifier, e.g. "P002"

    Returns:
        The product record, or an error message if not found.
    """
    logger.info("🔧 get_product(product_id=%r)", product_id)
    product = _PRODUCTS.get(product_id.strip().upper())
    if not product:
        return {"error": f"Product {product_id} not found"}
    return product


@tool
def search_products(query: str) -> dict:
    """
    Search the product catalog by keyword. Matches against product name and
    description.

    Use this when a customer is looking for a product but does not know the
    product ID, e.g. "do you sell headphones?".

    Args:
        query: A keyword or phrase to search for, e.g. "backpack"

    Returns:
        A dict with the matching products and a count.
    """
    logger.info("🔧 search_products(query=%r)", query)
    q = query.strip().lower()
    matches = [
        p for p in _PRODUCTS.values()
        if q in p["name"].lower() or q in p["description"].lower()
    ]
    return {"products": matches, "count": len(matches)}


@tool
def submit_request(order_id: str, request_type: str, reason: str) -> dict:
    """
    Submit a support request against an order — a return, exchange, complaint,
    or general inquiry. Returns a ticket ID.

    Only submit a request after confirming the order exists and the customer
    has clearly asked to proceed.

    Args:
        order_id: The order the request is about, e.g. "ORD-1001"
        request_type: One of "return", "exchange", "complaint", or "inquiry"
        reason: A short description of the customer's reason

    Returns:
        A confirmation with a ticket ID, or an error message.
    """
    logger.info(
        "🔧 submit_request(order_id=%r, request_type=%r, reason=%r)",
        order_id, request_type, reason,
    )
    valid_types = {"return", "exchange", "complaint", "inquiry"}
    request_type = request_type.strip().lower()
    if request_type not in valid_types:
        return {"error": f"requestType must be one of: {', '.join(sorted(valid_types))}"}
    if order_id.strip().upper() not in _ORDERS:
        return {"error": f"Order {order_id} not found"}

    ticket_id = "TKT-DEMO0001"
    return {
        "ticketId": ticket_id,
        "orderId": order_id.strip().upper(),
        "requestType": request_type,
        "status": "open",
        "message": f"Your {request_type} request has been submitted. Ticket ID: {ticket_id}",
    }


@tool
def check_carrier_tracking(tracking_number: str) -> dict:
    """
    Check the live tracking status for a shipment by its carrier tracking
    number. Use this after obtaining a tracking number from an order to answer
    "where is my package?".

    Args:
        tracking_number: The carrier tracking number, e.g. "UPS1234567890"

    Returns:
        The latest tracking status, or an error message if unavailable.
    """
    logger.info("🔧 check_carrier_tracking(tracking_number=%r)", tracking_number)
    tracking = _TRACKING.get(tracking_number.strip().upper())
    if not tracking:
        return {"error": f"No tracking information found for {tracking_number}"}
    return tracking


# ── System Prompt (FAQ removed — Aria retrieves it from the KB now) ─────────────

SYSTEM_PROMPT = """You are Aria, the AI customer support agent for ShopSmart — a friendly online retail store.

Your role is to help customers with their shopping experience. Be warm, helpful, and concise.

## How to use your tools
- For policy questions (returns, refunds, shipping, payments, store hours, general FAQs): use retrieve_from_knowledge_base. Do not rely on memorized policy — always look it up.
- For order questions: use get_order (when you have an order ID) or list_orders (when you have a customer ID).
- For product questions: use search_products (by keyword) or get_product (by product ID).
- For "where is my package?": first get the order's trackingNumber via get_order, then call check_carrier_tracking.
- For returns, exchanges, complaints, or inquiries: use submit_request.
- Never invent order, product, tracking, or policy details — always use a tool to get accurate data.
- If a customer asks about their orders but has not given a customer ID or order ID, politely ask for it.

## Tone
- Friendly but professional. Keep simple answers to 2–3 sentences.
- If something is outside what you know or can look up, say so and suggest contacting live support.
"""

# ── Agent ──────────────────────────────────────────────────────────────────────

agent = Agent(
    model=BedrockModel(model_id=cfg.model_id, region_name=cfg.region),
    system_prompt=SYSTEM_PROMPT,
    tools=[
        retrieve_from_knowledge_base,
        get_order,
        list_orders,
        get_product,
        search_products,
        submit_request,
        check_carrier_tracking,
    ],
)

# ── AgentCore Runtime Entrypoint ───────────────────────────────────────────────

app = BedrockAgentCoreApp()


@app.entrypoint
def agent_invocation(payload: dict, context) -> dict:
    """
    AgentCore Runtime entrypoint. Called on every agent invocation.

    Args:
        payload: Contains the user's message under the "prompt" key
        context: AgentCore context (session_id, etc.)

    Returns:
        dict with "result" key containing Aria's response
    """
    user_message = payload.get("prompt", "")

    if not isinstance(user_message, str) or not user_message.strip():
        return {"error": "Invalid input: 'prompt' must be a non-empty string"}

    result = agent(user_message)

    message = result.message
    if isinstance(message, dict):
        for block in message.get("content", []):
            if isinstance(block, dict) and "text" in block:
                return {"result": block["text"]}

    return {"result": str(message)}


if __name__ == "__main__":
    app.run()
