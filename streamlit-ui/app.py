"""
ShopSmart — Aria Customer Support Chat UI
Module 07: Identity — Cognito login replaces manual Customer ID input

Changes from Module 06:
  - Sidebar Customer ID text input is replaced by Cognito login
  - Login redirects to Cognito Hosted UI (authorization code flow)
  - After login, the id_token is stored in session state
  - Every invoke_agent_runtime call sends Authorization: Bearer <id_token>
  - Customer name and email are shown in the sidebar from token claims
  - Sign out clears the token and redirects to Cognito logout endpoint

Usage:
    export ARIA_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:<account>:runtime/aria-XXXXXXXX"
    export AWS_REGION="us-east-1"
    streamlit run app.py

Cognito config is loaded from SSM (/aria/cognito_*) automatically.
"""

import base64
import json
import os
import urllib.parse
import uuid

import boto3
import requests as http_requests
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="ShopSmart Support — Aria",
    page_icon="🛍️",
    layout="centered",
)

# ── Configuration ─────────────────────────────────────────────────────────────

RUNTIME_ARN = os.environ.get("ARIA_RUNTIME_ARN")
REGION = os.environ.get("AWS_REGION", "us-east-1")

if not RUNTIME_ARN:
    st.error(
        "**No agent ARN configured.**\n\n"
        "Set the following environment variable:\n"
        "```\n"
        "export ARIA_RUNTIME_ARN='arn:aws:bedrock-agentcore:...'\n"
        "```"
    )
    st.stop()

# ── Load Cognito config from SSM ──────────────────────────────────────────────

@st.cache_resource
def load_cognito_config():
    """Load Cognito parameters from SSM. Cached for the lifetime of the app."""
    try:
        ssm = boto3.client("ssm", region_name=REGION)
        paginator = ssm.get_paginator("get_parameters_by_path")
        params = {}
        for page in paginator.paginate(Path="/aria", WithDecryption=True):
            for p in page["Parameters"]:
                key = p["Name"].removeprefix("/aria/")
                params[key] = p["Value"]
        return {
            "user_pool_id": params.get("cognito_user_pool_id", ""),
            "client_id": params.get("cognito_client_id", ""),
            "domain": params.get("cognito_domain", "").rstrip("/"),
        }
    except Exception:
        # Fall back to env vars for local dev
        return {
            "user_pool_id": os.environ.get("COGNITO_USER_POOL_ID", ""),
            "client_id": os.environ.get("COGNITO_CLIENT_ID", ""),
            "domain": os.environ.get("COGNITO_DOMAIN", "").rstrip("/"),
        }

cognito = load_cognito_config()

REDIRECT_URI = "http://localhost:8501"

# ── AgentCore endpoint ────────────────────────────────────────────────────────
# When the runtime is configured with a JWT authorizer, Boto3 cannot pass a
# Bearer token — invocation must be made over plain HTTPS using the requests
# library. SigV4-signed Boto3 calls are only used when there is no JWT auth.

AGENTCORE_BASE_URL = f"https://bedrock-agentcore.{REGION}.amazonaws.com"

# ── JWT helpers ───────────────────────────────────────────────────────────────

def decode_jwt_payload(token: str) -> dict:
    """Decode the JWT payload (no signature verification — Runtime handles that)."""
    try:
        segment = token.split(".")[1]
        segment += "=" * (4 - len(segment) % 4)
        return json.loads(base64.urlsafe_b64decode(segment))
    except Exception:
        return {}

# ── Session state ─────────────────────────────────────────────────────────────

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "id_token" not in st.session_state:
    st.session_state.id_token = None        # used for reading user claims (name, email, custom:customer_id)
if "access_token" not in st.session_state:
    st.session_state.access_token = None    # used for invoking the runtime (has client_id claim)
if "user_claims" not in st.session_state:
    st.session_state.user_claims = {}

# ── Handle Cognito callback (authorization code exchange) ──────────────────────

