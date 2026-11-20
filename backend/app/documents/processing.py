"""process_document(document_id): the single processing entry point.

Runs synchronously from the upload request for now; the ARQ worker will call the
same function later (DOCS/TRD.md). A crash leaves the document 'processing';
app.documents.recovery marks it failed after a timeout, and this function then
retries it (failed documents without pages are processed again). It runs as the requesting user, so RLS
applies. It is idempotent: only queued or failed documents without pages are
processed. Errors are stored as codes, never with document text.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.repository import write_audit_event
from app.config import Settings
from app.database import user_transaction
from app.documents import repository as repo
from app.documents.extraction import document_language, extract_pages
from app.documents.storage import ObjectStore

logger = logging.getLogger("app.documents")


class ScannerNotConfigured(RuntimeError):
    """No malware scanner configured; production must refuse uploads and processing."""


def scan_status_for(settings: Settings) -> str:
    """Scan result for a new upload. Only 'not_configured' exists until ClamAV is wired."""
    if settings.malware_scanner == "none":
        if settings.app_env == "production":
            raise ScannerNotConfigured("A malware scanner is required in production")
        return "not_configured"
    raise ScannerNotConfigured(f"Unsupported scanner {settings.malware_scanner!r}")


@dataclass
class ProcessResult:
    document_id: UUID
    processing_status: str
    page_count: int = 0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


async def process_document(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    document_id: UUID,
    case_id: UUID,
    acting_user_id: UUID,
    store: ObjectStore,
    settings: Settings,
) -> ProcessResult:
    async with user_transaction(session_factory, acting_user_id) as session:
        document = await repo.get_document(session, case_id, document_id)
        if document is None:
            raise LookupError("document not found")
        if document["processing_status"] not in ("queued", "failed") or await repo.count_pages(session, document_id):
            return ProcessResult(document_id, document["processing_status"], document["page_count"] or 0)
        if settings.app_env == "production" and document["scan_status"] != "clean":
            await repo.set_processing_state(session, document_id, processing_status="failed",
                                            processing_error="malware_scan_required")
            raise ScannerNotConfigured("Unscanned documents are not processed in production")
        await repo.set_processing_state(session, document_id, processing_status="processing",
                                        processing_error=None, processing_started_at=datetime.now(UTC))
        organization_id = (await repo.case_status(session, case_id))[1]

    try:
        data = await asyncio.to_thread(store.get, document["storage_key"])
        pages, warnings = await asyncio.to_thread(
            extract_pages, data, document["mime_type"], settings.ocr_languages
        )
    except Exception as error:
        logger.warning("document.processing_failed", extra={"event": "document.processing_failed",
                                                            "error_type": type(error).__name__})
        async with user_transaction(session_factory, acting_user_id) as session:
            await repo.set_processing_state(session, document_id, processing_status="failed",
                                            processing_error="extraction_error")
        return ProcessResult(document_id, "failed", error="extraction_error")

    if document["scan_status"] == "not_configured":
        warnings.insert(0, "malware_scan_not_configured: file was not scanned (development only)")
    needs_review = any(p.quality_flag != "ok" for p in pages)
    status = "needs_review" if needs_review else "ready"

    async with user_transaction(session_factory, acting_user_id) as session:
        for page in pages:
            await repo.insert_page(session, {
                "document_id": document_id, "case_id": case_id, "organization_id": organization_id,
                "page_no": page.page_no, "version": 1, "text": page.text,
                "source_method": page.source_method, "ocr_engine": page.ocr_engine,
                "ocr_confidence": page.ocr_confidence, "quality_flag": page.quality_flag,
                "language": page.language, "edited_by": None, "supersedes_id": None,
            })
        await repo.set_processing_state(
            session, document_id, processing_status=status, page_count=len(pages),
            language=document_language(pages), processed_at=datetime.now(UTC),
        )
        await write_audit_event(
            session, action="document.processed", actor_user_id=acting_user_id, actor_role="lawyer",
            object_type="document", object_id=document_id, case_id=case_id, ip_address=None,
            user_agent=None, request_id=None,
            details={"pages": len(pages), "status": status,
                     "ocr_pages": sum(p.source_method == "ocr" for p in pages)},
        )
    return ProcessResult(document_id, status, len(pages), warnings)
