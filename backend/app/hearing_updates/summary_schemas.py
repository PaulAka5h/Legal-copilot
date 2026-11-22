from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

SectionId = Literal["keyNotes", "laws", "risks", "rights", "notes", "nextSteps"]


class LocalizedText(BaseModel):
    """Hearing notes can hold the order text and the notes (8000 characters each)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    en: str = Field(default="", max_length=20000)
    bn: str = Field(default="", max_length=20000)

    @model_validator(mode="after")
    def not_empty(self) -> "LocalizedText":
        if not (self.en or self.bn):
            raise ValueError("Text is required in English or Bangla.")
        return self


class SummaryClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")
    type: Literal["document", "lawyer", "ai", "assumption"] = Field(
        description="Statement type, kept apart (Rule 3)"
    )
    verification: Literal["verified", "unverified"]
    text: LocalizedText
    source: LocalizedText = Field(description="Where the claim comes from (Rule 2)")


class SummarySection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: SectionId
    claims: list[SummaryClaim] = Field(max_length=100)


class SummaryVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_version: int = Field(
        ge=1,
        description="The version the lawyer edited. A newer saved version makes this a 409 (stale edit).",
    )
    sections: list[SummarySection] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def unique_ids(self) -> "SummaryVersionCreate":
        section_ids = [section.id for section in self.sections]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("Section ids must be unique.")
        claim_ids = [claim.id for section in self.sections for claim in section.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("Claim ids must be unique.")
        return self


class SummaryVersionOut(BaseModel):
    id: UUID
    hearing_id: UUID
    version: int = Field(description="2 and up; version 1 is the AI draft built from the reassessment")
    supersedes_id: UUID | None
    sections: list[SummarySection]
    created_by: UUID
    created_at: datetime


class PdfMetaRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=100)
    value: str = Field(max_length=500)


class PdfItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=20000)
    tags: list[str] = Field(default_factory=list, max_length=4, description="Statement type and verification labels")
    source: str | None = Field(default=None, max_length=1000)


class PdfSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    heading: str = Field(min_length=1, max_length=200)
    items: list[PdfItem] = Field(max_length=100)


class SummaryPdfRequest(BaseModel):
    """The summary as the lawyer sees it, with labels already in the lawyer's language."""

    model_config = ConfigDict(extra="forbid")
    eyebrow: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=300)
    meta: list[PdfMetaRow] = Field(default_factory=list, max_length=12)
    notice: str | None = Field(default=None, max_length=2000, description="Not-legal-advice / draft notice")
    sections: list[PdfSection] = Field(max_length=10)
    footer: str | None = Field(default=None, max_length=2000)
    filename: str = Field(min_length=1, max_length=150, pattern=r"^[A-Za-z0-9._-]+\.pdf$")
