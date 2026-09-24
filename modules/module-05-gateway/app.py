"""
ShopSmart — Aria Customer Support Chat UI
Module 05: Gateway — Runtime invocation

Aria now reaches real tools through AgentCore Gateway. Since the agent does
not yet know who the customer is (that arrives with Memory in Module 06 and
Identity in Module 07), it simply asks for the customer ID in the conversation
when it needs one. The UI stays a plain chat interface.

Usage:
    export AWS_REGION="us-east-1"
    streamlit run app.py
"""

import json
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

REGION = os.environ.get("AWS_REGION", "us-east-1")

@st.cache_resource
def load_runtime_arn() -> str:
    """Load the Runtime ARN from SSM (/aria/runtime_arn), fallback to env var."""
    try:
        ssm = boto3.client("ssm", region_name=REGION)
        return ssm.get_parameter(Name="/aria/runtime_arn")["Parameter"]["Value"]
    except Exception:
        return os.environ.get("ARIA_RUNTIME_ARN", "")

RUNTIME_ARN = load_runtime_arn()

if not RUNTIME_ARN:
    st.error(
        "**No agent ARN configured.**\n\n"
        "Either add it to SSM Parameter Store:\n"
        "```\n"
        "export RUNTIME_ARN='arn:aws:bedrock-agentcore:...'\n"
        "bash aria-agent/scripts/put_ssm_params.sh\n"
        "```\n"
        "Or set the environment variable directly:\n"
        "```\n"
        "export ARIA_RUNTIME_ARN='arn:aws:bedrock-agentcore:...'\n"
        "```"
    )
    st.stop()

# ── AWS client ────────────────────────────────────────────────────────────────

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
    """Invoke Aria via AgentCore Runtime using SigV4 (Boto3)."""
    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=RUNTIME_ARN,
            runtimeSessionId=st.session_state.session_id,
            payload=json.dumps({"prompt": prompt}),
        )
        result = json.loads(response["response"].read())
        return result.get("result", "Sorry, I could not process your request.")
    except Exception as e:
        return f"Unable to reach Aria right now. Please try again. ({str(e)})"

# ── Chat input ────────────────────────────────────────────────────────────────

if prompt := st.chat_input("Ask Aria something..."):
    with st.chat_message("user"):
        st.write(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("Aria is thinking..."):
            response = invoke_aria(prompt)
        st.write(response)

    st.session_state.messages.append({"role": "assistant", "content": response})

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
