"""SQL for documents and extracted pages. Runs as app_user inside user_transaction (RLS)."""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

DOCUMENT_FIELDS = """
    d.id, d.case_id, d.title, d.original_filename, d.mime_type, d.size_bytes, d.storage_key,
    d.doc_type, d.language, d.page_count, d.scan_status, d.processing_status, d.processing_error,
    d.uploaded_by, d.uploaded_at, d.processed_at
"""


async def case_status(session: AsyncSession, case_id: UUID) -> tuple[str, UUID] | None:
    row = (
        await session.execute(
            text("SELECT status, organization_id FROM public.cases WHERE id = :id"), {"id": case_id}
        )
    ).first()
    return (row[0], row[1]) if row else None


async def find_by_sha(session: AsyncSession, case_id: UUID, sha256: bytes) -> UUID | None:
    return await session.scalar(
        text("SELECT id FROM public.documents WHERE case_id = :c AND sha256 = :s"),
        {"c": case_id, "s": sha256},
    )


async def insert_document(session: AsyncSession, values: dict[str, Any]) -> None:
    await session.execute(
        text(
            """
            INSERT INTO public.documents
              (id, case_id, organization_id, title, original_filename, mime_type, size_bytes,
               sha256, storage_key, page_count, scan_status, processing_status, uploaded_by)
            VALUES
              (:id, :case_id, :organization_id, :title, :original_filename, :mime_type, :size_bytes,
               :sha256, :storage_key, :page_count, :scan_status, 'queued', :uploaded_by)
            """
        ),
        values,
    )


async def get_document(session: AsyncSession, case_id: UUID, document_id: UUID) -> dict | None:
    row = (
        await session.execute(
            text(f"SELECT {DOCUMENT_FIELDS} FROM public.documents d WHERE d.id = :d AND d.case_id = :c"),
            {"d": document_id, "c": case_id},
        )
    ).mappings().first()
    return dict(row) if row else None


async def list_documents(session: AsyncSession, case_id: UUID) -> list[dict]:
    rows = await session.execute(
        text(f"SELECT {DOCUMENT_FIELDS} FROM public.documents d WHERE d.case_id = :c ORDER BY d.uploaded_at, d.id"),
        {"c": case_id},
    )
    return [dict(r) for r in rows.mappings()]


async def set_processing_state(session: AsyncSession, document_id: UUID, **fields: Any) -> None:
    allowed = {"processing_status", "processing_error", "page_count", "language", "processed_at"}
    assert set(fields) <= allowed, fields
    assignments = ", ".join(f"{k} = :{k}" for k in fields)
    await session.execute(
        text(f"UPDATE public.documents SET {assignments} WHERE id = :id"), {"id": document_id, **fields}
    )


async def count_pages(session: AsyncSession, document_id: UUID) -> int:
    return await session.scalar(
        text("SELECT count(*) FROM public.extracted_pages WHERE document_id = :d"), {"d": document_id}
    )


async def insert_page(session: AsyncSession, values: dict[str, Any]) -> UUID:
    return await session.scalar(
        text(
            """
            INSERT INTO public.extracted_pages
              (document_id, case_id, organization_id, page_no, version, is_current, text,
               source_method, ocr_engine, ocr_confidence, quality_flag, language, edited_by, supersedes_id)
            VALUES
              (:document_id, :case_id, :organization_id, :page_no, :version, true, :text,
               :source_method, :ocr_engine, :ocr_confidence, :quality_flag, :language, :edited_by, :supersedes_id)
            RETURNING id
            """
        ),
        values,
    )


PAGE_FIELDS = """
    p.id, p.document_id, p.page_no, p.version, p.is_current, p.text, p.source_method, p.ocr_engine,
    p.ocr_confidence, p.quality_flag, p.language, p.edited_by, p.supersedes_id, p.created_at
"""


async def page_versions(session: AsyncSession, case_id: UUID, document_id: UUID, page_no: int) -> list[dict]:
    rows = await session.execute(
        text(
            f"""
            SELECT {PAGE_FIELDS} FROM public.extracted_pages p
            WHERE p.case_id = :c AND p.document_id = :d AND p.page_no = :n
            ORDER BY p.version DESC
            """
        ),
        {"c": case_id, "d": document_id, "n": page_no},
    )
    return [dict(r) for r in rows.mappings()]


async def retire_page(session: AsyncSession, page_id: UUID) -> None:
    await session.execute(
        text("UPDATE public.extracted_pages SET is_current = false WHERE id = :id AND is_current"),
        {"id": page_id},
    )


async def current_pages(session: AsyncSession, case_id: UUID, document_ids: list[UUID] | None) -> list[dict]:
    rows = await session.execute(
        text(
            f"""
            SELECT {PAGE_FIELDS} FROM public.extracted_pages p
            JOIN public.documents d ON d.id = p.document_id AND d.case_id = p.case_id
            WHERE p.case_id = :c AND p.is_current
              AND d.processing_status IN ('ready', 'needs_review')
              AND (CAST(:ids AS uuid[]) IS NULL OR p.document_id = ANY(CAST(:ids AS uuid[])))
            ORDER BY d.uploaded_at, p.document_id, p.page_no
            """
        ),
        {"c": case_id, "ids": document_ids},
    )
    return [dict(r) for r in rows.mappings()]
