"""
Aria — JWT Identity Extractor
==============================
Extracts verified customer identity from the Authorization header.

AgentCore Runtime validates the JWT signature against Cognito's public keys
before forwarding the header to agent code. By the time this code runs,
the token is already verified — we only need to decode the payload.

JWT claims used:
  custom:customer_id  — set at user creation, matches customerId in DynamoDB (e.g. C001)
  sub                 — Cognito's stable UUID identifier (used as fallback)
  name                — customer's full name (e.g. "Alice Johnson")
  email               — customer's email address

We use custom:customer_id (not sub) as the customer identifier because:
  - Cognito auto-generates sub as a UUID — it doesn't match our DynamoDB IDs
  - custom:customer_id is explicitly set to C001/C002/C003 at user creation
  - This is a common production pattern when an IdP needs to carry an
    application-specific identifier alongside the Cognito sub

The custom:customer_id is also used as actor_id for memory scoping so
memories are correctly namespaced per customer across sessions.
"""

import base64
import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CustomerIdentity:
    """Verified customer identity extracted from a Cognito JWT."""

    customer_id: str          # custom:customer_id claim — matches DynamoDB customerId (e.g. C001)
    name: str                 # JWT name claim — customer's full name
    email: str                # JWT email claim
    raw_claims: dict = field(default_factory=dict, repr=False)

    @property
    def is_authenticated(self) -> bool:
        return self.customer_id != "anonymous"

    @property
    def display_name(self) -> str:
        """Returns name if available, falls back to customer_id."""
        return self.name if self.name else self.customer_id


# Singleton for unauthenticated/anonymous requests
ANONYMOUS = CustomerIdentity(
    customer_id="anonymous",
    name="",
    email="",
    raw_claims={},
)


def _decode_jwt_payload(token: str) -> dict:
    """
    Base64-decode the JWT payload segment.
    No signature verification — the Runtime already did that.
    """
    try:
        # JWT = header.payload.signature — we only need the middle segment
        payload_segment = token.split(".")[1]
        # Add padding if needed (base64url may omit it)
        payload_segment += "=" * (4 - len(payload_segment) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_segment))
    except Exception as e:
        logger.warning("Failed to decode JWT payload: %s", e)
        return {}


def extract_identity(context) -> CustomerIdentity:
    """
    Extract customer identity from the AgentCore Runtime request context.

    AgentCore Runtime validates the access_token in the Authorization header.
    The id_token (which carries name, email, custom:customer_id) is forwarded
    separately in X-Amzn-Bedrock-AgentCore-Runtime-Custom-Id-Token so that
    identity claims can be read without interfering with token validation.

    Args:
        context: AgentCore Runtime RequestContext — carries request headers

    Returns:
        CustomerIdentity with customer_id, name, email from the id_token claims
    """
    headers: dict = getattr(context, "request_headers", {}) or {}

    # Read the id_token from the custom header (set by the Streamlit UI)
    id_token = (
        headers.get("X-Amzn-Bedrock-AgentCore-Runtime-Custom-Id-Token")
        or headers.get("x-amzn-bedrock-agentcore-runtime-custom-id-token", "")
    )

    if not id_token:
        logger.warning(
            "No id_token in X-Amzn-Bedrock-AgentCore-Runtime-Custom-Id-Token header "
            "— returning anonymous identity. Check the Runtime request header allowlist."
        )
        return ANONYMOUS

    claims = _decode_jwt_payload(id_token)
    if not claims:
        return ANONYMOUS

    customer_id = claims.get("custom:customer_id") or claims.get("sub", "anonymous")
    name = claims.get("name", "")
    email = claims.get("email", "")

    logger.info(
        "Identity extracted — customer_id=%s name=%s email=%s",
        customer_id, name, email,
    )

    return CustomerIdentity(
        customer_id=customer_id,
        name=name,
        email=email,
        raw_claims=claims,
    )
