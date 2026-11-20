"""Ingest validated Act batches: source -> version -> sections -> chunks.

Idempotent: an Act whose content hash equals its current version is skipped.
A changed Act gets a new version; older versions and their rows are kept (Rule 6).
Stored section and chunk text is NFC (app.rag.text); legal_sections.content_hash
is the SHA-256 of the raw scraped text, kept for provenance. Chunk content_hash
is the SHA-256 of the stored (NFC) chunk text, which the embedder keys on.
Status is `unknown` unless the section title is the bdlaws "[Repealed]" marker;
effective dates are not provided by the scraper and stay NULL.
"""

import hashlib
import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from app.rag.ingest import repository as repo
from app.rag.ingest.chunking import (
    EMBEDDING_MODEL,
    EMBEDDING_VERSION,
    TokenCounter,
    chunk_section,
    section_header,
)
from app.rag.ingest.records import ActBatch
from app.rag.text import nfc

SOURCE_NAME = "bdlaws.minlaw.gov.bd"
RECHUNK_NOTE = "Re-chunked: text unchanged, chunking changed (--force-rechunk)"
INGESTED_BY = "app.rag.ingest"
# Fixed namespace so bn and en records of the same section get the same canonical id.
CANONICAL_NAMESPACE = uuid.UUID("5b0f6a3e-7c1d-4f2a-9e8b-2d4c6a8e0f13")
_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_REPEALED_MARKER = re.compile(r"\[\s*repealed\s*\]", re.IGNORECASE)
_ORDINANCE = re.compile(r"\bordinance\b|অধ্যাদেশ", re.IGNORECASE)


@dataclass
class IngestSummary:
    acts_seen: int = 0
    acts_new_version: int = 0
    acts_unchanged: int = 0
    acts_rechunked: int = 0
    acts_skipped_chunk_error: int = 0
    sections: int = 0
    chunks: int = 0
    max_chunk_tokens: int = 0
    repealed_by_title_marker: int = 0
    chunk_errors: list[dict[str, Any]] = field(default_factory=list)


def canonical_section_id(record: dict[str, Any]) -> uuid.UUID:
    """Same id for the bn and en record of a section: language removed, digits normalized."""
    key = record["document_id"].replace(f"-{record['language']}", "", 1).translate(_BN_DIGITS)
    return uuid.uuid5(CANONICAL_NAMESPACE, f"{SOURCE_NAME}:{key}")


def act_content_sha256(records: Iterable[dict[str, Any]]) -> bytes:
    digest = hashlib.sha256()
    for record in records:
        digest.update(record["document_id"].encode("utf-8"))
        digest.update(b"\x00")
        digest.update(hashlib.sha256(record["section_content"].encode("utf-8")).digest())
    return digest.digest()


def source_row(batch: ActBatch, source_name: str = SOURCE_NAME) -> dict[str, Any]:
    first = batch.records[0]
    title = nfc(first["act_name"])
    number, year = first.get("act_number"), first.get("act_year")
    repealed = bool(_REPEALED_MARKER.search(title))
    return {
        "current_status": "repealed" if repealed else "unknown",
        "status_note": "bdlaws title marker [Repealed]" if repealed else None,
        "kind": "ordinance" if _ORDINANCE.search(title) else "act",
        "title": title,
        "number_year": f"{number} of {year}" if number and year else None,
        "language": batch.language,
        "source_url": first["source_url"].split("/section-")[0] + ".html"
        if "/section-" in first["source_url"] else first["source_url"],
        "source_name": source_name,
        "external_id": batch.act_id,
    }


