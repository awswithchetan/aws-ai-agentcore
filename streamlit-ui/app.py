"""
ShopSmart — Aria Customer Support Chat UI

A Streamlit-based chat interface for interacting with the Aria
AgentCore Harness. Maintains conversation history and session state
across turns within the same browser session.

Usage:
    export ARIA_HARNESS_ARN="arn:aws:bedrock-agentcore:us-east-1:<account>:harness/aria-XyZ123"
    export AWS_REGION="us-east-1"
    streamlit run app.py
"""

import os
import uuid
import boto3
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="ShopSmart Support — Aria",
    page_icon="🛍️",
    layout="centered",
)

# ── Configuration ─────────────────────────────────────────────────────────────

HARNESS_ARN = os.environ.get("ARIA_HARNESS_ARN")
REGION = os.environ.get("AWS_REGION", "us-east-1")

if not HARNESS_ARN:
    st.error(
        "**ARIA_HARNESS_ARN environment variable is not set.**\n\n"
        "Run the app with:\n"
        "```\nexport ARIA_HARNESS_ARN='arn:aws:bedrock-agentcore:...'\n"
        "streamlit run app.py\n```"
    )
    st.stop()

# ── AWS Client ────────────────────────────────────────────────────────────────

@st.cache_resource
def get_client():
    return boto3.client("bedrock-agentcore", region_name=REGION)


client = get_client()

# ── Session state initialisation ──────────────────────────────────────────────

if "session_id" not in st.session_state:
    # Must be at least 33 characters
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

# ── Chat input ────────────────────────────────────────────────────────────────

if prompt := st.chat_input("Ask Aria something..."):
    # Display user message
    with st.chat_message("user"):
        st.write(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Invoke Aria and stream the response
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""

        try:
            response = client.invoke_harness(
                harnessArn=HARNESS_ARN,
                runtimeSessionId=st.session_state.session_id,
                messages=[{
                    "role": "user",
                    "content": [{"text": prompt}]
                }],
            )

            for event in response["stream"]:
                if "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"].get("delta", {})
                    if "text" in delta:
                        full_response += delta["text"]
                        response_placeholder.write(full_response + "▌")
                elif "runtimeClientError" in event:
                    error_msg = event["runtimeClientError"]["message"]
                    full_response = f"Sorry, something went wrong: {error_msg}"
                    break

            response_placeholder.write(full_response)

        except Exception as e:
            full_response = f"Unable to reach Aria right now. Please try again. ({str(e)})"
            response_placeholder.write(full_response)

    st.session_state.messages.append({"role": "assistant", "content": full_response})

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Session Info")
    st.caption(f"Session ID: `{st.session_state.session_id[:8]}...`")
    st.caption(f"Messages: {len(st.session_state.messages)}")
    st.divider()

    if st.button("🔄 New Session", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.caption("**Module 02** — Harness (FAQ only)")
    st.caption("Tools: None (added in Module 04)")
