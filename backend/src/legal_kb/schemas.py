"""Domain schemas for Legal Knowledge Base ingestion, chunking, and retrieval.

Aligned with DOCS/database.md:
- legal_sources
- legal_source_versions
- legal_chunks
- Amendment & version aware metadata fields.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class LegalKind(str, Enum):
    CONSTITUTION = "constitution"
    ACT = "act"
    ORDINANCE = "ordinance"
    CODE = "code"
    RULE = "rule"
    REGULATION = "regulation"
    NOTIFICATION = "notification"
    JUDGMENT = "judgment"
    OTHER = "other"


class LegalLanguage(str, Enum):
    BN = "bn"
    EN = "en"
    BOTH = "both"


class LegalStatus(str, Enum):
    IN_FORCE = "in_force"
    AMENDED = "amended"
    REPEALED = "repealed"
    PARTLY_REPEALED = "partly_repealed"
    UNKNOWN = "unknown"


class ScrapedSectionRecord(BaseModel):
    """Raw schema emitted by data-scrapper/data/processed/sections.jsonl."""

    document_id: str = Field(description="Deterministic ID e.g. bd-act-1-sec-1-en")
    act_id: str
    act_name: str
    act_number: Optional[str] = None
    act_year: Optional[str] = None
    language: LegalLanguage
    chapter_number: Optional[str] = None
    chapter_title: Optional[str] = None
    section_number: Optional[str] = None
    section_title: Optional[str] = None
    section_content: str
    subsections: List[Dict[str, Any]] = Field(default_factory=list)
    source_url: str
    source_website: str = "bdlaws.minlaw.gov.bd"
    enactment_date: Optional[str] = None
    scraped_at: Optional[datetime] = None
    content_hash: str


class LegalSourcePayload(BaseModel):
    """Normalized payload corresponding to legal_sources table."""

    id: UUID = Field(default_factory=uuid4)
    kind: LegalKind = LegalKind.ACT
    title: str
    title_bn: Optional[str] = None
    short_title: Optional[str] = None
    citation: Optional[str] = None
    number_year: Optional[str] = None
    language: LegalLanguage
    current_status: LegalStatus = LegalStatus.IN_FORCE
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    source_url: Optional[str] = None
    source_name: str = "bdlaws.minlaw.gov.bd"
    licence_note: Optional[str] = "Official legal text published by Government of Bangladesh"


class LegalChunkPayload(BaseModel):
    """Normalized payload corresponding to legal_chunks table with amendment-aware metadata."""

    id: UUID = Field(default_factory=uuid4)
    legal_source_id: Optional[UUID] = None
    act_id: Optional[str] = None
    act_name: str = ""
    act_name_bn: Optional[str] = None
    act_year: Optional[str] = None
    chapter: Optional[str] = None
    section: Optional[str] = None
    subsection: Optional[str] = None
    clause: Optional[str] = None
    language: LegalLanguage = LegalLanguage.EN
    jurisdiction: str = "Bangladesh"
    parent_id: Optional[UUID] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    is_current: bool = True
    source_page: Optional[int] = None
    document_version: int = 1
    provision_label: Optional[str] = None  # e.g. "Section 138"
    chunk_index: int = 0
    text: str
    token_count: int = 0
    source_url: str = ""
    content_hash: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
