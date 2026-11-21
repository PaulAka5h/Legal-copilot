from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Strength = Literal["strong", "moderate", "weak", "insufficient"]
ElementStatus = Literal["met", "missing", "disputed"]


# ------------------------------------------------------------- model output (validated)
SentenceNumbers = list[int]


class QuoteRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: UUID = Field(description="chunk_id of the provision the quote is copied from")
    sentences: SentenceNumbers = Field(max_length=12,
                                       description="Numbers of the provision's [S#] sentences the quote is copied from")


class ElementDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    element: str = Field(min_length=1, max_length=500, description="One legal ingredient, in plain words")
    # Long limits on purpose: Gemini's schema mode drops maxLength, and a long quote is
    # still checked and stored as the exact source span (app.rag.quote_locator).
    element_quote: str = Field(min_length=1, max_length=1500, description="Exact text of the ingredient in the provision")
    element_quote_sentences: SentenceNumbers = Field(
        max_length=12, description="Numbers of the [S#] sentences of the finding's provision the element_quote is from")
    matched_fact_id: UUID | None = Field(description="Confirmed fact that satisfies the ingredient, or null")
    status: ElementStatus


class FindingDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offence_or_claim: str = Field(min_length=1, max_length=300)
    chunk_id: UUID = Field(description="The provision chunk the ingredients come from")
    quote: str = Field(min_length=1, max_length=4000, description="Exact text from that chunk")
    quote_ref: QuoteRef = Field(description="Where the quote is in the provision (a hint; the text is what is checked)")
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
    element_quote: str | None = Field(
        description="Exact span of the cited provision text (located and copied from the database), or null when "
        "the model's quote could not be found in the provision and was dropped")
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
