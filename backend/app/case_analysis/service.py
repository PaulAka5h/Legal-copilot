"""Case analysis pipeline (Step D).

confirmed facts (case_facts_for_analysis) -> per-fact queries -> hybrid
retrieval with the incident-date filter -> abstain check -> element-by-element
findings (model or mock) -> deterministic verification -> new immutable version.
"""

import asyncio
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.llm import StructuredLLM
from app.ai.structured import generate_structured
from app.auth.repository import write_audit_event
from app.case_analysis.analyzer import (
    MAX_PROVISIONS,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    FactInput,
    ProvisionInput,
    build_user_prompt,
    mock_analysis,
)
from app.case_analysis.schemas import AnalysisDraft
from app.database import user_transaction
from app.facts import repository as facts_repo
from app.facts.service import fact_set_hash
from app.rag.search.providers import QueryEmbedder, Reranker
from app.rag.search.retrieval import KEYWORD_ONLY_WARNING, hybrid_search
from app.rag.quote_locator import segment_hint
from app.rag.text import BANGLA_STOPWORDS, normalize_for_match
from app.rag.verifier import (
    NO_PRECEDENT_NOTE,
    judgments_available,
    load_chunks,
    locate_in_chunk,
    scrub,
    verify_citation,
)

QUERIES_PER_FACT = 2
HITS_PER_QUERY = 5


class AnalysisError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code, self.detail = status_code, detail


@dataclass
class Thresholds:
    min_similarity: float  # mock reranker: cosine similarity of the best hit
    min_rerank_score: float  # cross-encoder score when a real reranker runs


# Keyword-only fallback gate (heuristic, not calibrated): a full-text hit counts only if
# it shares this many distinct content words with the fact. Generic overlap ("law",
# "section", the SAMPLE label) must not turn an unrelated fact into a legal finding.
KEYWORD_MIN_SHARED_WORDS = 3
_TOKEN = re.compile(r"[^\s.,;:!?()\[\]{}\"'“”‘’।/-]+")
_EN_STOP = frozenset(
    "the and that this with from have been were which their there would shall under into upon such "
    "other about after before being when where what also only than then them they will your said "
    "sample_data_not_real_law sample data real section act law".split()
)


def _content_words(text_value: str) -> set[str]:
    words = {w.lower() for w in _TOKEN.findall(normalize_for_match(text_value))}
    return {w for w in words if len(w) >= 4 and w not in _EN_STOP and w not in BANGLA_STOPWORDS}


def keyword_support(statement: str, chunk_text: str) -> int:
    """Distinct content words of the fact that also occur in the provision text."""
    return len(_content_words(statement) & _content_words(chunk_text))


def fact_queries(fact: FactInput) -> list[str]:
    """Multi-query per fact: the statement, plus its content words (names and filler removed)."""
    statement = normalize_for_match(fact.statement)
    words = [w for w in statement.split() if len(w) > 3 and not w[:1].isupper()]
    queries = [statement]
    if len(words) >= 3:
        queries.append(" ".join(words))
    return queries[:QUERIES_PER_FACT]


async def _retrieve(session, facts, embedder, reranker, incident_date, language,
                    keyword_fallback: bool = True) -> tuple[list[dict], list[str]]:
    by_chunk: dict[UUID, dict[str, Any]] = {}
    warnings: set[str] = set()
    for fact in facts:
        for query in fact_queries(fact):
            result = await hybrid_search(session, query=query, embedder=embedder, reranker=reranker,
                                         language=language, incident_date=incident_date, k=HITS_PER_QUERY,
                                         keyword_fallback=keyword_fallback)
            warnings.update(result.warnings)
            for hit in result.hits:
                score = hit.rerank_score if hit.rerank_score is not None else (hit.dense_similarity or 0.0)
                entry = by_chunk.setdefault(hit.chunk_id, {"hit": hit, "score": score, "facts": set()})
                entry["score"] = max(entry["score"], score)
                entry["facts"].add(fact.id)
    ranked = sorted(by_chunk.values(), key=lambda e: -e["score"])
    return ranked, sorted(warnings)


