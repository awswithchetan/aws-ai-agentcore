"""
ShopSmart — Seed Data Script
=============================
Populates the DynamoDB orders and products tables with realistic sample data.

Run this once after deploying the CloudFormation stack:

    export AWS_REGION=us-east-1
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
ORDERS_TABLE = "shopsmart-orders"
PRODUCTS_TABLE = "shopsmart-products"

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
    # ── Customer C001 — Alice Johnson ──────────────────────────────────────────
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
    {
        "orderId": "ORD-1003",
        "customerId": "C001",
        "customerName": "Alice Johnson",
        "customerEmail": "alice@example.com",
        "status": "processing",
        "orderDate": days_ago(1),
        "estimatedDelivery": days_from_now(6),
        "items": [
            {"productId": "P006", "name": "Yoga Mat — Non-Slip", "quantity": 1, "price": Decimal("34.99")},
        ],
        "total": Decimal("34.99"),
        "shippingAddress": "123 Maple Street, Austin, TX 78701",
        "trackingNumber": None,
    },
    {
        # High-value order (> $500) — for order-value policy control flows
        "orderId": "ORD-1004",
        "customerId": "C001",
        "customerName": "Alice Johnson",
        "customerEmail": "alice@example.com",
        "status": "delivered",
        "orderDate": days_ago(20),
        "deliveryDate": days_ago(14),
        "items": [
            {"productId": "P002", "name": "Wireless Noise-Cancelling Headphones", "quantity": 4, "price": Decimal("129.99")},
        ],
        "total": Decimal("519.96"),
        "shippingAddress": "123 Maple Street, Austin, TX 78701",
        "trackingNumber": "UPS5566778899",
    },
    {
        # Delivered order with an open return request — for return flows
        "orderId": "ORD-1005",
        "customerId": "C001",
        "customerName": "Alice Johnson",
        "customerEmail": "alice@example.com",
        "status": "delivered",
        "orderDate": days_ago(12),
        "deliveryDate": days_ago(7),
        "items": [
            {"productId": "P004", "name": "Running Shoes — Men's", "quantity": 1, "price": Decimal("89.99")},
        ],
        "total": Decimal("89.99"),
        "shippingAddress": "123 Maple Street, Austin, TX 78701",
        "trackingNumber": "FDX1122334455",
        "supportRequests": [
            {
                "ticketId": "TKT-ALICE001",
                "requestType": "return",
                "reason": "Shoes were too small",
                "status": "open",
                "submittedAt": days_ago(2),
            }
        ],
    },

    # ── Customer C002 — Bob Smith ──────────────────────────────────────────────
    {
        "orderId": "ORD-1006",
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
    {
        "orderId": "ORD-1007",
        "customerId": "C002",
        "customerName": "Bob Smith",
        "customerEmail": "bob@example.com",
        "status": "shipped",
        "orderDate": days_ago(4),
        "estimatedDelivery": days_from_now(3),
        "items": [
            {"productId": "P001", "name": "Classic Blue Backpack", "quantity": 1, "price": Decimal("49.99")},
        ],
        "total": Decimal("49.99"),
        "shippingAddress": "456 Oak Avenue, Seattle, WA 98101",
        "trackingNumber": "UPS2468013579",
    },
    {
        "orderId": "ORD-1008",
        "customerId": "C002",
        "customerName": "Bob Smith",
        "customerEmail": "bob@example.com",
        "status": "delivered",
        "orderDate": days_ago(18),
        "deliveryDate": days_ago(13),
        "items": [
            {"productId": "P003", "name": "Stainless Steel Water Bottle", "quantity": 1, "price": Decimal("24.99")},
        ],
        "total": Decimal("24.99"),
        "shippingAddress": "456 Oak Avenue, Seattle, WA 98101",
        "trackingNumber": "FDX3692581470",
    },
    {
        # High-value order (> $500) — for order-value policy control flows
        "orderId": "ORD-1009",
        "customerId": "C002",
        "customerName": "Bob Smith",
        "customerEmail": "bob@example.com",
        "status": "shipped",
        "orderDate": days_ago(5),
        "estimatedDelivery": days_from_now(1),
        "items": [
            {"productId": "P002", "name": "Wireless Noise-Cancelling Headphones", "quantity": 3, "price": Decimal("129.99")},
            {"productId": "P005", "name": "Portable Bluetooth Speaker", "quantity": 2, "price": Decimal("59.99")},
        ],
        "total": Decimal("509.95"),
        "shippingAddress": "456 Oak Avenue, Seattle, WA 98101",
        "trackingNumber": "UPS7418529630",
    },
    {
        "orderId": "ORD-1010",
        "customerId": "C002",
        "customerName": "Bob Smith",
        "customerEmail": "bob@example.com",
        "status": "cancelled",
        "orderDate": days_ago(9),
        "items": [
            {"productId": "P005", "name": "Portable Bluetooth Speaker", "quantity": 1, "price": Decimal("59.99")},
        ],
        "total": Decimal("59.99"),
        "shippingAddress": "456 Oak Avenue, Seattle, WA 98101",
        "trackingNumber": None,
    },

    # ── Customer C003 — Carol White ────────────────────────────────────────────
    {
        # Delivered order with an open return request — for return flows
        "orderId": "ORD-1011",
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
    {
        "orderId": "ORD-1012",
        "customerId": "C003",
        "customerName": "Carol White",
        "customerEmail": "carol@example.com",
        "status": "delivered",
        "orderDate": days_ago(22),
        "deliveryDate": days_ago(17),
        "items": [
            {"productId": "P001", "name": "Classic Blue Backpack", "quantity": 1, "price": Decimal("49.99")},
            {"productId": "P003", "name": "Stainless Steel Water Bottle", "quantity": 1, "price": Decimal("24.99")},
        ],
        "total": Decimal("74.98"),
        "shippingAddress": "789 Pine Road, Chicago, IL 60601",
        "trackingNumber": "FDX8520741963",
    },
    {
        "orderId": "ORD-1013",
        "customerId": "C003",
        "customerName": "Carol White",
        "customerEmail": "carol@example.com",
        "status": "shipped",
        "orderDate": days_ago(2),
        "estimatedDelivery": days_from_now(4),
        "items": [
            {"productId": "P006", "name": "Yoga Mat — Non-Slip", "quantity": 2, "price": Decimal("34.99")},
        ],
        "total": Decimal("69.98"),
        "shippingAddress": "789 Pine Road, Chicago, IL 60601",
        "trackingNumber": "UPS9513574862",
    },
    {
        "orderId": "ORD-1014",
        "customerId": "C003",
        "customerName": "Carol White",
        "customerEmail": "carol@example.com",
        "status": "processing",
        "orderDate": days_ago(1),
        "estimatedDelivery": days_from_now(7),
        "items": [
            {"productId": "P004", "name": "Running Shoes — Men's", "quantity": 1, "price": Decimal("89.99")},
        ],
        "total": Decimal("89.99"),
        "shippingAddress": "789 Pine Road, Chicago, IL 60601",
        "trackingNumber": None,
    },
    {
        "orderId": "ORD-1015",
        "customerId": "C003",
        "customerName": "Carol White",
        "customerEmail": "carol@example.com",
        "status": "delivered",
        "orderDate": days_ago(40),
        "deliveryDate": days_ago(35),
        "items": [
            {"productId": "P002", "name": "Wireless Noise-Cancelling Headphones", "quantity": 1, "price": Decimal("129.99")},
        ],
        "total": Decimal("129.99"),
        "shippingAddress": "789 Pine Road, Chicago, IL 60601",
        "trackingNumber": "FDX1593574862",
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
    print(f"Orders table:   {ORDERS_TABLE}")
    print(f"Products table: {PRODUCTS_TABLE}")

    try:
        seed_products()
        seed_orders()
        print(f"\n✅ All done! Tables are ready for use.")
        print(f"\nTest customers (5 orders each):")
        print(f"  C001 — Alice Johnson (delivered, shipped, processing, delivered >$500, delivered + open return)")
        print(f"  C002 — Bob Smith     (processing, shipped, delivered, shipped >$500, cancelled)")
        print(f"  C003 — Carol White   (delivered + open return, delivered, shipped, processing, delivered)")
        print(f"\nHigh-value orders (> $500, for order-value policy flows): ORD-1004 (C001), ORD-1009 (C002)")
    except Exception as e:
        print(f"\n❌ Seed failed: {e}")
        print(f"Make sure the CloudFormation stack is deployed and your AWS credentials are configured.")
        sys.exit(1)
