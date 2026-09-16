"""
Aria — Module 04 configuration loader.

Module 04 uses these SSM parameters under /aria/:
  /aria/model_id              — Bedrock model ID
  /aria/knowledge_base_id     — Bedrock Knowledge Base ID
  /aria/kb_num_results        — Number of Knowledge Base chunks per query
  /aria/region                — AWS Region

Set SSM_ENABLED=false for local development and use environment variables
instead.
"""

import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "model_id": "us.anthropic.claude-sonnet-4-6",
    "knowledge_base_id": "",
    "kb_num_results": "5",
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
        self.knowledge_base_id = _resolve("knowledge_base_id", ssm)
        self.kb_num_results = int(_resolve("kb_num_results", ssm))

        if not self.knowledge_base_id:
            logger.warning("Configuration warning: knowledge_base_id is not set")
        if not 1 <= self.kb_num_results <= 20:
            raise ValueError("kb_num_results must be between 1 and 20")

    def __repr__(self):
        return (
            f"AgentConfig(region={self.region!r}, model_id={self.model_id!r}, "
            f"knowledge_base_id={'<set>' if self.knowledge_base_id else '<not set>'}, "
            f"kb_num_results={self.kb_num_results})"
        )


cfg = AgentConfig()
