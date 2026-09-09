"""
Lambda — search_products
Searches products by keyword against name and description.
Uses a DynamoDB scan with filter expressions — suitable for a small catalog.
"""
import json
import os
import boto3
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["PRODUCTS_TABLE"])


def lambda_handler(event, context):
    params = event.get("queryStringParameters") or {}
    keyword = params.get("q", "").strip().lower()
    category = params.get("category", "").strip()

    if not keyword and not category:
        return _response(400, {"error": "At least one of 'q' or 'category' query parameters is required"})

    filter_expr = None

    if keyword:
        keyword_filter = (
            Attr("nameLower").contains(keyword) |
            Attr("descriptionLower").contains(keyword)
        )
        filter_expr = keyword_filter

    if category:
        category_filter = Attr("category").eq(category)
        filter_expr = category_filter if filter_expr is None else filter_expr & category_filter

    result = table.scan(FilterExpression=filter_expr)
    products = result.get("Items", [])

    # Remove internal lowercase fields used for search
    for p in products:
        p.pop("nameLower", None)
        p.pop("descriptionLower", None)

    return _response(200, {"products": products, "count": len(products)})


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }
