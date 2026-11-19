"""Hybrid legal search over approved legal_chunks.

1. Query is NFC-normalized; the dense side embeds "query: " + query (e5-large).
2. Eligible versions: review_status 'approved', is_current, source language filter,
   and not out of force on the incident date at source/version level.
3. Dense: HNSW cosine (pgvector, iterative scan) within those versions.
   Sparse: 'simple' full-text, query lexemes OR-ed with English stopwords removed,
   ranked by length-normalized ts_rank_cd.
4. Reciprocal Rank Fusion, k = 60, over both ranked lists.
5. Section-level in-force check on the incident date; `unknown` status is
   included but flagged; repealed text is excluded unless its end date is known
   and on/after the incident date.
6. bn/en and sub-chunks of one section are merged by canonical_section_id; the
   other language versions are returned as alternates (cite both).
7. Reranker (mock by default) orders the merged candidates; top k returned.
Query text is never logged.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.embed.worker import vector_literal
from app.rag.search.providers import QueryEmbedder, Reranker
from app.rag.text import nfc

RRF_K = 60
DENSE_K = 50
SPARSE_K = 50
FUSED_K = 60
RERANK_POOL = 30
EF_SEARCH = 100

INCLUDED_STATUSES = {"in_force", "unknown", "amended", "partly_repealed"}

_ELIGIBLE_VERSIONS = text(
    """
    SELECT v.id
    FROM public.legal_source_versions v
    JOIN public.legal_sources s ON s.id = v.legal_source_id
    WHERE v.review_status = 'approved' AND v.is_current
      AND (CAST(:language AS text) IS NULL OR s.language = :language)
      AND (CAST(:incident_date AS date) IS NULL OR v.effective_from IS NULL
           OR v.effective_from <= :incident_date)
      AND (CAST(:incident_date AS date) IS NULL OR v.effective_to IS NULL
           OR v.effective_to >= :incident_date)
      AND (s.current_status <> 'repealed'
           OR (CAST(:incident_date AS date) IS NOT NULL AND v.effective_to IS NOT NULL
               AND v.effective_to >= :incident_date))
    """
)

_HYBRID = text(
    f"""
    WITH q AS (
      SELECT CAST(:qvec AS vector) AS v,
             (SELECT to_tsquery('simple', string_agg(quote_literal(l), ' | '))
              FROM unnest(tsvector_to_array(to_tsvector('simple', :qtext))) AS l
              -- 'simple' keeps stopwords; drop English ones (english_stem returns an empty array for them)
              WHERE cardinality(ts_lexize('english_stem', l)) > 0) AS ts
    ),
    dense AS (
      SELECT d.id, row_number() OVER (ORDER BY d.dist) AS r
      FROM (
        SELECT c.id, c.embedding <=> q.v AS dist
        FROM public.legal_chunks c, q
        WHERE c.is_active AND c.embedding IS NOT NULL
          AND c.legal_source_version_id = ANY(CAST(:versions AS uuid[]))
        ORDER BY c.embedding <=> q.v
        LIMIT {DENSE_K}
      ) d
    ),
    sparse AS (
      SELECT s.id, row_number() OVER (ORDER BY s.rank DESC, s.id) AS r
      FROM (
        SELECT c.id, ts_rank_cd(c.tsv, q.ts, 1) AS rank  -- 1: divide by 1 + log(length)
        FROM public.legal_chunks c, q
        WHERE q.ts IS NOT NULL AND c.tsv @@ q.ts AND c.is_active
          AND c.legal_source_version_id = ANY(CAST(:versions AS uuid[]))
        ORDER BY rank DESC, c.id
        LIMIT {SPARSE_K}
      ) s
    ),
    fused AS (
      SELECT id, sum(1.0 / ({RRF_K} + r)) AS score, min(dense_r) AS dense_rank, min(sparse_r) AS sparse_rank
      FROM (
        SELECT id, r, r AS dense_r, NULL::bigint AS sparse_r FROM dense
        UNION ALL
        SELECT id, r, NULL::bigint, r FROM sparse
      ) both_lists
      GROUP BY id
      ORDER BY score DESC, id
      LIMIT {FUSED_K}
    )
    SELECT f.id AS chunk_id, f.score, f.dense_rank, f.sparse_rank,
           c.text, c.chunk_index, c.provision_label,
           sec.id AS section_id, sec.canonical_section_id, sec.section_number, sec.heading,
           sec.language, sec.status AS section_status, sec.source_url,
           coalesce(sec.effective_from, v.effective_from) AS effective_from,
           coalesce(sec.effective_to, v.effective_to) AS effective_to,
           v.id AS version_id, v.version_no, s.title AS act_title, s.external_id AS act_id,
           s.current_status AS source_status
    FROM fused f
    JOIN public.legal_chunks c ON c.id = f.id
    JOIN public.legal_sections sec ON sec.id = c.legal_section_id
    JOIN public.legal_source_versions v ON v.id = c.legal_source_version_id
    JOIN public.legal_sources s ON s.id = v.legal_source_id
    ORDER BY f.score DESC, f.id
    """
)


@dataclass
class Alternate:
    chunk_id: UUID
    language: str
    section_number: str | None
    source_url: str


@dataclass
class SearchHit:
    chunk_id: UUID
    section_id: UUID
    canonical_section_id: UUID
    version_id: UUID
    version_no: int
    act_id: str
    act_title: str
    section_number: str | None
    heading: str | None
    language: str
    source_url: str
    text: str
    fused_score: float
    dense_rank: int | None
    sparse_rank: int | None
    rerank_score: float | None
    in_force_status: str
    warnings: list[str]
    alternates: list[Alternate] = field(default_factory=list)


@dataclass
class SearchResult:
    hits: list[SearchHit]
    warnings: list[str]
    reranker: str
    embedding_model: str
    eligible_versions: int


def in_force(
    section_status: str,
    source_status: str,
    effective_from: date | None,
    effective_to: date | None,
    incident_date: date | None,
) -> tuple[bool, str, list[str]]:
    """Decide inclusion for one section on the incident date: (include, status, warnings)."""
    status = section_status if section_status != "unknown" else source_status
    if incident_date is not None:
        if effective_from is not None and incident_date < effective_from:
            return False, status, []
        if effective_to is not None and incident_date > effective_to:
            return False, status, []
    if status == "repealed":
        known_in_force = incident_date is not None and effective_to is not None and incident_date <= effective_to
        return (True, status, ["repealed_after_incident_date"]) if known_in_force else (False, status, [])
    if status not in INCLUDED_STATUSES:
        return False, status, []
    warnings = []
    if status == "unknown":
        warnings.append("amendment_status_unknown")
    elif status != "in_force":
        warnings.append(f"status_{status}")
    if effective_from is None and effective_to is None:
        warnings.append("effective_dates_unknown")
    return True, status, warnings


async def hybrid_search(
    session: AsyncSession,
    *,
    query: str,
    embedder: QueryEmbedder,
    reranker: Reranker,
    language: str | None = None,
    incident_date: date | None = None,
    k: int = 10,
) -> SearchResult:
    query = nfc(query).strip()
    response_warnings = [] if incident_date else ["no_incident_date: in-force status not checked against a date"]

    await session.execute(text("SELECT set_config('hnsw.ef_search', :v, true)"), {"v": str(EF_SEARCH)})
    await session.execute(text("SELECT set_config('hnsw.iterative_scan', 'relaxed_order', true)"))
    params = {"language": language, "incident_date": incident_date}
    versions = [r[0] for r in await session.execute(_ELIGIBLE_VERSIONS, params)]
    if not versions:
        return SearchResult([], [*response_warnings, "no_approved_sources"], reranker.name,
                            embedder.model_name, 0)

    qvec = vector_literal(embedder.embed_query(query))
    rows = (await session.execute(_HYBRID, {"qvec": qvec, "qtext": query, "versions": versions})).mappings().all()

    merged: dict[UUID, SearchHit] = {}
    for row in rows:
        include, status, warnings = in_force(
            row["section_status"], row["source_status"], row["effective_from"], row["effective_to"], incident_date
        )
        if not include:
            continue
        canonical = row["canonical_section_id"]
        best = merged.get(canonical)
        if best is None:
            merged[canonical] = _hit(row, status, warnings)
        elif row["language"] != best.language and all(a.language != row["language"] for a in best.alternates):
            best.alternates.append(
                Alternate(row["chunk_id"], row["language"], row["section_number"], row["source_url"])
            )

    pool = list(merged.values())[:RERANK_POOL]
    scores = reranker.scores(query, [h.text for h in pool], [h.fused_score for h in pool])
    for hit, score in zip(pool, scores):
        hit.rerank_score = None if reranker.name == "mock" else score
    ranked = [h for _, h in sorted(zip(scores, pool), key=lambda pair: -pair[0])]
    return SearchResult(ranked[:k], response_warnings, reranker.name, embedder.model_name, len(versions))


def _hit(row: Any, status: str, warnings: list[str]) -> SearchHit:
    return SearchHit(
        chunk_id=row["chunk_id"],
        section_id=row["section_id"],
        canonical_section_id=row["canonical_section_id"],
        version_id=row["version_id"],
        version_no=row["version_no"],
        act_id=row["act_id"],
        act_title=row["act_title"],
        section_number=row["section_number"],
        heading=row["heading"],
        language=row["language"],
        source_url=row["source_url"],
        text=row["text"],
        fused_score=float(row["score"]),
        dense_rank=row["dense_rank"],
        sparse_rank=row["sparse_rank"],
        rerank_score=None,
        in_force_status=status,
        warnings=warnings,
    )
