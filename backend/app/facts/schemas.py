from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Category = Literal["party", "date", "place", "act_or_omission", "document", "relief_sought", "other"]
StatementType = Literal["document_says", "lawyer_entered", "ai_inference", "assumption"]
FactStatus = Literal["undisputed", "disputed", "needs_clarification", "verified_record"]
ReviewStatus = Literal["draft", "lawyer_reviewed", "lawyer_rejected"]


class FactAttributes(BaseModel):
    """Structured fields; all optional. Dates are ISO YYYY-MM-DD as written in the source."""

    model_config = ConfigDict(extra="forbid")

    party_name: str | None = Field(default=None, max_length=300)
    party_role: str | None = Field(default=None, max_length=100)
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    date_end: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    date_certainty: Literal["exact", "approximate", "range", "unknown"] | None = None
    place: str | None = Field(default=None, max_length=300)
    amount: str | None = Field(default=None, max_length=100)


# ------------------------------------------------------------- model output (strict)
class ExtractedSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    page_no: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=500, description="Exact text copied from the page")


class ExtractedFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Category
    statement: str = Field(min_length=1, max_length=1000)
    statement_type: Literal["document_says", "ai_inference", "assumption"]
    attributes: FactAttributes
    sources: list[ExtractedSource] = Field(max_length=5)

    @model_validator(mode="after")
    def document_says_needs_source(self) -> "ExtractedFact":
        if self.statement_type == "document_says" and not self.sources:
            raise ValueError("document_says facts need at least one source quote")
        return self


class ExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facts: list[ExtractedFact] = Field(max_length=100)


# ------------------------------------------------------------- API
class FactSourceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    page_no: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=2000, description="Exact text on the current page version")


class FactSourceOut(BaseModel):
    id: UUID
    source_kind: Literal["document_page", "lawyer_note"]
    document_id: UUID | None
    page_id: UUID | None = Field(description="The page version the quote was checked against")
    page_no: int | None
    quote: str | None
    quote_check: Literal["passed", "failed", "not_applicable"]


class FactOut(BaseModel):
    id: UUID
    lineage_id: UUID
    version: int
    supersedes_id: UUID | None
    is_current: bool
    category: Category
    statement: str
    attributes: dict
    statement_type: StatementType
    origin: Literal["ai", "ai_mock", "lawyer"]
    fact_status: FactStatus
    source_check: Literal["passed", "failed", "not_applicable"]
    review_status: ReviewStatus
    review_note: str | None
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    extraction_run_id: UUID | None
    created_by: UUID
    created_at: datetime
    usable_in_analysis: bool = Field(description="lawyer_entered or lawyer-confirmed, current, not rejected")
    sources: list[FactSourceOut]


class ExtractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_ids: list[UUID] | None = Field(
        default=None, max_length=50, description="Documents to read; omit for all processed documents"
    )


class ExtractionResponse(BaseModel):
    run_id: UUID
    status: Literal["succeeded", "extraction_failed"]
    provider: str
    model: str | None
    attempts: int
    pages_read: int
    facts_created: int
    source_check_failed: int
    facts: list[FactOut]


class FactCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Category
    statement: str = Field(min_length=1, max_length=4000)
    statement_type: Literal["lawyer_entered", "assumption"] = "lawyer_entered"
    attributes: FactAttributes = Field(default_factory=FactAttributes)
    fact_status: FactStatus = "undisputed"
    sources: list[FactSourceIn] = Field(default_factory=list, max_length=10)


class FactEditRequest(BaseModel):
    """Any change creates a new version. Changing the statement or sources makes it lawyer_entered."""

    model_config = ConfigDict(extra="forbid")

    category: Category | None = None
    statement: str | None = Field(default=None, min_length=1, max_length=4000)
    statement_type: Literal["lawyer_entered", "assumption"] | None = None
    attributes: FactAttributes | None = None
    fact_status: FactStatus | None = None
    sources: list[FactSourceIn] | None = Field(default=None, max_length=10)

    @model_validator(mode="after")
    def at_least_one_change(self) -> "FactEditRequest":
        if not self.model_fields_set:
            raise ValueError("No changes given")
        return self


class FactReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=2000)


class FactRejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str = Field(min_length=1, max_length=2000, description="Why the fact is rejected")


class ConfirmedFactSet(BaseModel):
    case_id: UUID
    fact_set_hash: str = Field(description="SHA-256 over the sorted fact version IDs; analysis records it")
    facts: list[FactOut]