def _verify(draft: AnalysisDraft, chunks: dict, fact_ids: set[UUID], incident_date: date | None,
            retrieved_ids: set[UUID], precedents: bool) -> tuple[list[dict], dict]:
    findings, summary = [], {"findings_in": len(draft.findings), "stripped_not_retrieved": 0,
                             "citations_verified": 0, "citations_failed": 0, "elements_unverified": 0,
                             "fact_links_removed": 0, "quotes_repaired": 0, "quotes_dropped": 0,
                             "scrub_flags": []}
    for finding in draft.findings:
        if finding.chunk_id not in retrieved_ids:
            summary["stripped_not_retrieved"] += 1  # only retrieved text may be cited
            continue
        chunk_text = chunks.get(finding.chunk_id, {}).get("text", "")
        ref = finding.quote_ref if finding.quote_ref.chunk_id == finding.chunk_id else None
        citation = verify_citation(finding.chunk_id, finding.quote, chunks, incident_date,
                                   segment_hint(chunk_text, ref.sentences) if ref and chunk_text else None)
        summary["citations_verified" if citation.verified else "citations_failed"] += 1
        summary["quotes_repaired"] += any(w.startswith("quote_repaired") for w in citation.warnings)
        summary["quotes_dropped"] += citation.quote is None
        dropped_elements = 0
        elements = []
        for element in finding.elements:
            fact_id, status = element.matched_fact_id, element.status
            if fact_id is not None and fact_id not in fact_ids:
                fact_id, status = None, "missing"
                summary["fact_links_removed"] += 1
            if status == "met" and fact_id is None:
                status = "missing"
            # Only the exact span from the stored provision is kept; an unlocatable quote is dropped.
            located = locate_in_chunk(element.element_quote, chunk_text,
                                      segment_hint(chunk_text, element.element_quote_sentences)) if chunk_text else None
            element_ok = located is not None
            summary["elements_unverified"] += not element_ok
            summary["quotes_repaired"] += bool(located and located.method != "exact")
            summary["quotes_dropped"] += not element_ok
            dropped_elements += not element_ok
            elements.append({"element": scrub(element.element, summary["scrub_flags"], precedents),
                             "element_quote": located.text if located else None, "matched_fact_id": fact_id,
                             "status": status, "verified": element_ok})
        reasons = [scrub(r, summary["scrub_flags"], precedents) for r in finding.reasons]
        verified = citation.verified and all(e["verified"] for e in elements)
        if not citation.verified:
            reasons.append("Citation failed verification: " + ", ".join(citation.failures))
        if dropped_elements:
            reasons.append(f"{dropped_elements} element quote(s) not found in the provision text were removed; "
                           "this finding stays unverified.")
        findings.append({
            "offence_or_claim": scrub(finding.offence_or_claim, summary["scrub_flags"], precedents),
            "section_citation": asdict(citation), "elements": elements,
            "strength": finding.strength if verified else "insufficient",
            "reasons": reasons, "statement_type": "ai_inference",
            "verification": "verified" if verified else "unverified",
        })
    summary["scrub_flags"] = sorted(set(summary["scrub_flags"]))
    return findings, summary


