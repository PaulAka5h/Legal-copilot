"""Deterministic citation verifier (code, not an LLM). Used by analysis and strategy.

For each cited chunk: it must exist and be readable (RLS), belong to an approved
and current source version, be in force on the incident date (unknown status
is allowed but flagged), and any quote must be an NFC, whitespace-normalized
substring of the stored chunk text. Also scrubs probability language and case
citations when no judgment is in the knowledge base (Rules 1 and 4).
"""

import re
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.search.retrieval import in_force
from app.rag.text import quote_in_text

NO_PRECEDENT_NOTE = "No precedent in knowledge base: no judgments are ingested, so no case law is cited."

_CHUNKS = text(
    """
    SELECT c.id, c.text, sec.section_number, sec.heading, sec.language, sec.source_url, sec.status AS section_status,
           coalesce(sec.effective_from, v.effective_from) AS effective_from,
           coalesce(sec.effective_to, v.effective_to) AS effective_to,
           v.review_status, v.is_current, s.title, s.current_status AS source_status
    FROM public.legal_chunks c
    JOIN public.legal_sections sec ON sec.id = c.legal_section_id
    JOIN public.legal_source_versions v ON v.id = c.legal_source_version_id
    JOIN public.legal_sources s ON s.id = v.legal_source_id
    WHERE c.id = ANY(CAST(:ids AS uuid[])) AND c.is_active
    """
)
_PROBABILITY = re.compile(r"\d{1,3}(?:\.\d+)?\s*%|\bper\s?cent\b|\bprobabilit\w*|\bodds\b|শতাংশ|সম্ভাবনা\s*\d", re.I)
_CASE_CITATION = re.compile(r"\b\d{1,3}\s+(?:DLR|BLD|BLC|MLR|SCOB|BLT|ALR)\b|\b(?:DLR|BLD|BLC|SCOB)\s*\(|\bAIR\s+\d{4}\b"
                            r"|\b[A-Z][a-zA-Z.]+\s+(?:vs?\.?|versus)\s+[A-Z][a-zA-Z.]+")


@dataclass
class Citation:
    chunk_id: UUID
    act_title: str | None = None
    section: str | None = None
    language: str | None = None
    source_url: str | None = None
    quote: str | None = None
    verified: bool = False
    in_force_status: str = "unknown"
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


async def load_chunks(session: AsyncSession, chunk_ids: list[UUID]) -> dict[UUID, dict]:
    if not chunk_ids:
        return {}
    rows = await session.execute(_CHUNKS, {"ids": list({UUID(str(c)) for c in chunk_ids})})
    return {r["id"]: dict(r) for r in rows.mappings()}


def verify_citation(chunk_id: UUID, quote: str | None, chunks: dict[UUID, dict], incident_date: date | None) -> Citation:
    chunk = chunks.get(UUID(str(chunk_id)))
    citation = Citation(chunk_id=UUID(str(chunk_id)), quote=quote)
    if chunk is None:
        citation.failures.append("chunk_not_found")
        return citation
    citation.act_title, citation.section = chunk["title"], chunk["section_number"]
    citation.language, citation.source_url = chunk["language"], chunk["source_url"]
    if chunk["review_status"] != "approved":
        citation.failures.append("source_not_approved")
    if not chunk["is_current"]:
        citation.failures.append("source_version_superseded")
    include, status, warnings = in_force(chunk["section_status"], chunk["source_status"], chunk["effective_from"],
                                         chunk["effective_to"], incident_date)
    citation.in_force_status = status
    citation.warnings.extend(warnings)
    if not include:
        citation.failures.append("not_in_force_on_incident_date")
    if quote is not None and not quote_in_text(quote, chunk["text"]):
        citation.failures.append("quote_not_in_source")
    citation.verified = not citation.failures
    return citation


def scrub(text_value: str, flags: list[str], precedents_available: bool = False) -> str:
    """Remove probability language (Rule 4) and case citations when no judgments are stored (Rule 1)."""
    cleaned = text_value
    if _PROBABILITY.search(cleaned):
        cleaned = _PROBABILITY.sub("[removed: no probabilities]", cleaned)
        flags.append("probability_language_removed")
    if not precedents_available and _CASE_CITATION.search(cleaned):
        cleaned = _CASE_CITATION.sub("[removed: no precedent in knowledge base]", cleaned)
        flags.append("precedent_reference_removed")
    return cleaned


async def judgments_available(session: AsyncSession) -> bool:
    count = await session.scalar(text(
        "SELECT count(*) FROM public.legal_sources s JOIN public.legal_source_versions v ON v.legal_source_id = s.id "
        "WHERE s.kind = 'judgment' AND v.review_status = 'approved' AND v.is_current"
    ))
    return bool(count)
