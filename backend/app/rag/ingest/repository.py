"""SQL for writing the legal knowledge base as app_admin_ingest (migration 0011)."""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

INGEST_ROLE = "app_admin_ingest"


def create_ingest_engine(database_url: str) -> AsyncEngine:
    url = make_url(database_url)
    if url.drivername != "postgresql+asyncpg" or url.username != INGEST_ROLE:
        raise ValueError(f"Ingest database URL must use postgresql+asyncpg as {INGEST_ROLE}")
    return create_async_engine(database_url, pool_pre_ping=True)


async def upsert_source(conn: AsyncConnection, source: dict[str, Any]) -> UUID:
    inserted = await conn.scalar(
        text(
            """
            INSERT INTO public.legal_sources
              (kind, title, number_year, language, source_url, source_name, external_id,
               current_status, status_note)
            VALUES (:kind, :title, :number_year, :language, :source_url, :source_name, :external_id,
                    :current_status, :status_note)
            ON CONFLICT (source_name, external_id, language) DO UPDATE
              SET current_status = EXCLUDED.current_status, status_note = EXCLUDED.status_note
              WHERE public.legal_sources.current_status = 'unknown'
                AND EXCLUDED.current_status <> 'unknown'
            RETURNING id
            """
        ),
        source,
    )
    if inserted is not None:
        return inserted
    return await conn.scalar(
        text(
            """
            SELECT id FROM public.legal_sources
            WHERE source_name = :source_name AND external_id = :external_id AND language = :language
            """
        ),
        source,
    )


async def current_version(conn: AsyncConnection, source_id: UUID) -> tuple[UUID, int, bytes] | None:
    row = (
        await conn.execute(
            text(
                """
                SELECT id, version_no, content_sha256 FROM public.legal_source_versions
                WHERE legal_source_id = :source_id AND is_current
                FOR UPDATE
                """
            ),
            {"source_id": source_id},
        )
    ).first()
    return (row[0], row[1], bytes(row[2])) if row else None


async def insert_version(
    conn: AsyncConnection,
    source_id: UUID,
    previous: tuple[UUID, int, bytes] | None,
    content_sha256: bytes,
    ingested_by: str,
) -> UUID:
    """Add a new current version; the previous one is kept and marked not current."""
    if previous is not None:
        await conn.execute(
            text("UPDATE public.legal_source_versions SET is_current = false WHERE id = :id"),
            {"id": previous[0]},
        )
    return await conn.scalar(
        text(
            """
            INSERT INTO public.legal_source_versions
              (legal_source_id, version_no, content_sha256, ingested_by, is_current)
            VALUES (:source_id, :version_no, :sha, :ingested_by, true)
            RETURNING id
            """
        ),
        {
            "source_id": source_id,
            "version_no": (previous[1] + 1) if previous else 1,
            "sha": content_sha256,
            "ingested_by": ingested_by,
        },
    )


async def insert_section(conn: AsyncConnection, version_id: UUID, section: dict[str, Any]) -> UUID:
    return await conn.scalar(
        text(
            """
            INSERT INTO public.legal_sections
              (legal_source_version_id, section_key, position, section_number, heading,
               chapter_number, chapter_title, language, text, canonical_section_id,
               status, status_basis, source_url, content_hash)
            VALUES
              (:version_id, :section_key, :position, :section_number, :heading,
               :chapter_number, :chapter_title, :language, :text, :canonical_section_id,
               :status, :status_basis, :source_url, :content_hash)
            RETURNING id
            """
        ),
        {"version_id": version_id, **section},
    )


async def insert_chunks(conn: AsyncConnection, rows: list[dict[str, Any]]) -> None:
    """Chunks start with embedding NULL; the pending-embedding index is the work queue."""
    if not rows:
        return
    await conn.execute(
        text(
            """
            INSERT INTO public.legal_chunks
              (legal_source_version_id, legal_section_id, provision_label, chunk_index,
               text, token_count, content_hash, embedding_model, embedding_version)
            VALUES
              (:version_id, :section_id, :provision_label, :chunk_index,
               :text, :token_count, :content_hash, :embedding_model, :embedding_version)
            """
        ),
        rows,
    )
