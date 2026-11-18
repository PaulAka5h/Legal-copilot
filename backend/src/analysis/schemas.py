"""Data Models and Schemas for Case Analysis & Fact Extraction Engine.

Follows database specification in DOCS/database.md:
- analyses
- claims
- claim_sources
- verification_results
- timeline events & contradictions
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class ClaimType(str, Enum):
    FACT_FROM_DOCUMENT = "fact_from_document"
    LAWYER_ENTERED = "lawyer_entered"
    VERIFIED_RECORD = "verified_record"
    INFERENCE = "inference"
    ASSUMPTION = "assumption"
    PREDICTION = "prediction"


class ConfidenceLabel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNVERIFIED = "unverified"


class VerificationVerdict(str, Enum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CANNOT_VERIFY = "cannot_verify"


class ClaimSourceItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_kind: str = "document_chunk"  # 'document_chunk' | 'legal_source_version' | 'lawyer_note'
    document_chunk_id: Optional[str] = None
    document_name: str = "Case Record"
    page_number: int = 1
    quote: str = ""
    legal_source_version_id: Optional[str] = None
    provision_label: Optional[str] = None
    source_url: Optional[str] = None


class ClaimItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    text: str
    claim_type: ClaimType = ClaimType.FACT_FROM_DOCUMENT
    confidence_label: ConfidenceLabel = ConfidenceLabel.HIGH
    needs_lawyer_review: bool = False
    sources: List[ClaimSourceItem] = Field(default_factory=list)
    verification_verdict: VerificationVerdict = VerificationVerdict.SUPPORTED


class TimelineEventItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    event_date: str  # ISO 8601 YYYY-MM-DD
    raw_date_text: str = ""
    title: str
    description: str
    actor: str = "Unspecified"
    source_document_id: Optional[str] = None
    source_name: str = "Case Document"
    source_page: int = 1
    confidence: str = "high"
    is_anomaly: bool = False
    anomaly_reason: Optional[str] = None


class TimelineExtractionResult(BaseModel):
    events: List[TimelineEventItem] = Field(default_factory=list)


class ContradictionItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    issue: str
    statement_a: str
    source_a_document: str = "Document A"
    source_a_page: int = 1
    statement_b: str
    source_b_document: str = "Document B"
    source_b_page: int = 1
    severity: str = "medium"  # high | medium | low
    analysis: str = ""


class EvidenceGapItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    missing_item: str
    statutory_requirement: str
    impact: str


class ContradictionExtractionResult(BaseModel):
    contradictions: List[ContradictionItem] = Field(default_factory=list)
    gaps: List[EvidenceGapItem] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    item: str
    source: str
    page: int = 1
    relevance: str
    evidence_type: str = "supporting"  # "supporting" | "weakening"


class CaseAnalysisExtractionResult(BaseModel):
    """Raw structured extraction from LLM."""
    client_position: str
    factual_summary: str
    legal_issues: List[str] = Field(default_factory=list)
    key_claims: List[Dict[str, Any]] = Field(default_factory=list)
    supporting_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    weakening_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    suggested_next_steps: List[str] = Field(default_factory=list)


class LegalResearchCitation(BaseModel):
    act_id: str
    act_name: str
    section: str
    section_title: str
    relevance_reason: str
    source_url: str
    is_verified: bool = True


class CaseAnalysisRecord(BaseModel):
    """Full persisted case analysis record."""
    id: UUID = Field(default_factory=uuid4)
    case_id: str
    organization_id: str = "default_org"
    version: int = 1
    supersedes_id: Optional[UUID] = None
    trigger: str = "initial"
    client_position: str
    factual_summary: str
    legal_issues: List[str] = Field(default_factory=list)
    claims: List[ClaimItem] = Field(default_factory=list)
    timeline: List[TimelineEventItem] = Field(default_factory=list)
    contradictions: List[ContradictionItem] = Field(default_factory=list)
    gaps: List[EvidenceGapItem] = Field(default_factory=list)
    evidence: List[EvidenceItem] = Field(default_factory=list)
    citations: List[LegalResearchCitation] = Field(default_factory=list)
    suggested_next_steps: List[str] = Field(default_factory=list)
    review_status: str = "draft"  # 'draft' | 'lawyer_reviewed' | 'lawyer_rejected'
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    ai_run_id: Optional[UUID] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
