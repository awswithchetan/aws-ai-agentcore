"""
Aria — ShopSmart AI Customer Support Agent
Module 02: A Self-Contained Agent (local, no AWS infrastructure)

This is your first look at what an AI agent actually is: a model, a system
prompt, and a set of tools wired together in a loop. Everything here runs
locally on your laptop — the only network call is to Amazon Bedrock for the
language model.

To keep this module simple and self-contained, the tools below are SIMULATED.
They return hardcoded data with the *same shape* the real ShopSmart APIs return
later in the course. The FAQ knowledge and the return policy are inlined into
the system prompt.

Later modules replace each simulated piece with a real, managed AgentCore
capability — without changing how the agent fundamentally works:

  - the agent running locally    → Runtime          (Module 03)
  - inline FAQ knowledge         → Knowledge Base    (Module 04)
  - simulated order/product/...  → Gateway (real APIs) (Module 05)
  - conversation memory          → Memory            (Module 06)
  - "who is the customer?"       → Identity          (Module 07)
  - policy rules in the prompt   → Policy            (Module 08)
  - simulated carrier tracking   → Browser           (Module 09)

Run it locally:
    export AWS_REGION=us-east-1
    python agent.py

Optionally override the model (default: us.anthropic.claude-sonnet-4-6):
    export ARIA_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
"""

import logging
import os
import sys

from strands import Agent, tool
from strands.models import BedrockModel

# ── Logging ─────────────────────────────────────────────────────────────────
# INFO-level logging lets you *watch* the agent pick and call tools. This is the
# most instructive part of the module — you see the reasoning loop in action.

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
)
logger = logging.getLogger("aria")

# The default model is a US cross-region inference profile (the "us." prefix),
# so the agent must run in a US region. You can override the model without
# editing this file by setting the ARIA_MODEL_ID environment variable — see the
# "Try a different model" section in the module README. We also bind the Bedrock
# model to AWS_REGION explicitly (default us-east-1) so it does not silently pick
# up a different region from your AWS profile.
MODEL_ID = os.environ.get("ARIA_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
REGION = os.environ.get("AWS_REGION", "us-east-1")

# ── Simulated data ────────────────────────────────────────────────────────────
# A small slice of the ShopSmart catalog and orders. The shapes match the real
# DynamoDB records used later (see shopsmart-backend/seed_data.py), so when we
# swap these tools for real APIs in Module 05, the agent behaves identically.

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

# Two sample orders for customer C001 (Alice Johnson) are enough to demonstrate
# order lookup, status, delivery estimates, and tracking. The real dataset
# (Module 05) has 15 orders across 3 customers.
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

# Simulated live carrier tracking, keyed by tracking number. In Module 09 this
# is replaced by a real AgentCore Browser session that visits a carrier portal.
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


# ── Tools ──────────────────────────────────────────────────────────────────────
# Each function decorated with @tool becomes a capability the model can invoke.
# The docstring is what the model reads to decide *when* to call the tool, so it
# is part of the prompt — write it for the model, not just for humans.

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


# ── System Prompt ──────────────────────────────────────────────────────────────
# The system prompt defines Aria's persona, the rules she must follow, and the
# ShopSmart knowledge she can rely on. In later modules the FAQ moves to a
# Knowledge Base (Module 04) and the rules become enforced Policy (Module 08).

SYSTEM_PROMPT = """You are Aria, the AI customer support agent for ShopSmart — a friendly online retail store.

Your role is to help customers with their shopping experience. Be warm, helpful, and concise.

## How to use your tools
- For order questions: use get_order (when you have an order ID) or list_orders (when you have a customer ID).
- For product questions: use search_products (by keyword) or get_product (by product ID).
- For "where is my package?": first get the order's trackingNumber via get_order, then call check_carrier_tracking.
- For returns, exchanges, complaints, or inquiries: use submit_request.
- Never invent order, product, or tracking details — always use a tool to get real data.
- If a customer asks about their orders but has not given a customer ID or order ID, politely ask for it.

## ShopSmart policies (follow these exactly)
- Returns are accepted within 30 days of delivery for standard items (electronics: 15 days).
- Items must be in original, unused condition with tags attached.
- Return shipping is free for defective or wrong items; $5.99 for change-of-mind or sizing returns.
- Refunds are processed within 3–5 business days after the returned item is received.
- ShopSmart does not do direct exchanges: return the original and place a new order.

## Shipping
- Standard: 5–7 business days, free on orders over $50. Express: 2–3 business days, $9.99.
- Same-day delivery in select cities, $14.99. International to 30 countries, rates vary.

## Payment methods
- Visa, Mastercard, American Express, Discover; PayPal, Apple Pay, Google Pay; ShopSmart Gift Cards.

## Tone
- Friendly but professional. Keep simple answers to 2–3 sentences.
- If something is outside what you know or can look up, say so and suggest contacting live support.
"""

# ── Agent ──────────────────────────────────────────────────────────────────────
# This is the whole agent: a model, a system prompt, and a list of tools.
# Strands runs the reasoning loop — deciding when to call a tool, feeding the
# result back to the model, and repeating until it has a final answer.

agent = Agent(
    model=BedrockModel(model_id=MODEL_ID, region_name=REGION),
    system_prompt=SYSTEM_PROMPT,
    tools=[
        get_order,
        list_orders,
        get_product,
        search_products,
        submit_request,
        check_carrier_tracking,
    ],
)


# ── Local CLI chat loop ─────────────────────────────────────────────────────────
# Run `python agent.py` and chat with Aria in your terminal. Watch the tool
# logs above each response to see which tools she calls and why.

# ANSI color codes for the "You" prompt. The colored prompt makes it easy to
# scroll back and find where each of your questions — and Aria's answer — begins.
# Colors are disabled automatically when output is not a TTY (e.g. piped to a
# file) so we don't emit escape codes into logs.
_COLOR = sys.stdout.isatty()
_CYAN = "\033[96m" if _COLOR else ""
_BOLD = "\033[1m" if _COLOR else ""
_RESET = "\033[0m" if _COLOR else ""


def _run_cli() -> None:
    print("\n🛍️  ShopSmart Support — Aria (local)")
    print("Type your message and press Enter. Type 'exit' or 'quit' to stop.\n")
    print("Try:")
    print("  • What is your return policy?")
    print("  • What's the status of order ORD-1002?")
    print("  • Where is my package for order ORD-1001?")
    print("  • Do you sell headphones?")
    print("  • Show me all orders for customer C001\n")

    while True:
        try:
            user_input = input(f"{_BOLD}{_CYAN}You  › {_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        # Strands streams Aria's response to the terminal as it is generated,
        # so we don't print the result again here (that would duplicate it).
        # A short label before the stream marks where each answer begins.
        print("\nAria › ", end="", flush=True)
        agent(user_input)
        print()


if __name__ == "__main__":
    _run_cli()