query_params = st.query_params
if "code" in query_params and not st.session_state.id_token:
    code = query_params["code"]
    try:
        token_endpoint = f"{cognito['domain']}/oauth2/token"
        resp = http_requests.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "client_id": cognito["client_id"],
                "code": code,
                "redirect_uri": REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        resp.raise_for_status()
        tokens = resp.json()
        # id_token: used to read user identity claims (name, email, custom:customer_id)
        # access_token: used to invoke the runtime — contains the client_id claim
        #               that AgentCore's JWT authorizer validates against allowedClients
        st.session_state.id_token = tokens.get("id_token")
        st.session_state.access_token = tokens.get("access_token")
        if st.session_state.id_token:
            st.session_state.user_claims = decode_jwt_payload(st.session_state.id_token)
        # Clear the code from the URL to avoid re-exchanging on refresh
        st.query_params.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Login failed: {str(e)}")
        st.query_params.clear()

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
        if st.session_state.id_token:
            name = st.session_state.user_claims.get("name", "")
            greeting = f"Hi {name}! " if name else "Hi! "
        else:
            greeting = "Hi! "
        st.write(f"{greeting}I'm Aria, ShopSmart's virtual support agent. How can I help you today?")

# ── Invoke function ───────────────────────────────────────────────────────────

def invoke_aria(prompt: str) -> str:
    """Invoke Aria via AgentCore Runtime HTTPS endpoint, passing the JWT as a Bearer token.

    Boto3 does not support passing a Bearer token to invoke_agent_runtime — it
    only uses SigV4 signing. When the runtime is configured with a JWT
    authorizer, the invocation must go over plain HTTPS with an Authorization
    header.

    The access_token (not id_token) is used here because AgentCore's JWT
    authorizer validates the client_id claim against allowedClients — that
    claim is only present in the access_token. The id_token is used separately
    to read user identity claims (name, email) for display purposes.
    """
    if not st.session_state.access_token:
        return "Please sign in to chat with Aria."

    payload = {"prompt": prompt}

    # URL-encode the runtime ARN for use in the path
    escaped_arn = urllib.parse.quote(RUNTIME_ARN, safe="")
    url = f"{AGENTCORE_BASE_URL}/runtimes/{escaped_arn}/invocations?qualifier=DEFAULT"

    headers = {
        "Authorization": f"Bearer {st.session_state.access_token}",
        # Pass the id_token as a custom header so agent.py can extract
        # identity claims (name, email, custom:customer_id) from it.
        # The Authorization header carries the access_token which contains
        # the client_id claim that AgentCore's JWT authorizer validates.
        "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Id-Token": st.session_state.id_token or "",
        "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": st.session_state.session_id,
    }

    try:
        resp = http_requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=60,
        )
        if resp.status_code == 401:
            # Show the raw error before logging out so we can debug
            return f"[401 Unauthorized] Response body: {resp.text[:500]}"
        if not resp.ok:
            return f"[HTTP {resp.status_code}] Response body: {resp.text[:500]}"
        result = resp.json()
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
    st.header("ShopSmart Account")

    if st.session_state.id_token:
        # Logged in
        name = st.session_state.user_claims.get("name", "")
        email = st.session_state.user_claims.get("email", "")
        customer_id = st.session_state.user_claims.get("sub", "")

        st.success(f"👤 **{name}**")
        if email:
            st.caption(email)
        st.caption(f"Customer ID: `{customer_id}`")
        st.divider()

        if st.button("Sign out", use_container_width=True):
            logout_url = (
                f"{cognito['domain']}/logout"
                f"?client_id={cognito['client_id']}"
                f"&logout_uri={urllib.parse.quote(REDIRECT_URI)}"
            )
            st.session_state.id_token = None
            st.session_state.access_token = None
            st.session_state.user_claims = {}
            st.session_state.messages = []
            st.session_state.session_id = str(uuid.uuid4())
            st.markdown(f'<meta http-equiv="refresh" content="0; url={logout_url}">', unsafe_allow_html=True)

    else:
        # Not logged in
        st.info("Sign in to access your orders and account.")

        if cognito["domain"] and cognito["client_id"]:
            login_url = (
                f"{cognito['domain']}/login"
                f"?response_type=code"
                f"&client_id={cognito['client_id']}"
                f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
                f"&scope=openid+email+profile"
            )
            st.markdown(
                f'<a href="{login_url}" target="_self">'
                f'<button style="width:100%;padding:8px;background:#FF9900;border:none;'
                f'border-radius:4px;color:white;font-weight:bold;cursor:pointer;">'
                f'Sign in with ShopSmart</button></a>',
                unsafe_allow_html=True,
            )
        else:
            st.warning(
                "Cognito not configured. Set `/aria/cognito_*` SSM parameters "
                "or set `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, `COGNITO_DOMAIN` env vars."
            )

    st.divider()
    st.header("Session Info")
    st.caption(f"Session ID: `{st.session_state.session_id[:8]}...`")
    st.caption(f"Messages: {len(st.session_state.messages)}")
    st.divider()

    if st.button("🔄 New Session", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()
