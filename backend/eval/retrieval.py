"""Retrieval eval and abstain-threshold calibration for the configured EMBEDDING_PROVIDER.

    uv run python -m eval.retrieval --label e5small [--rewrite] [--out eval/results/retrieval_e5small.json]

No LLM calls, nothing written to the database (LEGAL_INGEST_DATABASE_URL, read only).
Query sets (synthetic, SAMPLE_DATA_NOT_REAL_LAW):
- facts:  eval/fact_patterns.jsonl (case-fact statements, en + bn)
- search: tests/rag/data/retrieval_queries_20_acts.json (lawyer questions, en + bn)
Retrieval: hybrid_search, mock reranker, k=10 -> Recall@5, Recall@10, MRR@10 overall
and per language.
--rewrite: search and analysis use LLM query rewriting (app.rag.search.query_rewrite; needs
LLM_PROVIDER=gemini and its key). 429/503 answers are retried here (eval only) so quota
limits do not distort the numbers; the LLM calls are counted and reported.
Calibration: the analysis path (case_analysis.service._retrieve over fact_queries)
gives each query its best cosine similarity, the number the analysis threshold is
compared with. Relevant = both sets above; unrelated = eval/unrelated_facts.jsonl
(off-topic statements the analysis must abstain on). Chooses the midpoint of the
gap between the highest unrelated and the lowest relevant best score; if they
overlap, the lowest value that still abstains on every unrelated query.

--only-acts-in-db keeps only queries whose expected Acts are approved in the database
(for a knowledge base built from a subset of Acts); --unrelated N keeps N/2 en + N/2
bn off-topic statements. Query vectors are cached per text and the number of
embedding calls is reported (free-tier quotas count every call).
"""

import argparse
import asyncio
import json
import os
import re
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession

BACKEND = Path(__file__).resolve().parents[1]
FACTS = BACKEND / "eval" / "fact_patterns.jsonl"
SEARCH = BACKEND / "tests" / "rag" / "data" / "retrieval_queries_20_acts.json"
UNRELATED = BACKEND / "eval" / "unrelated_facts.jsonl"
BANGLA = re.compile(r"[ঀ-৿]")


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def load_sets() -> dict[str, list[dict]]:
    facts = [{"id": r["id"], "language": r["language"], "text": r["fact"], "category": r["category"],
              "expected": r["expected"]} for r in _jsonl(FACTS)]
    search = [{"id": f"q-{i:02d}", "language": "bn" if BANGLA.search(q["query"]) else "en", "text": q["query"],
               "category": "other", "expected": [{"act_id": q["act_id"], "section": q["section"]}]}
              for i, q in enumerate(json.loads(SEARCH.read_text("utf-8"))["queries"], 1)]
    unrelated = [{"id": r["id"], "language": r["language"], "text": r["fact"], "category": "other", "expected": []}
                 for r in _jsonl(UNRELATED)]
    return {"facts": facts, "search": search, "unrelated": unrelated}


def rank_of(hits, expected) -> int | None:
    for i, hit in enumerate(hits, start=1):
        for e in expected:
            if hit.act_id == e["act_id"] and (hit.section_number == e["section"]
                                              or any(a.section_number == e["section"] for a in hit.alternates)):
                return i
    return None


def retrieval_metrics(rows: list[dict]) -> dict:
    def block(subset):
        n = len(subset)
        ranks = [r["rank"] for r in subset]
        return {"n": n,
                "recall_at_5": round(sum(1 for r in ranks if r and r <= 5) / n, 3) if n else None,
                "recall_at_10": round(sum(1 for r in ranks if r and r <= 10) / n, 3) if n else None,
                "mrr_at_10": round(sum(1 / r for r in ranks if r) / n, 3) if n else None}

    return {"all": block(rows), **{lang: block([r for r in rows if r["language"] == lang]) for lang in ("en", "bn")}}


def choose_threshold(relevant: list[float], unrelated: list[float]) -> dict:
    lo_rel, hi_unrel = min(relevant), max(unrelated)
    if lo_rel > hi_unrel:
        value, rule = round((lo_rel + hi_unrel) / 2, 3), "midpoint of the gap"
    else:
        value, rule = round(hi_unrel + 0.001, 3), "overlap: just above the highest unrelated score"
    return {"value": value, "rule": rule, "lowest_relevant": round(lo_rel, 4), "highest_unrelated": round(hi_unrel, 4),
            "relevant_abstaining": sum(s < value for s in relevant), "unrelated_passing": sum(s >= value for s in unrelated)}


