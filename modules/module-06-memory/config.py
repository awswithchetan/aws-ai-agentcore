"""
Aria — Configuration Loader
============================
Module 06 adds memory_id and memory_strategy_id for AgentCore Memory.
Tools are routed through the Gateway (gateway_endpoint) as of Module 05.

SSM Parameters (all under /aria/):
  /aria/model_id            — Bedrock model ID
  /aria/knowledge_base_id   — Bedrock Knowledge Base ID
  /aria/kb_num_results      — Number of KB chunks per query
  /aria/region              — AWS region
  /aria/gateway_endpoint    — AgentCore Gateway MCP endpoint URL
  /aria/memory_id           — AgentCore Memory resource ID
  /aria/memory_strategy_id  — AgentCore Memory strategy ID
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
    "gateway_endpoint": "",
    "memory_id": "",
    "memory_strategy_id": "",
}

# ── Internal helpers ──────────────────────────────────────────────────────────

def _ssm_enabled() -> bool:
    return os.environ.get("SSM_ENABLED", "true").lower() != "false"


def _ssm_prefix() -> str:
    return os.environ.get("SSM_PREFIX", "/aria").rstrip("/")


def _load_from_ssm(region: str) -> dict:
    prefix = _ssm_prefix()
    try:
        client = boto3.client("ssm", region_name=region)
        paginator = client.get_paginator("get_parameters_by_path")
        params = {}
        for page in paginator.paginate(
            Path=prefix,
            Recursive=False,
            WithDecryption=True,
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
    return ssm.get(key) or os.environ.get(key.upper()) or _DEFAULTS.get(key, "")


# ── Public API ────────────────────────────────────────────────────────────────

class AgentConfig:
    """Immutable configuration snapshot loaded once at agent startup."""

    def __init__(self):
        region = os.environ.get("AWS_REGION", _DEFAULTS["region"])
        ssm = _load_from_ssm(region) if _ssm_enabled() else {}

        self.region: str = region
        self.model_id: str = _resolve("model_id", ssm)
        self.knowledge_base_id: str = _resolve("knowledge_base_id", ssm)
        self.kb_num_results: int = int(_resolve("kb_num_results", ssm))
        self.gateway_endpoint: str = _resolve("gateway_endpoint", ssm).rstrip("/")
        self.memory_id: str = _resolve("memory_id", ssm)
        self.memory_strategy_id: str = _resolve("memory_strategy_id", ssm)

        self._validate()

    def _validate(self):
        if not self.model_id:
            raise ValueError("Configuration error: 'model_id' is required but not set.")
        if self.kb_num_results < 1 or self.kb_num_results > 20:
            raise ValueError(
                f"Configuration error: 'kb_num_results' must be between 1 and 20, "
                f"got {self.kb_num_results}."
            )
        for name, value in [
            ("knowledge_base_id", self.knowledge_base_id),
            ("gateway_endpoint", self.gateway_endpoint),
            ("memory_id", self.memory_id),
            ("memory_strategy_id", self.memory_strategy_id),
        ]:
            if not value:
                logger.warning("Configuration warning: '%s' is not set.", name)

    def __repr__(self):
        return (
            f"AgentConfig("
            f"region={self.region!r}, "
            f"model_id={self.model_id!r}, "
            f"knowledge_base_id={'<set>' if self.knowledge_base_id else '<not set>'}, "
            f"gateway_endpoint={'<set>' if self.gateway_endpoint else '<not set>'}, "
            f"memory_id={'<set>' if self.memory_id else '<not set>'}"
            f")"
        )


cfg = AgentConfig()
