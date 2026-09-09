"""
Aria — ShopSmart AI Customer Support Agent
Module 04: Runtime with Knowledge Base

This is the production Aria agent built with Strands Agents and deployed
on Amazon Bedrock AgentCore Runtime. It retrieves answers from the
ShopSmart Knowledge Base rather than relying on a hardcoded system prompt.

This agent evolves throughout the course — each module adds new capabilities.
"""

import os
import boto3
from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# ── Configuration ─────────────────────────────────────────────────────────────

KNOWLEDGE_BASE_ID = os.environ.get("KNOWLEDGE_BASE_ID")
REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = "us.anthropic.claude-sonnet-4-6"

# ── Knowledge Base client ──────────────────────────────────────────────────────

bedrock_agent_runtime = boto3.client(
    "bedrock-agent-runtime",
    region_name=REGION
)

# ── Tools ──────────────────────────────────────────────────────────────────────

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
    if not KNOWLEDGE_BASE_ID:
        return "Knowledge base not configured."

    response = bedrock_agent_runtime.retrieve(
        knowledgeBaseId=KNOWLEDGE_BASE_ID,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {
                "numberOfResults": 5
            }
        }
    )

    results = response.get("retrievalResults", [])
    if not results:
        return "No relevant information found in the knowledge base."

    # Combine retrieved chunks into a single context string
    context = "\n\n".join([
        result["content"]["text"]
        for result in results
        if result.get("content", {}).get("text")
    ])

    return context


# ── System Prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Aria, the AI customer support agent for ShopSmart — a friendly online retail store.

Your role is to help customers with their shopping experience. Be warm, helpful, and concise.

## How to answer questions:
- Always use the retrieve_from_knowledge_base tool to look up ShopSmart's official policies and information
- Never make up information — if you cannot find an answer, say so honestly
- Keep responses concise — 2-3 sentences for simple questions
- If a customer needs help beyond what you know, suggest they contact live support

## What you can help with:
- Return and refund policy
- Shipping options and delivery times
- Payment methods
- Store hours and support contact
- General FAQs about orders and accounts
"""

# ── Agent ──────────────────────────────────────────────────────────────────────

agent = Agent(
    model=MODEL_ID,
    system_prompt=SYSTEM_PROMPT,
    tools=[retrieve_from_knowledge_base]
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

    return {"result": str(result.message)}


if __name__ == "__main__":
    app.run()
