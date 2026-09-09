"""
Lambda — get_product
Returns a single product by productId.
"""
import json
import os
import boto3

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"])
table = dynamodb.Table(os.environ["PRODUCTS_TABLE"])


def lambda_handler(event, context):
    product_id = (event.get("pathParameters") or {}).get("productId")

    if not product_id:
        return _response(400, {"error": "productId path parameter is required"})

    result = table.get_item(Key={"productId": product_id})
    product = result.get("Item")

    if not product:
        return _response(404, {"error": f"Product {product_id} not found"})

    return _response(200, product)


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }
