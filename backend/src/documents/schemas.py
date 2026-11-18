"""Domain schemas for Document Management and Processing Pipeline (Phase 3).

Aligned with DOCS/TRD.md Section 5 and DOCS/database.md:
- documents
- extracted_pages
- document_chunks
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class ExtractionMethod(str, Enum):
    TEXT_LAYER = "text_layer"
    OCR = "ocr"
    DOCX_PARSER = "docx_parser"
    HYBRID = "hybrid"


class QualityFlag(str, Enum):
    GOOD = "good"
    NEEDS_REVIEW = "needs_review"
    UNCERTAIN = "uncertain"  # e.g. for handwriting or poor scans


class DocumentMetadata(BaseModel):
    """Metadata describing an uploaded original legal document."""

    id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    organization_id: Optional[UUID] = None
    original_filename: str
    file_size_bytes: int
    mime_type: str
    sha256_hash: str
    storage_path: str
    total_pages: Optional[int] = None
    status: DocumentStatus = DocumentStatus.PROCESSING
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExtractedPage(BaseModel):
    """Extracted text and quality analysis for a single page of a document."""

    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    page_number: int  # 1-indexed exact physical page
    text: str
    source_method: ExtractionMethod
    ocr_confidence: Optional[float] = None  # 0.0 - 1.0 (None if digital text)
    quality_flag: QualityFlag = QualityFlag.GOOD
    language: str = "en"  # "en", "bn", or "mixed"
    char_count: int = 0
    word_count: int = 0
    has_images: bool = False
    is_uncertain_handwriting: bool = False
    version: int = 1


class DocumentChunk(BaseModel):
    """A single retrieval chunk derived from an extracted page (case-scoped)."""

    id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    organization_id: Optional[UUID] = None
    document_id: UUID
    page_number: int
    char_start: int
    char_end: int
    text: str
    token_count: int
    embedding_model: str = "intfloat/multilingual-e5-large"
    embedding_version: int = 1
    is_active: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)
