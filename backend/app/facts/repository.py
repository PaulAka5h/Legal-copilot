"""SQL for ai_runs, case_facts, and case_fact_sources (app_user, RLS)."""

import json
from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

FACT_FIELDS = """
    f.id, f.lineage_id, f.version, f.supersedes_id, f.is_current, f.category, f.statement,
    f.attributes, f.statement_type, f.origin, f.fact_status, f.source_check, f.review_status,
    f.review_note, f.reviewed_by, f.reviewed_at, f.extraction_run_id, f.created_by, f.created_at,
    (f.is_current AND f.review_status <> 'lawyer_rejected'
     AND (f.statement_type = 'lawyer_entered' OR f.review_status = 'lawyer_reviewed')) AS usable_in_analysis
"""


async def create_run(session: AsyncSession, values: dict[str, Any]) -> UUID:
    return await session.scalar(
        text(
            """
            INSERT INTO public.ai_runs
              (case_id, organization_id, requested_by, run_type, agent, provider, model, prompt_version,
               input_hash, settings, status, started_at)
            VALUES
              (:case_id, :organization_id, :requested_by, 'fact_extraction', 'fact_extractor', :provider,
               :model, :prompt_version, :input_hash, CAST(:settings AS jsonb), 'running', now())
            RETURNING id
            """
        ),
        {**values, "settings": json.dumps(values["settings"])},
    )


async def finish_run(session: AsyncSession, run_id: UUID, status: str, attempts: int, error: str | None) -> None:
    await session.execute(
        text(
            "UPDATE public.ai_runs SET status = :s, attempts = :a, error = :e, finished_at = now() "
            "WHERE id = :id"
        ),
        {"s": status, "a": attempts, "e": error, "id": run_id},
    )


async def insert_fact(session: AsyncSession, values: dict[str, Any]) -> UUID:
    return await session.scalar(
        text(
            """
            INSERT INTO public.case_facts
              (case_id, organization_id, lineage_id, version, supersedes_id, is_current, category, statement,
               attributes, statement_type, fact_status, origin, source_check, extraction_run_id, created_by)
            VALUES
              (:case_id, :organization_id, :lineage_id, :version, :supersedes_id, true, :category, :statement,
               CAST(:attributes AS jsonb), :statement_type, :fact_status, :origin, :source_check,
               :extraction_run_id, :created_by)
            RETURNING id
            """
        ),
        {**values, "attributes": json.dumps(values["attributes"], ensure_ascii=False)},
    )


async def insert_source(session: AsyncSession, values: dict[str, Any]) -> None:
    await session.execute(
        text(
            """
            INSERT INTO public.case_fact_sources
              (fact_id, case_id, organization_id, source_kind, document_id, page_id, page_no, quote, quote_check,
               quote_start, quote_end, quote_match)
            VALUES
              (:fact_id, :case_id, :organization_id, :source_kind, :document_id, :page_id, :page_no, :quote,
               :quote_check, :quote_start, :quote_end, :quote_match)
            """
        ),
        values,
    )


async def retire_fact(session: AsyncSession, fact_id: UUID) -> bool:
    result = await session.execute(
        text("UPDATE public.case_facts SET is_current = false WHERE id = :id AND is_current"), {"id": fact_id}
    )
    return result.rowcount == 1


async def review_fact(session: AsyncSession, fact_id: UUID, status: str, reviewer: UUID, note: str | None) -> bool:
    result = await session.execute(
        text(
            """
            UPDATE public.case_facts
            SET review_status = :s, reviewed_by = :r, reviewed_at = now(), review_note = :n
            WHERE id = :id AND is_current AND review_status = 'draft'
            """
        ),
        {"s": status, "r": reviewer, "n": note, "id": fact_id},
    )
    return result.rowcount == 1


async def _with_sources(session: AsyncSession, rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    sources = await session.execute(
        text(
            """
            SELECT id, fact_id, source_kind, document_id, page_id, page_no, quote, quote_check,
                   quote_start, quote_end, quote_match
            FROM public.case_fact_sources WHERE fact_id = ANY(CAST(:ids AS uuid[])) ORDER BY created_at, id
            """
        ),
        {"ids": [r["id"] for r in rows]},
    )
    by_fact: dict[UUID, list[dict]] = defaultdict(list)
    for source in sources.mappings():
        by_fact[source["fact_id"]].append(dict(source))
    return [{**r, "sources": by_fact[r["id"]]} for r in rows]


async def get_fact(session: AsyncSession, case_id: UUID, fact_id: UUID) -> dict | None:
    row = (
        await session.execute(
            text(f"SELECT {FACT_FIELDS} FROM public.case_facts f WHERE f.id = :id AND f.case_id = :c"),
            {"id": fact_id, "c": case_id},
        )
    ).mappings().first()
    return (await _with_sources(session, [dict(row)]))[0] if row else None


async def list_facts(
    session: AsyncSession, case_id: UUID, review_status: str | None, statement_type: str | None,
    include_rejected: bool,
) -> list[dict]:
    rows = await session.execute(
        text(
            f"""
            SELECT {FACT_FIELDS} FROM public.case_facts f
            WHERE f.case_id = :c AND f.is_current
              AND (CAST(:rs AS text) IS NULL OR f.review_status = :rs)
              AND (CAST(:st AS text) IS NULL OR f.statement_type = :st)
              AND (:inc OR f.review_status <> 'lawyer_rejected')
            ORDER BY f.created_at, f.id
            """
        ),
        {"c": case_id, "rs": review_status, "st": statement_type, "inc": include_rejected},
    )
    return await _with_sources(session, [dict(r) for r in rows.mappings()])


async def facts_for_run(session: AsyncSession, run_id: UUID) -> list[dict]:
    rows = await session.execute(
        text(f"SELECT {FACT_FIELDS} FROM public.case_facts f WHERE f.extraction_run_id = :r ORDER BY f.created_at, f.id"),
        {"r": run_id},
    )
    return await _with_sources(session, [dict(r) for r in rows.mappings()])


async def lineage_history(session: AsyncSession, case_id: UUID, fact_id: UUID) -> list[dict]:
    rows = await session.execute(
        text(
            f"""
            SELECT {FACT_FIELDS} FROM public.case_facts f
            WHERE f.case_id = :c
              AND f.lineage_id = (SELECT lineage_id FROM public.case_facts WHERE id = :id AND case_id = :c)
            ORDER BY f.version DESC
            """
        ),
        {"c": case_id, "id": fact_id},
    )
    return await _with_sources(session, [dict(r) for r in rows.mappings()])


async def facts_for_analysis(session: AsyncSession, case_id: UUID) -> list[dict]:
    rows = await session.execute(
        text(
            f"SELECT {FACT_FIELDS} FROM public.case_facts_for_analysis f WHERE f.case_id = :c "
            "ORDER BY f.created_at, f.id"
        ),
        {"c": case_id},
    )
    return await _with_sources(session, [dict(r) for r in rows.mappings()])
