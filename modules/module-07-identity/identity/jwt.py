"""
Aria — JWT Identity Extractor
==============================
Extracts verified customer identity from the Authorization header.

AgentCore Runtime validates the JWT signature against Cognito's public keys
before forwarding the header to agent code. By the time this code runs,
the token is already verified — we only need to decode the payload.

JWT claims used:
  sub    — stable user identifier, matches customerId in DynamoDB (e.g. C001)
  name   — customer's full name (e.g. "Alice Johnson")
  email  — customer's email address

The `sub` claim is used as actor_id for memory scoping so memories are
correctly namespaced per customer across sessions.
"""

import base64
import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CustomerIdentity:
    """Verified customer identity extracted from a Cognito JWT."""

    customer_id: str          # JWT sub — stable identifier, matches DynamoDB customerId
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

    Reads the Authorization header forwarded by the Runtime, decodes the
    JWT payload, and returns a CustomerIdentity. Returns ANONYMOUS if no
    valid Bearer token is present.

    Args:
        context: AgentCore Runtime RequestContext — carries request headers

    Returns:
        CustomerIdentity with sub, name, email from the JWT claims
    """
    headers: dict = getattr(context, "request_headers", {}) or {}

    # Header names are case-insensitive
    auth = headers.get("Authorization") or headers.get("authorization", "")

    if not auth.startswith("Bearer "):
        logger.warning(
            "No Bearer token in Authorization header — returning anonymous identity. "
            "Check that 'Authorization' is in the Runtime request header allowlist."
        )
        return ANONYMOUS

    token = auth.split(" ", 1)[1].strip()
    if not token:
        logger.warning("Empty Bearer token — returning anonymous identity.")
        return ANONYMOUS

    claims = _decode_jwt_payload(token)
    if not claims:
        return ANONYMOUS

    customer_id = claims.get("sub", "anonymous")
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
