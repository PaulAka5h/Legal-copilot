"""Candidate Strategy Generator (NOT_CONFIGURED).

The earlier generator returned three fixed cheque-dishonour strategies for every
case, with hard-coded statutory and procedural claims marked as verified. That
broke Legal Product Rules 1 and 2 and was removed.

Until a grounded generator exists (master prompt Step E: confirmed facts,
retrieval, deterministic citation verification), this returns no strategies and
callers report STRATEGY_NOT_CONFIGURED_REASON.
"""

import os
from typing import Any, Dict, List, Optional

from backend.src.ai.gateway import LLMGateway
from backend.src.strategy.schemas import StrategyRecord


class ProductionLLMConfigurationError(RuntimeError):
    """Raised when production environment lacks required real LLM configuration."""


class StrategyGenerator:
    """Generates candidate legal strategies. Currently NOT_CONFIGURED."""

    def __init__(
        self,
        llm_gateway: Optional[LLMGateway] = None,
        retriever: Optional[Any] = None,
    ):
        self.gateway = llm_gateway or LLMGateway()
        self.retriever = retriever

    def generate_candidate_strategies(
        self,
        case_id: str,
        case_facts: Dict[str, Any],
        available_documents: List[Dict[str, Any]],
        organization_id: str = "default_org",
    ) -> List[StrategyRecord]:
        """Return no strategies: generation is NOT_CONFIGURED (Rule 11)."""
        env = os.getenv("ENVIRONMENT", "development").lower()
        if env == "production" and self.gateway.current_provider == "mock":
            raise ProductionLLMConfigurationError(
                "Cannot generate legal strategies using MockLLMProvider in production environment. "
                "An LLM provider approved in DOCS/providers.md must be configured."
            )
        return []
