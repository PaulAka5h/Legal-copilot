from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ResearchSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(min_length=2, max_length=1000, description="Legal question or keywords, Bangla or English")
    language: Literal["bn", "en"] | None = Field(
        default=None, description="Only search statutes in this language; omit for both"
    )
    incident_date: date | None = Field(
        default=None, description="Date of the incident; sections not in force on this date are excluded"
    )
    k: int = Field(default=10, ge=1, le=20, description="Number of sections to return")


class AlternateLanguageCitation(BaseModel):
    chunk_id: UUID
    language: Literal["bn", "en"]
    section_number: str | None
    source_url: str


class ResearchSearchHit(BaseModel):
    chunk_id: UUID = Field(description="Cited chunk; the text below is its exact stored text")
    section_id: UUID
    canonical_section_id: UUID = Field(description="Shared by the bn and en versions of the section")
    version_id: UUID
    version_no: int
    act_id: str = Field(description="bdlaws Act ID")
    act_title: str
    section_number: str | None
    heading: str | None
    language: Literal["bn", "en"]
    source_url: str = Field(description="Official source page for the section")
    text: str = Field(description="Stored chunk text (NFC), including the section header")
    fused_score: float = Field(description="Reciprocal Rank Fusion score (k=60); a ranking signal, not a probability")
    dense_rank: int | None = Field(description="Rank in vector search, if retrieved there")
    sparse_rank: int | None = Field(description="Rank in full-text search, if retrieved there")
    dense_similarity: float | None = Field(
        description="Cosine similarity to the query (e5), if retrieved by vector search; a relevance signal, not a probability"
    )
    rerank_score: float | None = Field(description="Cross-encoder score; null with the mock reranker")
    in_force_status: Literal["in_force", "unknown", "amended", "partly_repealed", "repealed"]
    warnings: list[str] = Field(description="e.g. amendment_status_unknown, effective_dates_unknown")
    alternates: list[AlternateLanguageCitation] = Field(
        description="Same section in the other language, to cite both"
    )
    statement_type: Literal["retrieved_source"] = "retrieved_source"
    verification: Literal["unverified"] = Field(
        default="unverified",
        description="Retrieved text is not a verified legal conclusion; citation checks run in analysis",
    )


class ResearchSearchResponse(BaseModel):
    case_id: UUID
    results: list[ResearchSearchHit]
    warnings: list[str]
    reranker: str
    embedding_model: str
    searched_versions: int = Field(description="Approved, current source versions searched")
    source_scope: Literal["approved_statutes_only"] = Field(
        default="approved_statutes_only",
        description="Only approved statute versions are searched; no judgments are in the knowledge base",
    )