async def run_analysis(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    case_id: UUID,
    user_id: UUID,
    incident_date: date | None,
    language: str | None,
    embedder: QueryEmbedder,
    reranker: Reranker,
    llm: StructuredLLM | None,
    allow_mock: bool,
    thresholds: Thresholds,
    trigger: str = "manual",
    trigger_ref_id: UUID | None = None,
) -> UUID:
    async with user_transaction(session_factory, user_id) as session:
        organization_id = await session.scalar(text("SELECT organization_id FROM public.cases WHERE id = :c"),
                                               {"c": case_id})
        rows = await facts_repo.facts_for_analysis(session, case_id)
        previous = (await session.execute(
            text("SELECT id, version FROM public.case_analyses WHERE case_id = :c ORDER BY version DESC LIMIT 1"),
            {"c": case_id})).first()
    if not rows:
        raise AnalysisError(409, "No confirmed facts: confirm or enter facts before running an analysis.")
    facts = [FactInput(r["id"], r["statement"], r["category"], r["statement_type"], r["fact_status"]) for r in rows]
    fact_hash = fact_set_hash(rows)

    async with user_transaction(session_factory, user_id) as session:
        ranked, retrieval_warnings = await _retrieve(session, facts, embedder, reranker, incident_date, language)
        precedents = await judgments_available(session)
    using_reranker = reranker.name != "mock"
    threshold = thresholds.min_rerank_score if using_reranker else thresholds.min_similarity
    # Keyword-only fallback (embedder unavailable): those hits have no cosine score, so a
    # full-text match counts as retrieved; the warning travels with the analysis and the
    # UI labels it.
    keyword_only = KEYWORD_ONLY_WARNING in retrieval_warnings
    statements = {f.id: f.statement for f in facts}

    def keyword_relevant(entry: dict) -> bool:
        hit = entry["hit"]
        return (keyword_only and hit.dense_similarity is None and hit.sparse_rank is not None
                and max(keyword_support(statements[f], hit.text) for f in entry["facts"]) >= KEYWORD_MIN_SHARED_WORDS)

    relevant = [e for e in ranked if e["score"] >= threshold or keyword_relevant(e)]
    provisions = [ProvisionInput(e["hit"].chunk_id, e["hit"].act_title, e["hit"].section_number, e["hit"].text)
                  for e in relevant[:MAX_PROVISIONS]]
    retrieved_sources = [{
        "chunk_id": str(e["hit"].chunk_id), "act_title": e["hit"].act_title, "section_number": e["hit"].section_number,
        "language": e["hit"].language, "source_url": e["hit"].source_url, "best_score": round(e["score"], 4),
        "from_fact_ids": sorted(str(f) for f in e["facts"]),
    } for e in relevant[:MAX_PROVISIONS]]

    warnings = list(retrieval_warnings)
    abstain_reason = None
    findings: list[dict] = []
    missing: list[str] = []
    summary: dict = {}
    origin, provider, model, attempts = ("ai_mock", "mock", None, 0) if llm is None else ("ai", llm.provider, llm.model, 0)

    if not provisions:
        best = round(ranked[0]["score"], 4) if ranked else None
        abstain_reason = (f"insufficient_information: no retrieved provision reached the relevance threshold "
                          f"({'rerank' if using_reranker else 'similarity'} >= {threshold}; best {best}).")
        uncovered = [f.statement for f in facts]
        missing = [f"No applicable provision found in approved statutes for: {s[:200]}" for s in uncovered][:10]
    else:
        generated = await generate_structured(
            llm, AnalysisDraft, SYSTEM_PROMPT, build_user_prompt(facts, provisions),
            lambda: mock_analysis(facts, provisions), allow_mock,
        )
        origin, provider, model, attempts = generated.origin, generated.provider, generated.model, generated.attempts
        warnings.extend(generated.warnings)
        async with user_transaction(session_factory, user_id) as session:
            chunks = await load_chunks(session, [p.chunk_id for p in provisions])
        # CPU-bound (quote location); off the event loop so other requests keep moving.
        findings, summary = await asyncio.to_thread(
            _verify, generated.value, chunks, {f.id for f in facts}, incident_date,
            {p.chunk_id for p in provisions}, precedents)
        missing = [scrub(m, summary["scrub_flags"], precedents) for m in generated.value.missing_information]
        # Abstain only when no finding has a verified citation. Findings whose element
        # quotes failed are kept, labelled unverified and capped at insufficient.
        if not any(f["section_citation"]["verified"] for f in findings):
            abstain_reason = "insufficient_information: no finding has a verified citation."

    status = "insufficient_information" if abstain_reason else "succeeded"
    result = {
        "findings": findings, "missing_information": missing, "retrieved_sources": retrieved_sources,
        "abstain_reason": abstain_reason, "precedent_note": "" if precedents else NO_PRECEDENT_NOTE,
        "verification_summary": summary, "warnings": sorted(set(warnings)),
        "queries": sum(len(fact_queries(f)) for f in facts), "threshold": threshold,
    }
    input_hash = hashlib.sha256(json.dumps([PROMPT_VERSION, fact_hash, [s["chunk_id"] for s in retrieved_sources],
                                            str(incident_date)]).encode()).digest()
    async with user_transaction(session_factory, user_id) as session:
        run_id = await session.scalar(text(
            """
            INSERT INTO public.ai_runs (case_id, organization_id, requested_by, run_type, agent, provider, model,
              prompt_version, input_hash, settings, status, attempts, started_at, finished_at)
            VALUES (:c, :o, :u, 'case_analysis', 'case_analyzer', :p, :m, :pv, :h, CAST(:s AS jsonb), :st, :a, now(), now())
            RETURNING id
            """), {"c": case_id, "o": organization_id, "u": user_id, "p": provider, "m": model, "pv": PROMPT_VERSION,
                   "h": input_hash, "s": json.dumps({"incident_date": str(incident_date), "language": language,
                                                     "facts": len(facts), "origin": origin}),
                   "st": "succeeded", "a": attempts})
        analysis_id = await session.scalar(text(
            """
            INSERT INTO public.case_analyses (case_id, organization_id, version, supersedes_id, trigger, trigger_ref_id,
              status, fact_set_hash, fact_ids, incident_date, language, provider, origin, result, ai_run_id, created_by)
            VALUES (:c, :o, :v, :sup, :t, :tr, :st, :fh, CAST(:fids AS uuid[]), :d, :l, :p, :origin,
                    CAST(:r AS jsonb), :run, :u)
            RETURNING id
            """), {"c": case_id, "o": organization_id, "v": (previous[1] + 1) if previous else 1,
                   "sup": previous[0] if previous else None, "t": trigger, "tr": trigger_ref_id, "st": status,
                   "fh": fact_hash, "fids": [f.id for f in facts], "d": incident_date, "l": language,
                   "p": provider, "origin": origin, "r": json.dumps(result, default=str, ensure_ascii=False),
                   "run": run_id, "u": user_id})
        await write_audit_event(
            session, action="analysis.created", actor_user_id=user_id, actor_role="lawyer",
            object_type="case_analysis", object_id=analysis_id, case_id=case_id, ip_address=None, user_agent=None,
            request_id=None, details={"status": status, "findings": len(findings), "origin": origin,
                                      "version": (previous[1] + 1) if previous else 1},
        )
    return analysis_id


