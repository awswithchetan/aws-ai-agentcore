"""
Aria — Configuration Loader
============================
Loads agent configuration from AWS Systems Manager (SSM) Parameter Store.
Falls back to environment variables so local development works without SSM.

Production layout (all parameters under /aria/):
  /aria/model_id          — Bedrock model ID (e.g. us.anthropic.claude-sonnet-4-6)
  /aria/knowledge_base_id — Bedrock Knowledge Base ID
  /aria/kb_num_results    — Number of KB chunks to retrieve per query
  /aria/region            — AWS region

Why SSM instead of env vars for these values?
  - Model upgrades and KB replacements are configuration changes, not code changes.
  - Changing an env var requires a container redeploy; changing an SSM parameter does not.
  - SSM gives you an audit trail (who changed what, when) out of the box.
  - SSM SecureString can be used for sensitive values without Secrets Manager overhead.

Local development:
  Set the equivalent environment variables and SSM loading is skipped automatically
  (SSM_ENABLED=false), or just leave SSM_ENABLED unset — the fallback chain handles it.

Environment variables (fallback / local dev):
  SSM_ENABLED        — Set to "false" to skip SSM entirely (default: "true")
  SSM_PREFIX         — Override the SSM path prefix (default: /aria)
  MODEL_ID           — Fallback model ID
  KNOWLEDGE_BASE_ID  — Fallback Knowledge Base ID
  KB_NUM_RESULTS     — Fallback retrieval result count (default: 5)
  AWS_REGION         — AWS region (default: us-east-1)
"""

import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# ── Defaults ──────────────────────────────────────────────────────────────────

_DEFAULTS = {
    "model_id": "us.anthropic.claude-sonnet-4-6",
    "knowledge_base_id": "",
    "kb_num_results": "5",
    "region": "us-east-1",
}

# ── Internal helpers ──────────────────────────────────────────────────────────

def _ssm_enabled() -> bool:
    return os.environ.get("SSM_ENABLED", "true").lower() != "false"


def _ssm_prefix() -> str:
    return os.environ.get("SSM_PREFIX", "/aria").rstrip("/")


def _load_from_ssm(region: str) -> dict:
    """
    Fetch all parameters under the /aria/ prefix in a single API call.
    Returns a dict keyed by the last path segment (e.g. 'model_id').
    Returns an empty dict on any error so the fallback chain still works.
    """
    prefix = _ssm_prefix()
    try:
        client = boto3.client("ssm", region_name=region)
        paginator = client.get_paginator("get_parameters_by_path")
        params = {}
        for page in paginator.paginate(
            Path=prefix,
            Recursive=False,
            WithDecryption=True,  # handles SecureString transparently
        ):
            for p in page["Parameters"]:
                key = p["Name"].removeprefix(prefix + "/")
                params[key] = p["Value"]
        if params:
            logger.info("Loaded %d parameter(s) from SSM prefix '%s'", len(params), prefix)
        else:
            logger.warning("No parameters found at SSM prefix '%s' — using fallbacks", prefix)
        return params
    except ClientError as e:
        logger.warning("SSM unavailable (%s) — using environment variable fallbacks", e.response["Error"]["Code"])
        return {}
    except Exception as e:  # noqa: BLE001
        logger.warning("SSM load failed (%s) — using environment variable fallbacks", e)
        return {}


def _resolve(key: str, ssm: dict) -> str:
    """
    Resolution order:
      1. SSM Parameter Store  (when SSM_ENABLED=true)
      2. Environment variable (upper-case key name)
      3. Hard-coded default
    """
    env_key = key.upper()
    value = ssm.get(key) or os.environ.get(env_key) or _DEFAULTS.get(key, "")
    return value


# ── Public API ────────────────────────────────────────────────────────────────

class AgentConfig:
    """
    Immutable configuration snapshot loaded once at agent startup.
    Access values as attributes: cfg.model_id, cfg.knowledge_base_id, etc.
    """

    def __init__(self):
        region = os.environ.get("AWS_REGION", _DEFAULTS["region"])
        ssm = _load_from_ssm(region) if _ssm_enabled() else {}

        self.region: str = region
        self.model_id: str = _resolve("model_id", ssm)
        self.knowledge_base_id: str = _resolve("knowledge_base_id", ssm)
        self.kb_num_results: int = int(_resolve("kb_num_results", ssm))

        self._validate()

    def _validate(self):
        if not self.model_id:
            raise ValueError("Configuration error: 'model_id' is required but not set.")
        if self.kb_num_results < 1 or self.kb_num_results > 20:
            raise ValueError(
                f"Configuration error: 'kb_num_results' must be between 1 and 20, got {self.kb_num_results}."
            )
        if not self.knowledge_base_id:
            logger.warning(
                "Configuration warning: 'knowledge_base_id' is not set. "
                "Knowledge base retrieval will be disabled."
            )

    def __repr__(self):
        return (
            f"AgentConfig("
            f"region={self.region!r}, "
            f"model_id={self.model_id!r}, "
            f"knowledge_base_id={'<set>' if self.knowledge_base_id else '<not set>'!r}, "
            f"kb_num_results={self.kb_num_results}"
            f")"
        )


# Module-level singleton — loaded once when the container starts.
# Import this in agent.py: from config import cfg
cfg = AgentConfig()
