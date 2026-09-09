"""
Lambda — submit_request
Submits a support request or return initiation for an order.
Writes the request to the orders table as a sub-item and returns a ticket ID.
"""
import json
import os
import uuid
import boto3
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"])
orders_table = dynamodb.Table(os.environ["ORDERS_TABLE"])

VALID_REQUEST_TYPES = {"return", "exchange", "complaint", "inquiry"}


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"error": "Invalid JSON body"})

    order_id = body.get("orderId")
    request_type = body.get("requestType", "").lower()
    reason = body.get("reason", "").strip()

    # Validate
    if not order_id:
        return _response(400, {"error": "'orderId' is required"})
    if request_type not in VALID_REQUEST_TYPES:
        return _response(400, {
            "error": f"'requestType' must be one of: {', '.join(sorted(VALID_REQUEST_TYPES))}"
        })
    if not reason:
        return _response(400, {"error": "'reason' is required"})

    # Verify order exists
    result = orders_table.get_item(Key={"orderId": order_id})
    if not result.get("Item"):
        return _response(404, {"error": f"Order {order_id} not found"})

    ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
    submitted_at = datetime.now(timezone.utc).isoformat()

    # Append the request ticket to the order record
    orders_table.update_item(
        Key={"orderId": order_id},
        UpdateExpression="SET supportRequests = list_append(if_not_exists(supportRequests, :empty), :req)",
        ExpressionAttributeValues={
            ":req": [{
                "ticketId": ticket_id,
                "requestType": request_type,
                "reason": reason,
                "status": "open",
                "submittedAt": submitted_at,
            }],
            ":empty": [],
        },
    )

    return _response(201, {
        "ticketId": ticket_id,
        "orderId": order_id,
        "requestType": request_type,
        "status": "open",
        "submittedAt": submitted_at,
        "message": f"Your {request_type} request has been submitted. Ticket ID: {ticket_id}",
    })


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }
