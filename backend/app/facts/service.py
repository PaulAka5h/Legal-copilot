"""Fact extraction runs and lawyer review.

Extraction: pages -> batches -> extractor JSON -> Pydantic validation (one retry
per batch; a second failure marks the run extraction_failed and stores nothing)
-> deterministic quote check against the exact page version -> draft facts.
AI output is always a draft (Rule 5). Prompts, outputs, and page text are never
logged or stored on the run; the run keeps an input hash only.
"""

import asyncio
import hashlib
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.repository import write_audit_event
from app.database import user_transaction
from app.documents import repository as docs
from app.facts import repository as repo
from app.facts.extractor import PROMPT_VERSION, FactExtractor, PageInput, batch_pages
from app.facts.schemas import ExtractionOutput, FactSourceIn
from app.rag.text import normalize_for_match, quote_in_text

MAX_ATTEMPTS = 2  # first try plus one retry


class FactError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass
class ExtractionResult:
    run_id: UUID
    status: str
    attempts: int
    pages_read: int
    fact_ids: list[UUID]
    source_check_failed: int


def _input_hash(pages: list[PageInput]) -> bytes:
    digest = hashlib.sha256(PROMPT_VERSION.encode())
    for page in sorted(pages, key=lambda p: str(p.page_id)):
        digest.update(f"{page.page_id}:{page.version}".encode())
    return digest.digest()


def check_sources(statement_type: str, sources: list[dict], pages: dict[tuple[UUID, int], PageInput]) -> tuple[str, list[dict]]:
    """Attach page ids and quote_check to each source; return (fact source_check, sources)."""
    checked = []
    for source in sources:
        page = pages.get((UUID(str(source["document_id"])), source["page_no"]))
        passed = page is not None and quote_in_text(source["quote"], page.text)
        checked.append({**source, "page_id": page.page_id if page else None,
                        "quote_check": "passed" if passed else "failed"})
    if not checked:
        return ("failed" if statement_type == "document_says" else "not_applicable"), checked
    return ("passed" if all(s["quote_check"] == "passed" for s in checked) else "failed"), checked


async def _run_extractor(extractor: FactExtractor, batch: list[PageInput]) -> tuple[ExtractionOutput | None, int]:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            raw = await asyncio.to_thread(extractor.extract_batch, batch)
            return ExtractionOutput.model_validate_json(raw), attempt
        except (ValidationError, ValueError):
            continue
    return None, MAX_ATTEMPTS


async def run_extraction(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    case_id: UUID,
    organization_id: UUID,
    user_id: UUID,
    document_ids: list[UUID] | None,
    extractor: FactExtractor,
) -> ExtractionResult:
    async with user_transaction(session_factory, user_id) as session:
        rows = await docs.current_pages(session, case_id, document_ids)
        pages = [PageInput(r["id"], r["document_id"], r["page_no"], r["version"], r["text"])
                 for r in rows if r["text"].strip()]
        if not pages:
            raise FactError(409, "No processed page text to read in the selected documents.")
        run_id = await repo.create_run(session, {
            "case_id": case_id, "organization_id": organization_id, "requested_by": user_id,
            "provider": extractor.provider, "model": extractor.model, "prompt_version": PROMPT_VERSION,
            "input_hash": _input_hash(pages),
            "settings": {"document_ids": [str(d) for d in document_ids] if document_ids else None,
                         "pages": len(pages), "origin": extractor.origin},
        })

    by_page = {(p.document_id, p.page_no): p for p in pages}
    planned: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    attempts_total = 0
    for batch in batch_pages(pages):
        output, attempts = await _run_extractor(extractor, batch)
        attempts_total += attempts
        if output is None:
            async with user_transaction(session_factory, user_id) as session:
                await repo.finish_run(session, run_id, "extraction_failed", attempts_total, "invalid_model_output")
                await write_audit_event(
                    session, action="facts.extraction_failed", actor_user_id=user_id, actor_role="lawyer",
                    object_type="ai_run", object_id=run_id, case_id=case_id, ip_address=None, user_agent=None,
                    request_id=None, details={"attempts": attempts_total, "pages": len(pages)},
                )
            return ExtractionResult(run_id, "extraction_failed", attempts_total, len(pages), [], 0)
        batch_pages_by_key = {(p.document_id, p.page_no): p for p in batch}
        for fact in output.facts:
            key = (fact.category, normalize_for_match(fact.statement))
            if key in seen:
                continue
            seen.add(key)
            source_check, sources = check_sources(
                fact.statement_type, [s.model_dump() for s in fact.sources], batch_pages_by_key
            )
            planned.append({"fact": fact, "source_check": source_check, "sources": sources})

    fact_ids: list[UUID] = []
    async with user_transaction(session_factory, user_id) as session:
        for item in planned:
            fact = item["fact"]
            fact_id = await repo.insert_fact(session, {
                "case_id": case_id, "organization_id": organization_id, "lineage_id": uuid4(), "version": 1,
                "supersedes_id": None, "category": fact.category, "statement": fact.statement,
                "attributes": fact.attributes.model_dump(exclude_none=True),
                "statement_type": fact.statement_type, "fact_status": "undisputed", "origin": extractor.origin,
                "source_check": item["source_check"], "extraction_run_id": run_id, "created_by": user_id,
            })
            for source in item["sources"]:
                await _insert_page_source(session, fact_id, case_id, organization_id, source, by_page)
            fact_ids.append(fact_id)
        await repo.finish_run(session, run_id, "succeeded", attempts_total, None)
        failed = sum(1 for i in planned if i["source_check"] == "failed")
        await write_audit_event(
            session, action="facts.extracted", actor_user_id=user_id, actor_role="lawyer", object_type="ai_run",
            object_id=run_id, case_id=case_id, ip_address=None, user_agent=None, request_id=None,
            details={"facts": len(fact_ids), "source_check_failed": failed, "pages": len(pages),
                     "attempts": attempts_total, "origin": extractor.origin},
        )
    return ExtractionResult(run_id, "succeeded", attempts_total, len(pages), fact_ids, failed)


async def _insert_page_source(session, fact_id, case_id, organization_id, source, by_page) -> None:
    page = by_page.get((UUID(str(source["document_id"])), source["page_no"]))
    if page is None:
        # The page is not in this case's processed pages: keep the claim visible but unverifiable.
        await repo.insert_source(session, {
            "fact_id": fact_id, "case_id": case_id, "organization_id": organization_id,
            "source_kind": "lawyer_note", "document_id": None, "page_id": None, "page_no": None,
            "quote": source["quote"][:2000], "quote_check": "not_applicable",
        })
        return
    await repo.insert_source(session, {
        "fact_id": fact_id, "case_id": case_id, "organization_id": organization_id,
        "source_kind": "document_page", "document_id": page.document_id, "page_id": page.page_id,
        "page_no": page.page_no, "quote": source["quote"][:2000], "quote_check": source["quote_check"],
    })


async def _pages_for_sources(session: AsyncSession, case_id: UUID, sources: list[FactSourceIn]) -> dict:
    ids = list({s.document_id for s in sources}) or None
    rows = await docs.current_pages(session, case_id, ids) if sources else []
    return {(r["document_id"], r["page_no"]): PageInput(r["id"], r["document_id"], r["page_no"], r["version"], r["text"])
            for r in rows}


async def create_lawyer_fact(session: AsyncSession, *, case_id: UUID, organization_id: UUID, user_id: UUID,
                             payload, lineage_id: UUID | None = None, version: int = 1,
                             supersedes_id: UUID | None = None) -> UUID:
    pages = await _pages_for_sources(session, case_id, payload.sources)
    missing = [(str(src.document_id), src.page_no) for src in payload.sources
               if (src.document_id, src.page_no) not in pages]
    if missing:
        raise FactError(422, f"Cited pages are not processed pages of this case: {missing}")
    source_check, sources = check_sources(payload.statement_type, [s.model_dump() for s in payload.sources], pages)
    fact_id = await repo.insert_fact(session, {
        "case_id": case_id, "organization_id": organization_id, "lineage_id": lineage_id or uuid4(),
        "version": version, "supersedes_id": supersedes_id, "category": payload.category,
        "statement": payload.statement, "attributes": payload.attributes.model_dump(exclude_none=True),
        "statement_type": payload.statement_type, "fact_status": payload.fact_status, "origin": "lawyer",
        "source_check": source_check, "extraction_run_id": None, "created_by": user_id,
    })
    for source in sources:
        await _insert_page_source(session, fact_id, case_id, organization_id, source, pages)
    return fact_id