ANALYSIS_FIELDS = """id, case_id, version, supersedes_id, trigger, status, fact_set_hash, fact_ids, incident_date,
    provider, origin, result, created_by, created_at"""


def to_out(row: dict) -> dict:
    result = row["result"]
    return {**{k: row[k] for k in ("id", "case_id", "version", "supersedes_id", "trigger", "status", "fact_set_hash",
                                   "fact_ids", "incident_date", "provider", "origin", "created_by", "created_at")},
            "findings": result["findings"], "missing_information": result["missing_information"],
            "retrieved_sources": result["retrieved_sources"], "abstain_reason": result["abstain_reason"],
            "precedent_note": result["precedent_note"], "verification_summary": result["verification_summary"],
            "warnings": result["warnings"]}


async def get_analysis(session: AsyncSession, case_id: UUID, version: int | None = None) -> dict | None:
    query = f"SELECT {ANALYSIS_FIELDS} FROM public.case_analyses WHERE case_id = :c" + (
        " AND version = :v" if version is not None else "") + " ORDER BY version DESC LIMIT 1"
    row = (await session.execute(text(query), {"c": case_id, "v": version})).mappings().first()
    return dict(row) if row else None


async def get_analysis_by_id(session: AsyncSession, case_id: UUID, analysis_id: UUID) -> dict | None:
    row = (await session.execute(text(f"SELECT {ANALYSIS_FIELDS} FROM public.case_analyses WHERE case_id = :c AND id = :i"),
                                 {"c": case_id, "i": analysis_id})).mappings().first()
    return dict(row) if row else None


async def list_versions(session: AsyncSession, case_id: UUID) -> list[dict]:
    rows = await session.execute(text(
        "SELECT id, version, status, fact_set_hash, provider, origin, jsonb_array_length(result->'findings') AS findings, "
        "created_at FROM public.case_analyses WHERE case_id = :c ORDER BY version DESC"), {"c": case_id})
    return [dict(r) for r in rows.mappings()]
