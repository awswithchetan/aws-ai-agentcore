"""
ShopSmart — Aria Customer Support Chat UI

A Streamlit-based chat interface for interacting with the Aria agent.
Supports both AgentCore Runtime (Module 04+) and Harness (Module 02).

Usage:
    # For Runtime agent (Module 04+):
    export ARIA_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:<account>:runtime/aria-XXXXXXXX"
    export AWS_REGION="us-east-1"
    streamlit run app.py

    # For Harness agent (Module 02):
    export ARIA_HARNESS_ARN="arn:aws:bedrock-agentcore:us-east-1:<account>:harness/aria_harness-XXXXXXXX"
    export AWS_REGION="us-east-1"
    streamlit run app.py
"""

import os
import uuid
import json
import boto3
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="ShopSmart Support — Aria",
    page_icon="🛍️",
    layout="centered",
)

# ── Configuration ─────────────────────────────────────────────────────────────

RUNTIME_ARN = os.environ.get("ARIA_RUNTIME_ARN")
HARNESS_ARN = os.environ.get("ARIA_HARNESS_ARN")
REGION = os.environ.get("AWS_REGION", "us-east-1")

# Determine mode
if RUNTIME_ARN:
    MODE = "runtime"
elif HARNESS_ARN:
    MODE = "harness"
else:
    st.error(
        "**No agent ARN configured.**\n\n"
        "Set one of the following environment variables:\n"
        "```\n"
        "export ARIA_RUNTIME_ARN='arn:aws:bedrock-agentcore:...'\n"
        "# or\n"
        "export ARIA_HARNESS_ARN='arn:aws:bedrock-agentcore:...'\n"
        "```"
    )
    st.stop()

# ── AWS Client ────────────────────────────────────────────────────────────────

@st.cache_resource
def get_client():
    return boto3.client("bedrock-agentcore", region_name=REGION)

client = get_client()

# ── Session state ─────────────────────────────────────────────────────────────

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Header ────────────────────────────────────────────────────────────────────

st.title("🛍️ ShopSmart Support")
st.caption("Powered by Aria — Ask me about orders, returns, shipping, and more.")
st.divider()

# ── Display conversation history ──────────────────────────────────────────────

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# ── Welcome message on first load ─────────────────────────────────────────────

if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.write("Hi! I'm Aria, ShopSmart's virtual support agent. How can I help you today?")

# ── Invoke function ───────────────────────────────────────────────────────────

def invoke_aria(prompt: str) -> str:
    """Invoke Aria via Runtime or Harness depending on configuration."""

    if MODE == "runtime":
        response = client.invoke_agent_runtime(
            agentRuntimeArn=RUNTIME_ARN,
            runtimeSessionId=st.session_state.session_id,
            payload=json.dumps({"prompt": prompt}),
        )
        result = json.loads(response["response"].read())
        return result.get("result", "Sorry, I could not process your request.")

    else:  # harness
        response = client.invoke_harness(
            harnessArn=HARNESS_ARN,
            runtimeSessionId=st.session_state.session_id,
            messages=[{
                "role": "user",
                "content": [{"text": prompt}]
            }],
        )
        full_response = ""
        for event in response["stream"]:
            if "contentBlockDelta" in event:
                delta = event["contentBlockDelta"].get("delta", {})
                if "text" in delta:
                    full_response += delta["text"]
            elif "runtimeClientError" in event:
                return f"Error: {event['runtimeClientError']['message']}"
        return full_response

# ── Chat input ────────────────────────────────────────────────────────────────

if prompt := st.chat_input("Ask Aria something..."):
    with st.chat_message("user"):
        st.write(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("Aria is thinking..."):
            try:
                response = invoke_aria(prompt)
            except Exception as e:
                response = f"Unable to reach Aria right now. Please try again. ({str(e)})"
        st.write(response)

    st.session_state.messages.append({"role": "assistant", "content": response})

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Session Info")
    st.caption(f"Mode: `{MODE}`")
    st.caption(f"Session ID: `{st.session_state.session_id[:8]}...`")
    st.caption(f"Messages: {len(st.session_state.messages)}")
    st.divider()

    if st.button("🔄 New Session", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()