async def edit_fact(session: AsyncSession, *, case_id: UUID, organization_id: UUID, user_id: UUID,
                    current: dict, payload) -> UUID:
    """Insert version n+1. Statement or source changes make it a lawyer fact."""
    if not current["is_current"]:
        raise FactError(409, "Only the current version can be edited.")
    changes = payload.model_dump(exclude_unset=True)
    content_changed = any(k in changes for k in ("statement", "sources", "statement_type"))
    if not await repo.retire_fact(session, current["id"]):
        raise FactError(409, "The fact was changed by someone else; reload and try again.")

    if content_changed:
        from app.facts.schemas import FactAttributes, FactCreateRequest

        base_sources = [FactSourceIn(document_id=s["document_id"], page_no=s["page_no"], quote=s["quote"])
                        for s in current["sources"] if s["source_kind"] == "document_page"]
        merged = FactCreateRequest(
            category=changes.get("category", current["category"]),
            statement=changes.get("statement", current["statement"]),
            statement_type=changes.get("statement_type", "lawyer_entered"),
            attributes=payload.attributes if "attributes" in changes else FactAttributes(**current["attributes"]),
            fact_status=changes.get("fact_status", current["fact_status"]),
            sources=payload.sources if "sources" in changes else base_sources,
        )
        return await create_lawyer_fact(
            session, case_id=case_id, organization_id=organization_id, user_id=user_id, payload=merged,
            lineage_id=current["lineage_id"], version=current["version"] + 1, supersedes_id=current["id"],
        )

    # Metadata-only edit: provenance, statement type and sources carry over unchanged.
    fact_id = await repo.insert_fact(session, {
        "case_id": case_id, "organization_id": organization_id, "lineage_id": current["lineage_id"],
        "version": current["version"] + 1, "supersedes_id": current["id"],
        "category": changes.get("category", current["category"]), "statement": current["statement"],
        "attributes": (payload.attributes.model_dump(exclude_none=True) if "attributes" in changes
                       else current["attributes"]),
        "statement_type": current["statement_type"], "fact_status": changes.get("fact_status", current["fact_status"]),
        "origin": current["origin"], "source_check": current["source_check"],
        "extraction_run_id": current["extraction_run_id"], "created_by": user_id,
    })
    for source in current["sources"]:
        await repo.insert_source(session, {
            "fact_id": fact_id, "case_id": case_id, "organization_id": organization_id,
            "source_kind": source["source_kind"], "document_id": source["document_id"],
            "page_id": source["page_id"], "page_no": source["page_no"], "quote": source["quote"],
            "quote_check": source["quote_check"],
        })
    return fact_id


async def review(session: AsyncSession, *, current: dict, status: str, user_id: UUID, note: str | None) -> None:
    if not current["is_current"]:
        raise FactError(409, "Only the current version can be reviewed.")
    if current["review_status"] != "draft":
        raise FactError(409, "This version was already reviewed; edit it to create a new draft version.")
    if (status == "lawyer_reviewed" and current["statement_type"] == "document_says"
            and current["source_check"] != "passed"):
        raise FactError(409, "The quote was not found on the cited page; edit the fact or its source first.")
    if not await repo.review_fact(session, current["id"], status, user_id, note):
        raise FactError(409, "The fact was changed by someone else; reload and try again.")


def fact_set_hash(facts: list[dict]) -> str:
    return hashlib.sha256(",".join(sorted(str(f["id"]) for f in facts)).encode()).hexdigest()