class RetryingLLM:
    """Eval only: retries the rewrite call on 429/503 and counts calls (the app falls back instead)."""

    def __init__(self, inner, attempts: int = 6, wait: float = 15.0):
        self.inner, self.attempts, self.wait = inner, attempts, wait
        self.provider, self.model = inner.provider, inner.model
        self.calls = self.retries = self.failures = 0

    def complete_json(self, *args):
        import time

        import httpx

        for attempt in range(self.attempts):
            self.calls += 1
            try:
                return self.inner.complete_json(*args)
            except httpx.HTTPStatusError as error:
                if error.response.status_code not in (429, 503) or attempt == self.attempts - 1:
                    self.failures += 1
                    raise
                self.retries += 1
                time.sleep(self.wait * (attempt + 1))


class CountingEmbedder:
    """Caches query vectors per text and counts the calls that reach the provider."""

    def __init__(self, inner):
        self.inner, self.calls, self._cache = inner, 0, {}
        self.model_name, self.embedding_version = inner.model_name, inner.embedding_version

    def embed_query(self, query: str) -> list[float]:
        if query not in self._cache:
            self.calls += 1
            self._cache[query] = self.inner.embed_query(query)
        return self._cache[query]


async def _approved_acts(engine) -> set[str]:
    from sqlalchemy import text

    async with engine.connect() as conn:
        return set((await conn.execute(text(
            "SELECT s.external_id FROM public.legal_sources s JOIN public.legal_source_versions v "
            "ON v.legal_source_id = s.id WHERE v.is_current AND v.review_status = 'approved'"))).scalars())


async def evaluate(only_acts_in_db: bool = False, unrelated_n: int | None = None, rewrite: bool = False) -> dict:
    from app.case_analysis.analyzer import FactInput
    from app.case_analysis.service import _retrieve
    from app.config import Settings
    from app.rag.ingest.repository import create_ingest_engine
    from app.rag.search.providers import embedding_target, get_query_embedder, get_reranker
    from app.rag.search.query_rewrite import QueryRewriter, build_query_rewriter
    from app.rag.search.retrieval import hybrid_search, rewritten_search

    settings = Settings()
    target = embedding_target(settings)
    if target.provider == "gemini":
        # Paced like bulk embedding: free tier allows 100 texts/min, rejected tries count too.
        from app.rag.search.gemini_embeddings import GeminiQueryEmbedder
        from app.rag.search.providers import gemini_client

        inner = GeminiQueryEmbedder(gemini_client(settings, attempts=6, backoff=2.0, max_wait=65.0,
                                                  texts_per_minute=80))
    else:
        inner = get_query_embedder()
    embedder, reranker = CountingEmbedder(inner), get_reranker("mock")
    llm = rewriter = None
    if rewrite:
        base = build_query_rewriter(settings).llm
        if base is None:
            raise SystemExit("--rewrite needs a configured LLM (LLM_PROVIDER=gemini, GEMINI_API_KEY, GEMINI_MODEL)")
        llm = RetryingLLM(base)
        rewriter = QueryRewriter(llm)
    searches = analysis_queries = rewrites_failed = 0
    engine = create_ingest_engine(os.environ["LEGAL_INGEST_DATABASE_URL"])
    out: dict = {"provider": target.provider, "model": target.model, "embedding_version": target.version,
                 "threshold_in_use": settings.analysis_similarity_threshold, "sets": {}}
    sets = load_sets()
    if only_acts_in_db:
        acts = await _approved_acts(engine)
        out["acts"] = sorted(acts, key=lambda a: int(a) if a.isdigit() else a)
        for name in ("facts", "search"):
            sets[name] = [r for r in sets[name] if all(e["act_id"] in acts for e in r["expected"])]
    if unrelated_n is not None:
        half = unrelated_n // 2
        sets["unrelated"] = ([r for r in sets["unrelated"] if r["language"] == "en"][:unrelated_n - half]
                             + [r for r in sets["unrelated"] if r["language"] == "bn"][:half])
    try:
        for name, rows in sets.items():
            results = []
            for row in rows:
                async with AsyncSession(engine) as session, session.begin():
                    entry = {"id": row["id"], "language": row["language"]}
                    if row["expected"]:
                        searches += 1
                        if rewriter is not None:
                            search, rw = await rewritten_search(session, query=row["text"], rewriter=rewriter,
                                                                embedder=embedder, reranker=reranker, k=10,
                                                                keyword_fallback=False)
                            rewrites_failed += rw.failed
                        else:
                            search = await hybrid_search(session, query=row["text"], embedder=embedder,
                                                         reranker=reranker, k=10, keyword_fallback=False)
                        entry["rank"] = rank_of(search.hits, row["expected"])
                    fact = FactInput(uuid4(), row["text"], row["category"], "lawyer_entered", "undisputed")
                    analysis_queries += 1
                    ranked, _ = await _retrieve(session, [fact], embedder, reranker, None, None,
                                                keyword_fallback=False, rewriter=rewriter)
                    entry["best_score"] = round(ranked[0]["score"], 4) if ranked else 0.0
                results.append(entry)
            out["sets"][name] = {"rows": results}
            if name != "unrelated":
                out["sets"][name]["retrieval"] = retrieval_metrics(results)
    finally:
        await engine.dispose()
    relevant = [r["best_score"] for s in ("facts", "search") for r in out["sets"][s]["rows"]]
    unrelated = [r["best_score"] for r in out["sets"]["unrelated"]["rows"]]
    out["calibration"] = choose_threshold(relevant, unrelated)
    out["embedding_calls"] = embedder.calls
    if llm is not None:
        # The rewriter caches per text: a search and the analysis of the same text share one call.
        out["query_rewrite"] = {"llm_model": llm.model, "llm_requests_incl_retries": llm.calls,
                                "retries_429_503": llm.retries, "failed": llm.failures,
                                "searches_fell_back_to_plain_query": rewrites_failed,
                                "searches": searches, "analysis_fact_runs": analysis_queries,
                                "llm_calls_per_new_search": 1, "llm_calls_per_analysis": "1 per analysis (all fact statements batched)"}
    return out


