from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Strength = Literal["strong", "moderate", "weak", "insufficient"]
ElementStatus = Literal["met", "missing", "disputed"]


# ------------------------------------------------------------- model output (validated)
class ElementDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    element: str = Field(min_length=1, max_length=500, description="One legal ingredient, in plain words")
    element_quote: str = Field(min_length=1, max_length=600, description="Exact text of the ingredient in the provision")
    matched_fact_id: UUID | None = Field(description="Confirmed fact that satisfies the ingredient, or null")
    status: ElementStatus


class FindingDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offence_or_claim: str = Field(min_length=1, max_length=300)
    chunk_id: UUID = Field(description="The provision chunk the ingredients come from")
    quote: str = Field(min_length=1, max_length=1200, description="Exact text from that chunk")
    elements: list[ElementDraft] = Field(min_length=1, max_length=8)
    strength: Strength
    reasons: list[str] = Field(min_length=1, max_length=6)


class AnalysisDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[FindingDraft] = Field(max_length=8)
    missing_information: list[str] = Field(max_length=10)


# ------------------------------------------------------------- API (master prompt contracts)
class CitationOut(BaseModel):
    chunk_id: UUID
    act_title: str | None
    section: str | None
    language: Literal["bn", "en"] | None
    source_url: str | None
    quote: str | None
    verified: bool = Field(description="Passed the deterministic citation verifier")
    in_force_status: str
    failures: list[str] = Field(description="Why verification failed, if it did")
    warnings: list[str]


class ElementOut(BaseModel):
    element: str
    element_quote: str
    matched_fact_id: UUID | None
    status: ElementStatus
    verified: bool = Field(description="element_quote found in the cited provision text")


class ViolationFinding(BaseModel):
    offence_or_claim: str
    section_citation: CitationOut
    elements: list[ElementOut]
    strength: Strength = Field(description="Qualitative only; never a percentage (Rule 4)")
    reasons: list[str]
    statement_type: Literal["ai_inference"] = "ai_inference"
    verification: Literal["verified", "unverified"]


class RetrievedSource(BaseModel):
    chunk_id: UUID
    act_title: str
    section_number: str | None
    language: Literal["bn", "en"]
    source_url: str
    best_score: float = Field(description="Reranker score, or cosine similarity with the mock reranker")
    from_fact_ids: list[UUID]


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_date: date | None = Field(default=None, description="Statutes not in force on this date are excluded")
    language: Literal["bn", "en"] | None = Field(default=None, description="Restrict statute language; omit for both")


class AnalysisOut(BaseModel):
    id: UUID
    case_id: UUID
    version: int
    supersedes_id: UUID | None
    trigger: Literal["manual", "hearing_update"]
    status: Literal["succeeded", "insufficient_information", "failed"]
    fact_set_hash: str
    fact_ids: list[UUID]
    incident_date: date | None
    provider: str
    origin: Literal["ai", "ai_mock"]
    findings: list[ViolationFinding]
    missing_information: list[str]
    retrieved_sources: list[RetrievedSource]
    abstain_reason: str | None
    precedent_note: str
    verification_summary: dict
    warnings: list[str]
    review_status: Literal["draft"] = Field(default="draft", description="AI output is a draft (Rule 5)")
    created_by: UUID
    created_at: datetime


class AnalysisVersionSummary(BaseModel):
    id: UUID
    version: int
    status: str
    fact_set_hash: str
    provider: str
    origin: str
    findings: int
    created_at: datetime
