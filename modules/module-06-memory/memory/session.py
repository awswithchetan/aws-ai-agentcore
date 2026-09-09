"""
Aria — Memory Session Factory
==============================
Creates an AgentCoreMemorySessionManager scoped to a specific customer
(actor_id) and conversation (session_id).

Called once per agent invocation in agent.py. Strands uses the returned
session manager to:
  - Write conversation turns to short-term memory automatically
  - Retrieve relevant long-term memories before each response

Long-term memory retrieval:
  retrieval_config maps a namespace template to a RetrievalConfig. The SDK
  resolves {actorId} and {memoryStrategyId} placeholders at retrieval time
  using the actor_id and strategy_id values provided.

  The namespace template and strategy_id must match what AgentCore writes to —
  both come from the Memory resource created in Step 1 and stored in SSM.

  Namespace template (default for Semantic Memory):
    /strategies/{memoryStrategyId}/actors/{actorId}/

In Module 07 (Identity), actor_id will come from the verified JWT token
instead of the payload. This file stays unchanged.
"""

import logging
from typing import Optional

from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig,
    RetrievalConfig,
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)

from config import cfg

logger = logging.getLogger(__name__)


def get_memory_session_manager(
    session_id: str,
    actor_id: str,
) -> Optional[AgentCoreMemorySessionManager]:
    """
    Returns a configured AgentCoreMemorySessionManager for the given
    customer and session. Returns None if memory is not configured so
    the agent degrades gracefully without memory rather than crashing.

    Args:
        session_id: The runtime session ID (one per conversation window)
        actor_id:   The customer ID (e.g. C001) — stable across sessions

    Returns:
        AgentCoreMemorySessionManager or None
    """
    if not cfg.memory_id:
        logger.warning("Memory not configured — running without persistent memory")
        return None

    if not cfg.memory_strategy_id:
        logger.warning("Memory strategy ID not configured — running without persistent memory")
        return None

    # Namespace template uses {actorId} and {memoryStrategyId} placeholders.
    # The SDK resolves these at retrieval time via .format(actorId=..., memoryStrategyId=...).
    # This must match the namespace template on the Memory resource (default for Semantic Memory).
    retrieval_config = {
        "/strategies/{memoryStrategyId}/actors/{actorId}/": RetrievalConfig(
            top_k=5,
            relevance_score=0.4,
            strategy_id=cfg.memory_strategy_id,
        ),
    }

    logger.info(
        "Initialising memory session — actor_id=%s session_id=%s memory_id=%s strategy_id=%s",
        actor_id, session_id, cfg.memory_id, cfg.memory_strategy_id,
    )

    return AgentCoreMemorySessionManager(
        AgentCoreMemoryConfig(
            memory_id=cfg.memory_id,
            session_id=session_id,
            actor_id=actor_id,
            retrieval_config=retrieval_config,
        ),
        cfg.region,
    )