async def _count_only(only_acts_in_db: bool, unrelated_n: int | None) -> dict:
    """Upper bound of embedding calls: 1 search + up to 2 analysis queries per relevant row, 2 per unrelated."""
    from app.case_analysis.analyzer import FactInput
    from app.case_analysis.service import fact_queries
    from app.rag.ingest.repository import create_ingest_engine
    from app.rag.text import nfc

    sets = load_sets()
    engine = create_ingest_engine(os.environ["LEGAL_INGEST_DATABASE_URL"])
    try:
        acts = await _approved_acts(engine)
    finally:
        await engine.dispose()
    if only_acts_in_db:
        for name in ("facts", "search"):
            sets[name] = [r for r in sets[name] if all(e["act_id"] in acts for e in r["expected"])]
    if unrelated_n is not None:
        half = unrelated_n // 2
        sets["unrelated"] = ([r for r in sets["unrelated"] if r["language"] == "en"][:unrelated_n - half]
                             + [r for r in sets["unrelated"] if r["language"] == "bn"][:half])
    texts = set()
    for name, rows in sets.items():
        for r in rows:
            if r["expected"]:
                texts.add(nfc(r["text"]).strip())
            texts.update(fact_queries(FactInput(uuid4(), r["text"], r["category"], "lawyer_entered", "undisputed")))
    return {"rows": {n: len(r) for n, r in sets.items()},
            "languages": {n: {lang: sum(x["language"] == lang for x in r) for lang in ("en", "bn")}
                          for n, r in sets.items()},
            "distinct_query_texts": len(texts), "approved_acts": len(acts)}


def main() -> None:
    load_dotenv(BACKEND / ".env")
    parser = argparse.ArgumentParser(prog="python -m eval.retrieval", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", required=True, help="Name for this run, e.g. e5 or gemini")
    parser.add_argument("--out", type=Path, help="Write the full JSON here")
    parser.add_argument("--only-acts-in-db", action="store_true", help="Skip queries whose Acts are not approved")
    parser.add_argument("--unrelated", type=int, help="Number of off-topic statements (half en, half bn)")
    parser.add_argument("--dry-run", action="store_true", help="Only count the queries per set; no embedding")
    parser.add_argument("--rewrite", action="store_true", help="Use LLM query rewriting (search + analysis)")
    args = parser.parse_args()
    if args.dry_run:
        print(json.dumps(asyncio.run(_count_only(args.only_acts_in_db, args.unrelated)), indent=1))
        return
    result = {"label": args.label, **asyncio.run(evaluate(args.only_acts_in_db, args.unrelated, args.rewrite))}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {k: v for k, v in result.items() if k != "sets"}
    summary["retrieval"] = {s: result["sets"][s]["retrieval"] for s in ("facts", "search")}
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
