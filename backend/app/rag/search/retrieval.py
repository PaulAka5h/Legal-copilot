"""Hybrid legal search over approved legal_chunks.

1. Query is NFC-normalized; the dense side embeds it with EMBEDDING_PROVIDER's model.
2. Eligible versions: review_status 'approved', is_current, source language filter,
   and not out of force on the incident date at source/version level.
3. Dense: HNSW cosine (pgvector, iterative scan, the index for the query's dimension)
   within those versions.
   Sparse: 'simple' full-text, query lexemes OR-ed with English and Bangla
   (app.rag.text.BANGLA_STOPWORDS) stopwords removed,
   ranked by length-normalized ts_rank_cd.
4. Weighted Reciprocal Rank Fusion over both ranked lists (FusionConfig: k = 30, dense
   weight 1.5, sparse 1.0).
5. Section-level in-force check on the incident date; `unknown` status is
   included but flagged; repealed text is excluded unless its end date is known
   and on/after the incident date.
6. bn/en and sub-chunks of one section are merged by canonical_section_id; the
   other language versions are returned as alternates (cite both).
7. Reranker (mock by default) orders the merged candidates; top k returned.
Before embedding the query, the (embedding_model, embedding_version) of the
eligible embedded chunks must equal the query embedder's: a knowledge base embedded
with another model (or half re-embedded) raises EmbeddingModelMismatch (503) instead
of returning meaningless neighbours. The dense side also filters on that pair.
If the embedder is temporarily unavailable (EmbeddingUnavailable: quota 429, outage)
search falls back to the full-text side only, flagged with KEYWORD_ONLY_WARNING and
retrieval_mode "keyword_only" so the UI can label it. A model mismatch never falls
back: it is a configuration error and stays a 503.
rewritten_search runs the query plus its LLM rewrites (Bangla, English, keywords;
app.rag.search.query_rewrite) and fuses those result lists by canonical section.
Query text is never logged.
"""

import asyncio
import logging
from dataclasses import dataclass, field, replace
from functools import lru_cache
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.embed.worker import vector_literal
from app.rag.search.errors import EmbeddingModelMismatch, EmbeddingUnavailable
from app.rag.search.providers import QueryEmbedder, Reranker
from app.rag.search.query_rewrite import QueryRewriter, Rewrite
from app.rag.text import BANGLA_STOPWORDS, nfc

# Tuned 2026-11-22 for e5-small on the 19-Act set (33 queries; DOCS/eval_results.md):
# k=30 with the dense list weighted 1.5 beat k=60 / 1:1 (Recall@10 0.909 vs 0.879).
RRF_K = 30
DENSE_WEIGHT = 1.5
DENSE_K = 50
SPARSE_K = 50
FUSED_K = 60
RERANK_POOL = 30
EF_SEARCH = 100

BN_STOPWORDS = sorted(BANGLA_STOPWORDS)
KEYWORD_ONLY_WARNING = (
    "keyword_only_fallback: semantic search is unavailable (embedding quota or outage); "
    "results matched by keywords only"
)
logger = logging.getLogger(__name__)
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

_STORED_MODELS = text(
    """
    SELECT DISTINCT embedding_model, embedding_version
    FROM public.legal_chunks
    WHERE is_active AND embedding IS NOT NULL
      AND legal_source_version_id = ANY(CAST(:versions AS uuid[]))
    ORDER BY 1, 2
    """
)

# Full-text query: 'simple' lexemes OR-ed, minus English stopwords (english_stem
# returns an empty array for them) and the curated Bangla stopwords.
TSQUERY_SQL = """
    SELECT to_tsquery('simple', string_agg(quote_literal(l), ' | '))
    FROM unnest(tsvector_to_array(to_tsvector('simple', :qtext))) AS l
    WHERE cardinality(ts_lexize('english_stem', l)) > 0
      AND NOT (l = ANY(CAST(:bn_stopwords AS text[])))
"""

