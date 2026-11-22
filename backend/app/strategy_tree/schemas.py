from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.case_analysis.schemas import CitationOut

Level = Literal["low", "medium", "high", "unknown"]
Strength = Literal["strong", "moderate", "weak", "insufficient"]
MAX_MOVES = 4
MAX_BRANCHES = 3


# ------------------------------------------------------------- model output (3 explicit plies)
class LegalBasisDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: UUID
    quote: str = Field(min_length=1, max_length=600, description="Exact text from that provision")


class _NodeDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    move: str = Field(min_length=1, max_length=400)
    legal_basis: list[LegalBasisDraft] = Field(max_length=3)
    requirements: list[str] = Field(max_length=5)
    risk: Level
    cost: Level
    time: Level
    strength: Strength
    reasons: list[str] = Field(min_length=1, max_length=4)


class Ply3Draft(_NodeDraft):
    actor: Literal["us"]


class Ply2Draft(_NodeDraft):
    actor: Literal["opponent", "court"]
    children: list[Ply3Draft] = Field(max_length=MAX_BRANCHES)


class Ply1Draft(_NodeDraft):
    actor: Literal["us"]
    children: list[Ply2Draft] = Field(max_length=MAX_BRANCHES)


class StrategyDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    moves: list[Ply1Draft] = Field(max_length=MAX_MOVES)
    missing_information: list[str] = Field(max_length=10)


# ------------------------------------------------------------- model output: a flat node list
# The model returns a flat list (id + parent_id) instead of three nested levels: deep nesting
# with enums makes structured-output decoders slow or refuse the schema. The tree is rebuilt
# and checked in code (service.nest_nodes). Limits are generous; extras are trimmed in code.
class FlatLegalBasis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(description="chunk_id of one of the given provisions")
    quote: str = Field(min_length=1, max_length=2000, description="Exact text copied from that provision")


class FlatNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=40, description="Short unique id, e.g. m1, m1r1, m1r1c1")
    parent_id: str | None = Field(description="null for our first moves; otherwise the id of the parent node")
    actor: Literal["us", "opponent", "court"]
    move: str = Field(min_length=1, max_length=1200)
    legal_basis: list[FlatLegalBasis] = Field(max_length=6)
    requirements: list[str] = Field(max_length=10)
    risk: Level
    cost: Level
    time: Level
    strength: Strength
    reasons: list[str] = Field(min_length=1, max_length=8)


class StrategyFlatDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[FlatNode] = Field(max_length=80)
    missing_information: list[str] = Field(max_length=20)


# ------------------------------------------------------------- API (master prompt StrategyNode)
class StrategyNode(BaseModel):
    id: str
    parent_id: str | None
    ply: int = Field(ge=0, le=3)
    actor: Literal["us", "opponent", "court"]
    move: str
    legal_basis: list[CitationOut]
    requirements: list[str]
    risk: Level
    cost: Level
    time: Level
    strength: Strength = Field(description="Qualitative label; never a percentage (Rule 4)")
    reasons: list[str]
    verified: bool = Field(description="Every legal basis citation passed the deterministic verifier")
    statement_type: Literal["ai_inference", "case_state"]
    children: list["StrategyNode"]


class StrategyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_version: int | None = Field(default=None, ge=1, description="Defaults to the latest analysis")


class StrategyOut(BaseModel):
    id: UUID
    case_id: UUID
    version: int
    supersedes_id: UUID | None
    analysis_id: UUID
    analysis_version: int
    fact_set_hash: str
    status: Literal["succeeded", "insufficient_information"]
    provider: str
    origin: Literal["ai", "ai_mock"]
    root: StrategyNode
    missing_information: list[str]
    precedent_note: str
    verification_summary: dict
    warnings: list[str]
    review_status: Literal["draft"] = "draft"
    created_at: datetime


class StrategyVersionSummary(BaseModel):
    id: UUID
    version: int
    status: str
    analysis_id: UUID
    origin: str
    moves: int
    created_at: datetime


class NodeChange(BaseModel):
    ply: int
    actor: str
    move: str
    before: dict | None
    after: dict | None


class StrategyComparison(BaseModel):
    base_version: int
    target_version: int
    added: list[NodeChange]
    removed: list[NodeChange]
    changed: list[NodeChange]
    closed_options: list[str] = Field(description="Our first moves present in base but not in target")
    new_options: list[str] = Field(description="Our first moves present in target but not in base")
