"""
Module 02 — Invoke Aria via Python

This script demonstrates how to invoke the AgentCore Harness
directly using boto3. It maintains a session across multiple turns
so Aria remembers the conversation context.

Usage:
    export ARIA_HARNESS_ARN="arn:aws:bedrock-agentcore:us-east-1:<account>:harness/aria-XyZ123"
    export AWS_REGION="us-east-1"
    python invoke_aria.py
"""

import os
import uuid
import boto3

# ── Configuration ─────────────────────────────────────────────────────────────

HARNESS_ARN = os.environ.get("ARIA_HARNESS_ARN")
REGION = os.environ.get("AWS_REGION", "us-east-1")

if not HARNESS_ARN:
    raise ValueError(
        "ARIA_HARNESS_ARN environment variable is not set.\n"
        "Run: export ARIA_HARNESS_ARN='arn:aws:bedrock-agentcore:...'"
    )

# ── Client ────────────────────────────────────────────────────────────────────

client = boto3.client("bedrock-agentcore", region_name=REGION)

# ── Session ID ────────────────────────────────────────────────────────────────
# Reuse the same session ID across turns to keep the conversation in the
# same environment. Must be at least 33 characters.

session_id = str(uuid.uuid4())  # e.g. "550e8400-e29b-41d4-a716-446655440000"
print(f"Session ID: {session_id}\n")


# ── Invoke function ───────────────────────────────────────────────────────────

def invoke_aria(user_message: str) -> str:
    """
    Send a message to Aria and return the full streamed response.
    """
    response = client.invoke_harness(
        harnessArn=HARNESS_ARN,
        runtimeSessionId=session_id,
        messages=[{
            "role": "user",
            "content": [{"text": user_message}]
        }],
    )

    full_response = ""

    for event in response["stream"]:
        if "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})
            if "text" in delta:
                chunk = delta["text"]
                print(chunk, end="", flush=True)
                full_response += chunk
        elif "runtimeClientError" in event:
            error_msg = event["runtimeClientError"]["message"]
            print(f"\nError from Aria: {error_msg}")
            return error_msg

    print()  # newline after streamed response
    return full_response


# ── Multi-turn conversation loop ──────────────────────────────────────────────

def main():
    print("=" * 50)
    print("ShopSmart — Aria Customer Support")
    print("Type 'quit' or 'exit' to end the session")
    print("=" * 50)
    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        print("Aria: ", end="")
        invoke_aria(user_input)
        print()


if __name__ == "__main__":
    main()