# {dim} is the query vector's size (an int from code). The cast expression and the
# vector_dims predicate match the per-dimension partial HNSW index (migration 0021), and the
# query vector must be a bound parameter, not a joined column: pgvector can only order by
# the index against a constant/parameter.
_DENSE = f"""
      SELECT d.id, d.dist, row_number() OVER (ORDER BY d.dist) AS r
      FROM (
        SELECT c.id, CAST(c.embedding AS vector({{dim}})) <=> CAST(:qvec AS vector({{dim}})) AS dist
        FROM public.legal_chunks c
        WHERE c.is_active AND c.embedding IS NOT NULL AND vector_dims(c.embedding) = {{dim}}
          AND c.embedding_model = :model AND c.embedding_version = :model_version
          AND c.legal_source_version_id = ANY(CAST(:versions AS uuid[]))
        ORDER BY CAST(c.embedding AS vector({{dim}})) <=> CAST(:qvec AS vector({{dim}}))
        LIMIT {DENSE_K}
      ) d
"""
_NO_DENSE = "SELECT NULL::uuid AS id, NULL::float8 AS dist, NULL::bigint AS r WHERE false"

_SPARSE = f"""
      SELECT s.id, row_number() OVER (ORDER BY s.rank DESC, s.id) AS r
      FROM (
        SELECT c.id, ts_rank_cd(c.tsv, q.ts, 1) AS rank  -- 1: divide by 1 + log(length)
        FROM public.legal_chunks c, q
        WHERE q.ts IS NOT NULL AND c.tsv @@ q.ts AND c.is_active
          AND c.legal_source_version_id = ANY(CAST(:versions AS uuid[]))
        ORDER BY rank DESC, c.id
        LIMIT {SPARSE_K}
      ) s
"""
_NONE = "SELECT NULL::uuid AS id, NULL::bigint AS r WHERE false"

_SELECT_FUSED = """
    SELECT f.id AS chunk_id, f.score, f.dense_rank, f.sparse_rank, f.dense_distance,
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


@dataclass(frozen=True)
class FusionConfig:
    """Weighted Reciprocal Rank Fusion: score = sum(weight / (rrf_k + rank)) over the lists.

    A weight of 0 leaves that list out of the query entirely.
    """

    rrf_k: int = RRF_K
    dense: float = DENSE_WEIGHT
    sparse: float = 1.0


DEFAULT_FUSION = FusionConfig()


@lru_cache(maxsize=32)
def _hybrid_sql(dense: bool, fusion: FusionConfig, dim: int = 0):
    lists = {
        "dense": (_DENSE.format(dim=int(dim)) if dense and fusion.dense else _NO_DENSE, fusion.dense),
        "sparse": (_SPARSE if fusion.sparse else _NONE, fusion.sparse),
    }
    ctes = ", ".join(f"{name} AS ({sql})" for name, (sql, _) in lists.items())
    k = int(fusion.rrf_k)
    union = " UNION ALL ".join(
        f"SELECT id, {float(weight)!r} / ({k} + r) AS s, "
        + ("r AS dense_r, dist" if name == "dense" else "NULL::bigint AS dense_r, NULL::float8 AS dist")
        + (", r AS sparse_r" if name == "sparse" else ", NULL::bigint AS sparse_r")
        + f" FROM {name}"
        for name, (_, weight) in lists.items()
    )
    return text(
        f"WITH q AS (SELECT ({TSQUERY_SQL}) AS ts), {ctes}, "
        f"fused AS (SELECT id, sum(s) AS score, min(dense_r) AS dense_rank, min(sparse_r) AS sparse_rank, "
        f"min(dist) AS dense_distance FROM ({union}) all_lists GROUP BY id ORDER BY score DESC, id "
        f"LIMIT {FUSED_K}) {_SELECT_FUSED}"
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
    dense_similarity: float | None
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
    retrieval_mode: str = "hybrid"  # or "keyword_only" (embedder unavailable, labelled)


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


async def check_embedding_model(session: AsyncSession, embedder: QueryEmbedder, versions: list) -> None:
    """Raise EmbeddingModelMismatch unless every eligible embedded chunk matches the embedder."""
    stored = [(r[0], r[1]) for r in await session.execute(_STORED_MODELS, {"versions": versions})]
    if any(pair != (embedder.model_name, embedder.embedding_version) for pair in stored):
        raise EmbeddingModelMismatch(embedder.model_name, embedder.embedding_version, stored)


async def hybrid_search(
    session: AsyncSession,
    *,
    query: str,
    embedder: QueryEmbedder,
    reranker: Reranker,
    language: str | None = None,
    incident_date: date | None = None,
    k: int = 10,
    keyword_fallback: bool = True,
    fusion: FusionConfig = DEFAULT_FUSION,
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

    await check_embedding_model(session, embedder, versions)
    params = {"qtext": query, "versions": versions, "bn_stopwords": BN_STOPWORDS}
    mode, dim = "hybrid", 0
    try:
        # Off the event loop: local inference is CPU-bound, remote providers block on HTTP.
        vector = await asyncio.to_thread(embedder.embed_query, query)
        qvec, dim = vector_literal(vector), len(vector)
    except EmbeddingUnavailable as error:
        if not keyword_fallback:
            raise
        logger.warning("search.keyword_only_fallback",
                       extra={"event": "search.keyword_only_fallback", "exception_type": type(error).__name__})
        mode = "keyword_only"
        response_warnings.append(KEYWORD_ONLY_WARNING)
    if mode == "hybrid":
        params.update(qvec=qvec, model=embedder.model_name, model_version=embedder.embedding_version)
    rows = (await session.execute(_hybrid_sql(mode == "hybrid", fusion, dim), params)).mappings().all()

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
    return SearchResult(ranked[:k], response_warnings, reranker.name, embedder.model_name, len(versions), mode)


REWRITE_FAILED_WARNING = "rewrite_failed: query rewriting was unavailable; searched the query as typed"
VARIANT_POOL = 30  # hits taken from each query variant before fusing


async def rewritten_search(
    session: AsyncSession,
    *,
    query: str,
    rewriter: QueryRewriter,
    embedder: QueryEmbedder,
    reranker: Reranker,
    language: str | None = None,
    incident_date: date | None = None,
    k: int = 10,
    keyword_fallback: bool = True,
    fusion: FusionConfig = DEFAULT_FUSION,
) -> tuple[SearchResult, Rewrite]:
    """hybrid_search for the query and its LLM variants, fused by canonical section (RRF).

    One LLM call per new query (cached); without a usable LLM this is hybrid_search alone.
    """
    rewrite = await asyncio.to_thread(rewriter.rewrite, query)
    results = [
        await hybrid_search(session, query=q, embedder=embedder, reranker=reranker, language=language,
                            incident_date=incident_date, k=VARIANT_POOL, keyword_fallback=keyword_fallback,
                            fusion=fusion)
        for q in rewrite.queries
    ]
    first = results[0]
    if len(results) == 1:
        extra = [REWRITE_FAILED_WARNING] if rewrite.failed else []
        return replace(first, hits=first.hits[:k], warnings=[*first.warnings, *extra]), rewrite
    scores: dict[UUID, float] = {}
    best: dict[UUID, SearchHit] = {}
    for result in results:
        for rank, hit in enumerate(result.hits, start=1):
            scores[hit.canonical_section_id] = scores.get(hit.canonical_section_id, 0.0) + 1.0 / (fusion.rrf_k + rank)
            best.setdefault(hit.canonical_section_id, hit)
    ranked = sorted(best, key=lambda c: (-scores[c], str(c)))
    warnings = list(dict.fromkeys(w for r in results for w in r.warnings))
    mode = "keyword_only" if any(r.retrieval_mode == "keyword_only" for r in results) else "hybrid"
    merged = SearchResult([best[c] for c in ranked[:k]], warnings, first.reranker, first.embedding_model,
                          first.eligible_versions, mode)
    return merged, rewrite


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
        dense_similarity=None if row["dense_distance"] is None else round(1 - float(row["dense_distance"]), 4),
        rerank_score=None,
        in_force_status=status,
        warnings=warnings,
    )
