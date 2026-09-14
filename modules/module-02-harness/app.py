"""
Module 02 — ShopSmart Aria Harness chat UI.

Usage:
    export ARIA_HARNESS_ARN="arn:aws:bedrock-agentcore:us-east-1:<account>:harness/aria_harness-XXXXXXXX"
    export AWS_REGION="us-east-1"
    streamlit run streamlit-ui/app.py
"""

import os
import uuid

import boto3
import streamlit as st


st.set_page_config(
    page_title="ShopSmart Support — Aria",
    page_icon="🛍️",
    layout="centered",
)

HARNESS_ARN = os.environ.get("ARIA_HARNESS_ARN")
REGION = os.environ.get("AWS_REGION", "us-east-1")

if not HARNESS_ARN:
    st.error(
        "**No Harness ARN configured.**\n\n"
        "Set the Harness ARN before starting Streamlit:\n"
        "```bash\n"
        "export ARIA_HARNESS_ARN='arn:aws:bedrock-agentcore:...'\n"
        "```"
    )
    st.stop()


@st.cache_resource
def get_client():
    return boto3.client("bedrock-agentcore", region_name=REGION)


client = get_client()

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []


st.title("🛍️ ShopSmart Support")
st.caption("Powered by Aria — Ask me about returns, shipping, and payments.")
st.divider()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.write("Hi! I'm Aria, ShopSmart's virtual support agent. How can I help you today?")


def invoke_aria(prompt: str) -> str:
    """Invoke the Module 02 Harness and collect its streamed response."""
    response = client.invoke_harness(
        harnessArn=HARNESS_ARN,
        runtimeSessionId=st.session_state.session_id,
        messages=[{
            "role": "user",
            "content": [{"text": prompt}],
        }],
    )

    chunks = []
    for event in response["stream"]:
        if "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})
            if "text" in delta:
                chunks.append(delta["text"])
        elif "runtimeClientError" in event:
            return f"Error from Aria: {event['runtimeClientError']['message']}"

    return "".join(chunks) or "Sorry, I could not process your request."


if prompt := st.chat_input("Ask Aria something..."):
    with st.chat_message("user"):
        st.write(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("Aria is thinking..."):
            try:
                response = invoke_aria(prompt)
            except Exception as exc:
                response = f"Unable to reach Aria right now. Please try again. ({exc})"
        st.write(response)

    st.session_state.messages.append({"role": "assistant", "content": response})


with st.sidebar:
    st.header("Session Info")
    st.caption("Mode: `harness`")
    st.caption(f"Session ID: `{st.session_state.session_id[:8]}...`")
    st.caption(f"Messages: {len(st.session_state.messages)}")
    st.divider()

    if st.button("🔄 New Session", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()
