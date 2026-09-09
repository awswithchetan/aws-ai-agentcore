"""
Lambda — list_orders
Returns all orders for a given customer ID.
"""
import json
import os
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["ORDERS_TABLE"])


def lambda_handler(event, context):
    customer_id = event.get("queryStringParameters", {}) or {}
    customer_id = customer_id.get("customerId")

    if not customer_id:
        return _response(400, {"error": "customerId query parameter is required"})

    result = table.query(
        IndexName="customerId-index",
        KeyConditionExpression=Key("customerId").eq(customer_id),
    )

    orders = result.get("Items", [])
    return _response(200, {"orders": orders, "count": len(orders)})


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }
