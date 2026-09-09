"""
ShopSmart — Seed Data Script
=============================
Populates the DynamoDB orders and products tables with realistic sample data.

Run this once after deploying the CloudFormation stack:

    export AWS_REGION=us-east-1
    export ENVIRONMENT=dev          # must match the CloudFormation Environment parameter
    python seed_data.py

The script is idempotent — safe to re-run, existing items will be overwritten.
"""

import os
import sys
import boto3
from decimal import Decimal
from datetime import datetime, timezone, timedelta

# ── Config ────────────────────────────────────────────────────────────────────

REGION = os.environ.get("AWS_REGION", "us-east-1")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
ORDERS_TABLE = f"shopsmart-orders-{ENVIRONMENT}"
PRODUCTS_TABLE = f"shopsmart-products-{ENVIRONMENT}"

dynamodb = boto3.resource("dynamodb", region_name=REGION)

# ── Helper ────────────────────────────────────────────────────────────────────

def days_ago(n):
    return (datetime.now(timezone.utc) - timedelta(days=n)).strftime("%Y-%m-%d")

def days_from_now(n):
    return (datetime.now(timezone.utc) + timedelta(days=n)).strftime("%Y-%m-%d")

# ── Products ──────────────────────────────────────────────────────────────────

PRODUCTS = [
    {
        "productId": "P001",
        "name": "Classic Blue Backpack",
        "nameLower": "classic blue backpack",
        "category": "bags",
        "price": Decimal("49.99"),
        "description": "Durable 30L backpack with padded laptop compartment, water bottle pockets, and ergonomic straps. Available in blue, black, and grey.",
        "descriptionLower": "durable 30l backpack with padded laptop compartment water bottle pockets and ergonomic straps available in blue black and grey",
        "inStock": True,
        "rating": Decimal("4.5"),
        "reviewCount": 238,
    },
    {
        "productId": "P002",
        "name": "Wireless Noise-Cancelling Headphones",
        "nameLower": "wireless noise-cancelling headphones",
        "category": "electronics",
        "price": Decimal("129.99"),
        "description": "Over-ear headphones with 30-hour battery life, active noise cancellation, and foldable design. Includes USB-C charging cable and carry pouch.",
        "descriptionLower": "over-ear headphones with 30-hour battery life active noise cancellation and foldable design includes usb-c charging cable and carry pouch",
        "inStock": True,
        "rating": Decimal("4.7"),
        "reviewCount": 512,
    },
    {
        "productId": "P003",
        "name": "Stainless Steel Water Bottle",
        "nameLower": "stainless steel water bottle",
        "category": "kitchen",
        "price": Decimal("24.99"),
        "description": "32oz double-walled vacuum insulated bottle. Keeps drinks cold for 24 hours and hot for 12 hours. Leak-proof lid. BPA free.",
        "descriptionLower": "32oz double-walled vacuum insulated bottle keeps drinks cold for 24 hours and hot for 12 hours leak-proof lid bpa free",
        "inStock": True,
        "rating": Decimal("4.8"),
        "reviewCount": 891,
    },
    {
        "productId": "P004",
        "name": "Running Shoes — Men's",
        "nameLower": "running shoes men's",
        "category": "footwear",
        "price": Decimal("89.99"),
        "description": "Lightweight mesh running shoes with responsive foam cushioning and breathable upper. Sizes 7–13. Available in white/blue and black/orange.",
        "descriptionLower": "lightweight mesh running shoes with responsive foam cushioning and breathable upper sizes 7-13 available in white blue and black orange",
        "inStock": True,
        "rating": Decimal("4.3"),
        "reviewCount": 167,
    },
    {
        "productId": "P005",
        "name": "Portable Bluetooth Speaker",
        "nameLower": "portable bluetooth speaker",
        "category": "electronics",
        "price": Decimal("59.99"),
        "description": "Compact waterproof speaker with 360-degree sound, 12-hour playtime, and built-in microphone. IPX7 water resistance rating.",
        "descriptionLower": "compact waterproof speaker with 360-degree sound 12-hour playtime and built-in microphone ipx7 water resistance rating",
        "inStock": False,
        "rating": Decimal("4.4"),
        "reviewCount": 324,
    },
    {
        "productId": "P006",
        "name": "Yoga Mat — Non-Slip",
        "nameLower": "yoga mat non-slip",
        "category": "sports",
        "price": Decimal("34.99"),
        "description": "6mm thick eco-friendly TPE yoga mat with alignment lines and carrying strap. Non-slip surface on both sides. 183cm x 61cm.",
        "descriptionLower": "6mm thick eco-friendly tpe yoga mat with alignment lines and carrying strap non-slip surface on both sides 183cm x 61cm",
        "inStock": True,
        "rating": Decimal("4.6"),
        "reviewCount": 445,
    },
]

# ── Orders ────────────────────────────────────────────────────────────────────

ORDERS = [
    # Customer C001 — Alice Johnson
    {
        "orderId": "ORD-1001",
        "customerId": "C001",
        "customerName": "Alice Johnson",
        "customerEmail": "alice@example.com",
        "status": "delivered",
        "orderDate": days_ago(15),
        "deliveryDate": days_ago(10),
        "items": [
            {"productId": "P001", "name": "Classic Blue Backpack", "quantity": 1, "price": Decimal("49.99")},
            {"productId": "P003", "name": "Stainless Steel Water Bottle", "quantity": 2, "price": Decimal("24.99")},
        ],
        "total": Decimal("99.97"),
        "shippingAddress": "123 Maple Street, Austin, TX 78701",
        "trackingNumber": "UPS1234567890",
    },
    {
        "orderId": "ORD-1002",
        "customerId": "C001",
        "customerName": "Alice Johnson",
        "customerEmail": "alice@example.com",
        "status": "shipped",
        "orderDate": days_ago(3),
        "estimatedDelivery": days_from_now(2),
        "items": [
            {"productId": "P002", "name": "Wireless Noise-Cancelling Headphones", "quantity": 1, "price": Decimal("129.99")},
        ],
        "total": Decimal("129.99"),
        "shippingAddress": "123 Maple Street, Austin, TX 78701",
        "trackingNumber": "FDX9876543210",
    },
    # Customer C002 — Bob Smith
    {
        "orderId": "ORD-1003",
        "customerId": "C002",
        "customerName": "Bob Smith",
        "customerEmail": "bob@example.com",
        "status": "processing",
        "orderDate": days_ago(1),
        "estimatedDelivery": days_from_now(5),
        "items": [
            {"productId": "P004", "name": "Running Shoes — Men's", "quantity": 1, "price": Decimal("89.99")},
            {"productId": "P006", "name": "Yoga Mat — Non-Slip", "quantity": 1, "price": Decimal("34.99")},
        ],
        "total": Decimal("124.98"),
        "shippingAddress": "456 Oak Avenue, Seattle, WA 98101",
        "trackingNumber": None,
    },
    # Customer C003 — Carol White
    {
        "orderId": "ORD-1004",
        "customerId": "C003",
        "customerName": "Carol White",
        "customerEmail": "carol@example.com",
        "status": "delivered",
        "orderDate": days_ago(30),
        "deliveryDate": days_ago(25),
        "items": [
            {"productId": "P005", "name": "Portable Bluetooth Speaker", "quantity": 1, "price": Decimal("59.99")},
        ],
        "total": Decimal("59.99"),
        "shippingAddress": "789 Pine Road, Chicago, IL 60601",
        "trackingNumber": "UPS0011223344",
        "supportRequests": [
            {
                "ticketId": "TKT-ABCD1234",
                "requestType": "return",
                "reason": "Speaker stopped working after 2 weeks",
                "status": "open",
                "submittedAt": days_ago(5),
            }
        ],
    },
]

# ── Seed functions ─────────────────────────────────────────────────────────────

def seed_products():
    table = dynamodb.Table(PRODUCTS_TABLE)
    print(f"\nSeeding {len(PRODUCTS)} products into '{PRODUCTS_TABLE}'...")
    for product in PRODUCTS:
        table.put_item(Item=product)
        print(f"  ✓ {product['productId']} — {product['name']}")
    print(f"Products seeded successfully.")

def seed_orders():
    table = dynamodb.Table(ORDERS_TABLE)
    print(f"\nSeeding {len(ORDERS)} orders into '{ORDERS_TABLE}'...")
    for order in ORDERS:
        # Remove None values — DynamoDB doesn't accept null
        clean = {k: v for k, v in order.items() if v is not None}
        table.put_item(Item=clean)
        print(f"  ✓ {order['orderId']} — {order['customerId']} ({order['status']})")
    print(f"Orders seeded successfully.")

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"ShopSmart Seed Data")
    print(f"Region:      {REGION}")
    print(f"Environment: {ENVIRONMENT}")
    print(f"Orders table:   {ORDERS_TABLE}")
    print(f"Products table: {PRODUCTS_TABLE}")

    try:
        seed_products()
        seed_orders()
        print(f"\n✅ All done! Tables are ready for use.")
        print(f"\nTest customers:")
        print(f"  C001 — Alice Johnson (2 orders: delivered, shipped)")
        print(f"  C002 — Bob Smith     (1 order: processing)")
        print(f"  C003 — Carol White   (1 order: delivered, with return request)")
    except Exception as e:
        print(f"\n❌ Seed failed: {e}")
        print(f"Make sure the CloudFormation stack is deployed and your AWS credentials are configured.")
        sys.exit(1)
