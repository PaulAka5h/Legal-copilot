"""Data Models and Schemas for Chess-Inspired Legal Strategy Engine.

Follows TRD Section 8 and Database Specification (DOCS/database.md Section 10):
- Strict 2-ply scenario tree (D=2, B<=3) with residual risk metadata on response nodes
- 5-dimension qualitative rubric scoring with weakest-critical-dimension ceiling rule
- Traceable citations and precedent references
- Full lifecycle status enums and version lineage
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class StrategyStatus(str, Enum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    APPROVED = "approved"
    CURRENT = "current"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class StrategyOrigin(str, Enum):
    AI = "ai"
    AI_MOCK = "ai_mock"
    LAWYER = "lawyer"


class RubricRating(str, Enum):
    INSUFFICIENT_INFORMATION = "insufficient_information"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class Plausibility(str, Enum):
    LIKELY = "likely"
    POSSIBLE = "possible"
    UNLIKELY = "unlikely"


class ScenarioNodeType(str, Enum):
    STRATEGY_ROOT = "strategy_root"
    OPPOSING_ARGUMENT = "opposing_argument"
    OUR_RESPONSE = "our_response"


class RecommendationType(str, Enum):
    MAINTAIN = "maintain"
    REVIEW = "review"
    CHANGE_SUGGESTED = "change_suggested"
    INITIAL = "initial"


class LegalCitationReference(BaseModel):
    act_name: str
    section: Optional[str] = None
    subsection: Optional[str] = None
    clause: Optional[str] = None
    chapter: Optional[str] = None
    source_id: Optional[str] = None
    chunk_id: Optional[str] = None
    source_url: Optional[str] = None
    source_page: Optional[int] = None
    is_verified: bool = True


class PrecedentReference(BaseModel):
    case_title: str
    citation: str  # e.g. "54 DLR (AD) 124" or "2018 BLD (HCD) 345"
    court: str = "High Court Division"  # High Court Division | Appellate Division
    year: Optional[int] = None
    legal_principle: str
    source_url: Optional[str] = None
    is_verified: bool = False  # True only if verified from stored court judgments


class ResidualRiskMetadata(BaseModel):
    """Metadata attached directly to Depth-2 response node (TRD Requirement 2)."""
    risk_level: str = "medium"  # low | medium | high
    risk_summary: str
    practical_obstacles: List[str] = Field(default_factory=list)
    unresolved_weaknesses: List[str] = Field(default_factory=list)
    mitigation_options: List[str] = Field(default_factory=list)


class ScenarioResponseNode(BaseModel):
    """Depth 2: Our response to an adversary's argument."""
    id: UUID = Field(default_factory=uuid4)
    parent_id: UUID
    depth: int = 2
    node_type: ScenarioNodeType = ScenarioNodeType.OUR_RESPONSE
    text: str
    supporting_authorities: List[LegalCitationReference] = Field(default_factory=list)
    supporting_precedents: List[PrecedentReference] = Field(default_factory=list)
    supporting_facts: List[str] = Field(default_factory=list)
    residual_risk: ResidualRiskMetadata


class ScenarioOpposingNode(BaseModel):
    """Depth 1: Opposing argument or defense raised by adversary (max B=3)."""
    id: UUID = Field(default_factory=uuid4)
    parent_id: UUID
    depth: int = 1
    node_type: ScenarioNodeType = ScenarioNodeType.OPPOSING_ARGUMENT
    text: str
    legal_ground: str
    plausibility: Plausibility = Plausibility.LIKELY
    pruned: bool = False
    prune_reason: Optional[str] = None
    responses: List[ScenarioResponseNode] = Field(default_factory=list)


class ScenarioTree(BaseModel):
    """2-Ply Adversarial Scenario Tree."""
    root_strategy_id: UUID
    depth: int = 0
    strategy_name: str
    opposing_arguments: List[ScenarioOpposingNode] = Field(default_factory=list)


class RubricDimensionScore(BaseModel):
    dimension_name: str
    rating: RubricRating
    explanation: str
    supporting_evidence: List[str] = Field(default_factory=list)
    source_references: List[str] = Field(default_factory=list)
    gaps_or_uncertainties: List[str] = Field(default_factory=list)


class StrategyRubricEvaluation(BaseModel):
    statutory_strength: RubricDimensionScore
    precedent_alignment: RubricDimensionScore
    factual_support: RubricDimensionScore
    procedural_compliance: RubricDimensionScore
    forum_risk: RubricDimensionScore
    overall_rating: RubricRating
    weakest_critical_dimension: str
    requires_lawyer_review: bool = False
    review_reasons: List[str] = Field(default_factory=list)


class EligibilityCheckResult(BaseModel):
    is_eligible: bool
    jurisdiction_status: str
    limitation_status: str
    procedural_prerequisites_met: bool
    missing_verifications: List[str] = Field(default_factory=list)
    identified_remedies: List[str] = Field(default_factory=list)
    notes: str = ""


class StrategyRecord(BaseModel):
    """Immutable, versioned candidate legal strategy."""
    id: UUID = Field(default_factory=uuid4)
    case_id: str
    organization_id: str = "default_org"
    lineage_id: UUID = Field(default_factory=uuid4)  # stable across versions
    version: int = 1
    supersedes_id: Optional[UUID] = None

    name: str
    legal_basis: str
    procedural_requirements: List[str] = Field(default_factory=list)
    remedies_sought: List[str] = Field(default_factory=list)

    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)

    origin: StrategyOrigin = StrategyOrigin.AI
    status: StrategyStatus = StrategyStatus.DRAFT
    is_current_strategy: bool = False
    is_mock: bool = False

    supporting_facts: List[str] = Field(default_factory=list)
    source_references: List[LegalCitationReference] = Field(default_factory=list)
    precedent_references: List[PrecedentReference] = Field(default_factory=list)

    scenario_tree: Optional[ScenarioTree] = None
    rubric_evaluation: Optional[StrategyRubricEvaluation] = None
    eligibility: Optional[EligibilityCheckResult] = None

    created_by: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_version: str = "v1"
    prompt_version: str = "v1"


class StrategyComparisonItem(BaseModel):
    strategy_id: UUID
    name: str
    status: StrategyStatus
    is_current: bool
    overall_rating: RubricRating
    statutory_strength: RubricRating
    precedent_alignment: RubricRating
    factual_support: RubricRating
    procedural_compliance: RubricRating
    forum_risk: RubricRating
    key_strengths: List[str]
    key_vulnerabilities: List[str]
    major_opposing_arguments: List[str]
    potential_remedies: List[str]


class StrategyComparisonRecord(BaseModel):
    """Matrix comparing all legally plausible candidate strategies for a case."""
    id: UUID = Field(default_factory=uuid4)
    case_id: str
    organization_id: str = "default_org"
    version: int = 1
    supersedes_id: Optional[UUID] = None
    analysis_id: Optional[str] = None

    strategies: List[StrategyComparisonItem] = Field(default_factory=list)
    best_supported_strategy_id: Optional[UUID] = None
    recommendation: RecommendationType = RecommendationType.INITIAL
    recommendation_reason: str
    trade_offs_analysis: str
    uncertainties: List[str] = Field(default_factory=list)
    diff_from_previous: Optional[Dict[str, Any]] = None
    review_status: str = "draft"  # 'draft' | 'lawyer_reviewed' | 'lawyer_rejected'
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
