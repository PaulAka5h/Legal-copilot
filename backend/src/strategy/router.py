"""FastAPI Router for Chess-Inspired Legal Strategy Engine.

Follows:
- FastAPI best practices and OpenAPI documentation standards.
- Layered authorization and human-in-the-loop review.
- Audit event logging hooks.
"""

from typing import Annotated, Any, Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Body, HTTPException, Path, status
from pydantic import BaseModel, Field
from backend.src.strategy.engine import (
    ImmutableStrategyError,
    MockStrategyApprovalError,
    StrategyEngine,
)
from backend.src.strategy.orchestrator import StrategyOrchestrator
from backend.src.strategy.schemas import (
    LegalStrategyReportRecord,
    ScenarioTree,
    StrategyComparisonRecord,
    StrategyRecord,
    StrategyStatus,
)

router = APIRouter(prefix="/cases", tags=["Strategy Engine"])

# Global singleton strategy engine & orchestrator instances
_strategy_engine = StrategyEngine()
_strategy_orchestrator = StrategyOrchestrator()


def get_strategy_engine() -> StrategyEngine:
    return _strategy_engine


def get_strategy_orchestrator() -> StrategyOrchestrator:
    return _strategy_orchestrator


class StrategyGenerateRequest(BaseModel):
    case_facts: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Case summary and key extracted facts from Phase 5",
    )
    available_documents: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="List of available document summaries or extracted chunks",
    )
    organization_id: str = Field(
        default="default_org",
        description="Organization identifier for multi-tenant isolation",
    )


class StrategyActionRequest(BaseModel):
    lawyer_id: str = Field(description="User ID of the reviewing lawyer")
    notes: Optional[str] = Field(default=None, description="Optional action notes or reason")


@router.post(
    "/{case_id}/strategies/generate",
    response_model=List[StrategyRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Generate Candidate Legal Strategies",
    description="Analyzes case facts, retrieves relevant Bangladesh legal provisions, expands 2-ply adversarial scenario trees, and evaluates strategies across the 5-dimension rubric.",
)
def generate_strategies(
    case_id: Annotated[str, Path(description="Case UUID")],
    payload: Annotated[StrategyGenerateRequest, Body(description="Case facts and document list")],
) -> List[StrategyRecord]:
    engine = get_strategy_engine()
    facts = payload.case_facts or {}
    docs = payload.available_documents or []

    strategies = engine.generate_strategies_for_case(
        case_id=case_id,
        case_facts=facts,
        available_documents=docs,
        organization_id=payload.organization_id,
    )
    return strategies


@router.get(
    "/{case_id}/strategies",
    response_model=List[StrategyRecord],
    summary="List Candidate Strategies for Case",
    description="Retrieves all generated candidate strategies and their current lifecycle statuses.",
)
def list_strategies(
    case_id: Annotated[str, Path(description="Case UUID")],
) -> List[StrategyRecord]:
    engine = get_strategy_engine()
    return engine.get_strategies(case_id)


@router.get(
    "/{case_id}/strategies/comparison",
    response_model=StrategyComparisonRecord,
    summary="Get Strategy Comparison Matrix",
    description="Returns the qualitative 5-dimension comparison matrix and recommendation with reasoned trade-offs (No win percentages).",
)
def get_strategy_comparison(
    case_id: Annotated[str, Path(description="Case UUID")],
) -> StrategyComparisonRecord:
    engine = get_strategy_engine()
    comparison = engine.get_latest_comparison(case_id)
    if not comparison:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No strategy comparison available for this case.",
        )
    return comparison


@router.get(
    "/{case_id}/strategies/{strategy_id}",
    response_model=StrategyRecord,
    summary="Get Specific Strategy Record",
    description="Retrieves a specific strategy including legal basis, rubric score, and version lineage.",
)
def get_strategy(
    case_id: Annotated[str, Path(description="Case UUID")],
    strategy_id: Annotated[UUID, Path(description="Strategy UUID")],
) -> StrategyRecord:
    engine = get_strategy_engine()
    strategy = engine.get_strategy(case_id, strategy_id)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found in case {case_id}",
        )
    return strategy


