"""Strategy Engine Coordinator, Comparison Matrix, and Lifecycle Management.

Enforces:
1. Lifecycle: draft -> proposed -> approved -> current -> superseded, plus rejected.
2. Immutability of approved/current strategies (modifications spawn new versions).
3. At most ONE 'current' strategy per case.
4. Mock Safeguard: Mock strategies cannot be approved or marked current in production.
5. Qualitative comparison matrix without numerical win probabilities.
"""

from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from backend.src.strategy.generator import StrategyGenerator
from backend.src.strategy.schemas import (
    NO_PRECEDENT_NOTE,
    NOT_CONFIGURED,
    RecommendationType,
    RubricRating,
    StrategyComparisonItem,
    StrategyComparisonRecord,
    StrategyOrigin,
    StrategyRecord,
    StrategyStatus,
    comparison_reason,
)


class MockStrategyApprovalError(PermissionError):
    """Raised when an attempt is made to approve or select a mock-generated strategy."""
    pass


class ImmutableStrategyError(RuntimeError):
    """Raised when attempting to overwrite an approved or current strategy in place."""
    pass


class StrategyEngine:
    """Master orchestrator for Chess-Inspired Strategy Engine."""

    def __init__(self, generator: Optional[StrategyGenerator] = None):
        self.generator = generator or StrategyGenerator()
        # In-memory storage of strategies: case_id -> list of StrategyRecord
        self._strategy_store: Dict[str, List[StrategyRecord]] = {}
        # In-memory storage of comparisons: case_id -> list of StrategyComparisonRecord
        self._comparison_store: Dict[str, List[StrategyComparisonRecord]] = {}

    def generate_strategies_for_case(
        self,
        case_id: str,
        case_facts: Dict[str, Any],
        available_documents: List[Dict[str, Any]],
        organization_id: str = "default_org",
    ) -> List[StrategyRecord]:
        """Generate, evaluate, and store candidate legal strategies."""
        candidates = self.generator.generate_candidate_strategies(
            case_id=case_id,
            case_facts=case_facts,
            available_documents=available_documents,
            organization_id=organization_id,
        )

        if case_id not in self._strategy_store:
            self._strategy_store[case_id] = []

        for strat in candidates:
            self._strategy_store[case_id].append(strat)

        # Build comparison matrix
        self._build_and_store_comparison(case_id, organization_id)
        return candidates

    def get_strategies(self, case_id: str) -> List[StrategyRecord]:
        """Get all strategies for a case."""
        return self._strategy_store.get(case_id, [])

    def get_strategy(self, case_id: str, strategy_id: UUID) -> Optional[StrategyRecord]:
        """Fetch a specific strategy by ID."""
        for s in self.get_strategies(case_id):
            if s.id == strategy_id:
                return s
        return None

    def get_current_strategy(self, case_id: str) -> Optional[StrategyRecord]:
        """Fetch the single active current strategy for a case."""
        for s in self.get_strategies(case_id):
            if s.is_current_strategy and s.status == StrategyStatus.CURRENT:
                return s
        return None

    def propose_strategy(self, case_id: str, strategy_id: UUID, user_id: str) -> StrategyRecord:
        """Move strategy from DRAFT to PROPOSED for lawyer review."""
        strategy = self.get_strategy(case_id, strategy_id)
        if not strategy:
            raise KeyError(f"Strategy {strategy_id} not found in case {case_id}")

        if strategy.status != StrategyStatus.DRAFT:
            raise ValueError(f"Cannot propose strategy with status '{strategy.status.value}'. Must be 'draft'.")

        strategy.status = StrategyStatus.PROPOSED
        strategy.updated_at = datetime.now(timezone.utc)
        return strategy

    def approve_strategy(self, case_id: str, strategy_id: UUID, lawyer_id: str) -> StrategyRecord:
        """Approve a strategy. Enforces mock restriction and immutability."""
        strategy = self.get_strategy(case_id, strategy_id)
        if not strategy:
            raise KeyError(f"Strategy {strategy_id} not found in case {case_id}")

        # Instruction 9: Mock strategies cannot be approved in production
        env = os.getenv("ENVIRONMENT", "development").lower()
        if strategy.is_mock and env == "production":
            raise MockStrategyApprovalError(
                "Mock-generated legal strategies cannot be approved for real court representation. "
                "Run strategy generation with an approved production LLM."
            )

        if strategy.status in (StrategyStatus.APPROVED, StrategyStatus.CURRENT):
            return strategy  # already approved

        strategy.status = StrategyStatus.APPROVED
        strategy.approved_by = lawyer_id
        strategy.approved_at = datetime.now(timezone.utc)
        strategy.updated_at = datetime.now(timezone.utc)
        return strategy

    def select_current_strategy(self, case_id: str, strategy_id: UUID, lawyer_id: str) -> StrategyRecord:
        """Set a strategy as the active CURRENT strategy.
        
        Enforces single current strategy rule: supersedes any previously current strategy.
        """
        target = self.get_strategy(case_id, strategy_id)
        if not target:
            raise KeyError(f"Strategy {strategy_id} not found in case {case_id}")

        env = os.getenv("ENVIRONMENT", "development").lower()
        if target.is_mock and env == "production":
            raise MockStrategyApprovalError(
                "Mock-generated strategy cannot be selected as current in production."
            )

        now = datetime.now(timezone.utc)

        # Demote existing current strategy to SUPERSEDED
        for s in self.get_strategies(case_id):
            if s.is_current_strategy and s.id != target.id:
                s.is_current_strategy = False
                s.status = StrategyStatus.SUPERSEDED
                s.updated_at = now

        # Target strategy becomes CURRENT
        target.status = StrategyStatus.CURRENT
        target.is_current_strategy = True
        target.approved_by = target.approved_by or lawyer_id
        target.approved_at = target.approved_at or now
        target.updated_at = now

        # Update comparison record
        self._build_and_store_comparison(case_id, target.organization_id)
        return target

    def reject_strategy(self, case_id: str, strategy_id: UUID, lawyer_id: str, reason: str = "") -> StrategyRecord:
        """Reject a proposed strategy."""
        strategy = self.get_strategy(case_id, strategy_id)
        if not strategy:
            raise KeyError(f"Strategy {strategy_id} not found in case {case_id}")

        strategy.status = StrategyStatus.REJECTED
        strategy.is_current_strategy = False
        strategy.updated_at = datetime.now(timezone.utc)
        return strategy

    def update_strategy_with_new_version(
        self,
        case_id: str,
        strategy_id: UUID,
        updates: Dict[str, Any],
        author_id: str,
    ) -> StrategyRecord:
        """Create an immutable new version of an approved or current strategy."""
        old_strat = self.get_strategy(case_id, strategy_id)
        if not old_strat:
            raise KeyError(f"Strategy {strategy_id} not found in case {case_id}")

        # New version in the same lineage
        new_version_num = old_strat.version + 1
        new_strat = old_strat.model_copy(
            update={
                "id": uuid4(),
                "version": new_version_num,
                "supersedes_id": old_strat.id,
                "status": StrategyStatus.DRAFT,
                "is_current_strategy": False,
                "created_by": author_id,
                "approved_by": None,
                "approved_at": None,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                **updates,
            }
        )
        self._strategy_store[case_id].append(new_strat)
        return new_strat

    def _build_and_store_comparison(self, case_id: str, organization_id: str) -> StrategyComparisonRecord:
        """Construct the 5-dimension qualitative comparison matrix without win probabilities."""
        strategies = self.get_strategies(case_id)
        items: List[StrategyComparisonItem] = []

        best_strat_id: Optional[UUID] = None
        current_highest_rating = -1

        for s in strategies:
            rubric = s.rubric_evaluation
            if not rubric:
                continue

            from backend.src.strategy.evaluator import RATING_ORDER

            score_val = RATING_ORDER[rubric.overall_rating]
            if score_val > current_highest_rating:
                current_highest_rating = score_val
                best_strat_id = s.id

            major_opps = []
            if s.scenario_tree:
                for opp in s.scenario_tree.opposing_arguments:
                    if not opp.pruned:
                        major_opps.append(opp.text)

            items.append(
                StrategyComparisonItem(
                    strategy_id=s.id,
                    name=s.name,
                    status=s.status,
                    is_current=s.is_current_strategy,
                    overall_rating=rubric.overall_rating,
                    statutory_strength=rubric.statutory_strength.rating,
                    precedent_alignment=rubric.precedent_alignment.rating,
                    factual_support=rubric.factual_support.rating,
                    procedural_compliance=rubric.procedural_compliance.rating,
                    forum_risk=rubric.forum_risk.rating,
                    key_strengths=s.strengths[:2],
                    key_vulnerabilities=s.weaknesses[:2],
                    major_opposing_arguments=major_opps[:2],
                    potential_remedies=s.remedies_sought[:2],
                )
            )

        existing_comps = self._comparison_store.get(case_id, [])
        version_num = len(existing_comps) + 1
        supersedes_id = existing_comps[-1].id if existing_comps else None

        rec_record = StrategyComparisonRecord(
            case_id=case_id,
            organization_id=organization_id,
            version=version_num,
            supersedes_id=supersedes_id,
            strategies=items,
            best_supported_strategy_id=best_strat_id,
            recommendation=RecommendationType.INITIAL,
            recommendation_reason=comparison_reason(items),
            trade_offs_analysis=NOT_CONFIGURED,
            uncertainties=[NO_PRECEDENT_NOTE],
        )

        if case_id not in self._comparison_store:
            self._comparison_store[case_id] = []
        self._comparison_store[case_id].append(rec_record)
        return rec_record

    def get_latest_comparison(self, case_id: str) -> Optional[StrategyComparisonRecord]:
        """Fetch the latest comparison matrix for a case."""
        comps = self._comparison_store.get(case_id, [])
        return comps[-1] if comps else None
