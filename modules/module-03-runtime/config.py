"""
Aria — Module 03 (Runtime) configuration loader.

Module 03 deploys the self-contained agent from Module 02 onto AgentCore
Runtime with the *smallest possible change*. The only real difference from
Module 02 is the entrypoint (BedrockAgentCoreApp) — the tools are still
simulated and there is no Knowledge Base yet (that arrives in Module 04).

This module reads just two values from SSM Parameter Store under /aria/:
  /aria/model_id  — Bedrock model ID
  /aria/region    — AWS Region

Set SSM_ENABLED=false for local development and use environment variables
instead (MODEL_ID / AWS_REGION).
"""

import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "model_id": "us.anthropic.claude-sonnet-4-6",
    "region": "us-east-1",
}


def _ssm_enabled() -> bool:
    return os.environ.get("SSM_ENABLED", "true").lower() != "false"


def _load_from_ssm(region: str) -> dict:
    prefix = os.environ.get("SSM_PREFIX", "/aria").rstrip("/")
    try:
        client = boto3.client("ssm", region_name=region)
        paginator = client.get_paginator("get_parameters_by_path")
        params = {}
        for page in paginator.paginate(
            Path=prefix,
            Recursive=False,
            WithDecryption=True,
        ):
            for parameter in page["Parameters"]:
                key = parameter["Name"].removeprefix(prefix + "/")
                params[key] = parameter["Value"]
        return params
    except ClientError as error:
        logger.warning("SSM unavailable (%s); using fallbacks", error.response["Error"]["Code"])
        return {}
    except Exception as error:  # noqa: BLE001
        logger.warning("SSM load failed (%s); using fallbacks", error)
        return {}


def _resolve(key: str, ssm: dict) -> str:
    return ssm.get(key) or os.environ.get(key.upper()) or _DEFAULTS[key]


class AgentConfig:
    """Configuration snapshot loaded once when the agent starts."""

    def __init__(self):
        self.region = os.environ.get("AWS_REGION", _DEFAULTS["region"])
        ssm = _load_from_ssm(self.region) if _ssm_enabled() else {}
        self.model_id = _resolve("model_id", ssm)

    def __repr__(self):
        return f"AgentConfig(region={self.region!r}, model_id={self.model_id!r})"


cfg = AgentConfig()