@router.get(
    "/{case_id}/strategies/{strategy_id}/tree",
    response_model=ScenarioTree,
    summary="Get 2-Ply Adversarial Scenario Tree",
    description="Returns the interactive 2-ply game tree (Adversary Defenses & Our Responses) with residual risk metadata.",
)
def get_strategy_scenario_tree(
    case_id: Annotated[str, Path(description="Case UUID")],
    strategy_id: Annotated[UUID, Path(description="Strategy UUID")],
) -> ScenarioTree:
    engine = get_strategy_engine()
    strategy = engine.get_strategy(case_id, strategy_id)
    if not strategy or not strategy.scenario_tree:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario tree for strategy {strategy_id} not found",
        )
    return strategy.scenario_tree


@router.post(
    "/{case_id}/strategies/{strategy_id}/approve",
    response_model=StrategyRecord,
    summary="Approve Strategy (Lawyer Action)",
    description="Marks a proposed strategy as approved by the authorized lawyer. Fails if strategy is a simulated mock in production.",
)
def approve_strategy(
    case_id: Annotated[str, Path(description="Case UUID")],
    strategy_id: Annotated[UUID, Path(description="Strategy UUID")],
    payload: Annotated[StrategyActionRequest, Body(description="Lawyer approval identity and notes")],
) -> StrategyRecord:
    engine = get_strategy_engine()
    try:
        return engine.approve_strategy(case_id, strategy_id, lawyer_id=payload.lawyer_id)
    except MockStrategyApprovalError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")


@router.post(
    "/{case_id}/strategies/{strategy_id}/select",
    response_model=StrategyRecord,
    summary="Select Current Active Strategy",
    description="Sets strategy as the single CURRENT strategy for the case, superseding any prior active strategy.",
)
def select_current_strategy(
    case_id: Annotated[str, Path(description="Case UUID")],
    strategy_id: Annotated[UUID, Path(description="Strategy UUID")],
    payload: Annotated[StrategyActionRequest, Body(description="Lawyer selection identity")],
) -> StrategyRecord:
    engine = get_strategy_engine()
    try:
        return engine.select_current_strategy(case_id, strategy_id, lawyer_id=payload.lawyer_id)
    except MockStrategyApprovalError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")


@router.post(
    "/{case_id}/strategies/{strategy_id}/reject",
    response_model=StrategyRecord,
    summary="Reject Strategy",
    description="Marks a candidate strategy as rejected by the lawyer.",
)
def reject_strategy(
    case_id: Annotated[str, Path(description="Case UUID")],
    strategy_id: Annotated[UUID, Path(description="Strategy UUID")],
    payload: Annotated[StrategyActionRequest, Body(description="Lawyer rejection identity and reason")],
) -> StrategyRecord:
    engine = get_strategy_engine()
    try:
        return engine.reject_strategy(case_id, strategy_id, lawyer_id=payload.lawyer_id, reason=payload.notes or "")
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")


@router.post(
    "/{case_id}/strategies/report",
    response_model=LegalStrategyReportRecord,
    status_code=status.HTTP_200_OK,
    summary="Generate Comprehensive Legal Strategy Report",
    description="Orchestrates full RAG + LLM pipeline: material facts, bilingual query expansion, statutory & precedent analysis, 2-ply adversarial tree, 5-dimension rubric scoring, comparison matrix, and actionable next steps.",
)
def generate_strategy_report(
    case_id: Annotated[str, Path(description="Case UUID")],
    payload: Annotated[StrategyGenerateRequest, Body(description="Case facts and document list")],
) -> LegalStrategyReportRecord:
    orchestrator = get_strategy_orchestrator()
    facts = payload.case_facts or {}
    docs = payload.available_documents or []
    report = orchestrator.generate_final_report(
        case_id=case_id,
        case_facts=facts,
        available_documents=docs,
        organization_id=payload.organization_id,
    )
    return report
