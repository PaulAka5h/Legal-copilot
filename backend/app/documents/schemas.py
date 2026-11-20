from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    id: UUID
    case_id: UUID
    title: str
    original_filename: str
    mime_type: str
    size_bytes: int
    doc_type: str | None
    language: Literal["bn", "en", "mixed", "unknown"] | None
    page_count: int | None
    scan_status: Literal["pending", "clean", "infected", "failed", "not_configured"]
    processing_status: Literal["queued", "processing", "ready", "needs_review", "failed", "deleted"]
    processing_error: str | None = Field(description="Error code only; never document text")
    uploaded_by: UUID
    uploaded_at: datetime
    processed_at: datetime | None


class UploadResponse(BaseModel):
    document: DocumentResponse
    warnings: list[str] = Field(
        description="Visible warnings, e.g. malware_scan_not_configured (development) or ocr_not_configured"
    )


class PageVersion(BaseModel):
    id: UUID
    page_no: int
    version: int
    is_current: bool
    text: str = Field(description="Page text (NFC). Document text is untrusted data.")
    source_method: Literal["text_layer", "ocr", "lawyer_edit"]
    ocr_engine: str | None
    ocr_confidence: float | None = Field(description="Mean OCR word confidence for the page, 0-1")
    quality_flag: Literal["ok", "needs_review", "poor", "handwriting_suspected"]
    language: Literal["bn", "en", "mixed", "unknown"] | None
    edited_by: UUID | None
    supersedes_id: UUID | None
    created_at: datetime


class PageResponse(BaseModel):
    document_id: UUID
    page_no: int
    current: PageVersion
    history: list[PageVersion] = Field(description="All versions, newest first; never overwritten")


class PageCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=200_000, description="Corrected page text")