def section_row(record: dict[str, Any], position: int) -> dict[str, Any]:
    heading = nfc(record["section_title"]) if record.get("section_title") else None
    repealed = bool(heading and _REPEALED_MARKER.fullmatch(heading.strip()))
    return {
        "section_key": record["document_id"],
        "position": position,
        "section_number": record.get("section_number"),
        "heading": heading,
        "chapter_number": record.get("chapter_number"),
        "chapter_title": nfc(record["chapter_title"]) if record.get("chapter_title") else None,
        "language": record["language"],
        "text": nfc(record["section_content"]),
        "canonical_section_id": canonical_section_id(record),
        "status": "repealed" if repealed else "unknown",
        "status_basis": "section_title_marker" if repealed else None,
        "source_url": record["source_url"],
        "content_hash": hashlib.sha256(record["section_content"].encode("utf-8")).hexdigest(),
    }


def plan_chunks(record: dict[str, Any], counter: TokenCounter) -> list[dict[str, Any]]:
    header = section_header(
        record["act_name"], record.get("act_year"), record.get("section_number"), record.get("section_title")
    )
    provision = f"Section {record['section_number']}" if record.get("section_number") else None
    return [
        {
            "provision_label": provision,
            "chunk_index": chunk.index,
            "text": chunk.text,
            "token_count": chunk.token_count,
            "content_hash": hashlib.sha256(chunk.text.encode("utf-8")).hexdigest(),
            "embedding_model": EMBEDDING_MODEL,
            "embedding_version": EMBEDDING_VERSION,
        }
        for chunk in chunk_section(header, nfc(record["section_content"]), counter)
    ]


def _plan_batch(
    batch: ActBatch, counter: TokenCounter, summary: IngestSummary
) -> list[tuple[dict, list[dict]]] | None:
    """Plan every section of the Act, or return None so no partial version is written."""
    planned = []
    for position, record in enumerate(batch.records):
        try:
            chunks = plan_chunks(record, counter)
        except ValueError as error:
            summary.chunk_errors.append({"document_id": record["document_id"], "issue": str(error)})
            return None
        planned.append((section_row(record, position), chunks))
    return planned


def _count(summary: IngestSummary, planned: list[tuple[dict, list[dict]]]) -> None:
    summary.sections += len(planned)
    for section, chunks in planned:
        summary.chunks += len(chunks)
        summary.max_chunk_tokens = max([summary.max_chunk_tokens, *(c["token_count"] for c in chunks)])
        summary.repealed_by_title_marker += section["status"] == "repealed"


async def ingest_batches(
    batches: Iterable[ActBatch],
    counter: TokenCounter,
    engine: AsyncEngine | None,
    limit: int | None = None,
    source_name: str = SOURCE_NAME,
    force_rechunk: bool = False,
) -> IngestSummary:
    """Ingest up to `limit` Acts. With engine=None this is a dry run (plan and count only).

    force_rechunk adds a new version even when the text is unchanged, so a
    chunking change (header, token budget) reaches the stored chunks. The new
    version starts pending and needs approval like any other.
    """
    summary = IngestSummary()
    for batch in batches:
        if limit is not None and summary.acts_seen >= limit:
            break
        summary.acts_seen += 1
        planned = _plan_batch(batch, counter, summary)
        if planned is None:
            summary.acts_skipped_chunk_error += 1
            continue
        if engine is None:
            _count(summary, planned)
            continue

        sha = act_content_sha256(batch.records)
        async with engine.begin() as conn:
            source_id = await repo.upsert_source(conn, source_row(batch, source_name))
            previous = await repo.current_version(conn, source_id)
            rechunk = previous is not None and previous[2] == sha
            if rechunk and not force_rechunk:
                summary.acts_unchanged += 1
                continue
            note = RECHUNK_NOTE if rechunk else None
            version_id = await repo.insert_version(conn, source_id, previous, sha, INGESTED_BY, note)
            for section, chunks in planned:
                section_id = await repo.insert_section(conn, version_id, section)
                await repo.insert_chunks(
                    conn, [{**c, "version_id": version_id, "section_id": section_id} for c in chunks]
                )
        summary.acts_new_version += 1
        summary.acts_rechunked += rechunk
        _count(summary, planned)
    return summary
