"""
Lambda — get_order
Returns a single order by orderId.
"""
import json
import os
import boto3

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"])
table = dynamodb.Table(os.environ["ORDERS_TABLE"])


def lambda_handler(event, context):
    order_id = (event.get("pathParameters") or {}).get("orderId")

    if not order_id:
        return _response(400, {"error": "orderId path parameter is required"})

    result = table.get_item(Key={"orderId": order_id})
    order = result.get("Item")

    if not order:
        return _response(404, {"error": f"Order {order_id} not found"})

    return _response(200, order)


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }
