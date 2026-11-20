"""Evaluation harness (Step G): uv run python -m eval.run [--provider mock|gemini] [--limit N] [--write]

Reads eval/fact_patterns.jsonl (synthetic, SAMPLE_DATA_NOT_REAL_LAW) and, against
the approved legal knowledge base (read-only, LEGAL_INGEST_DATABASE_URL), reports:
- retrieval Recall@5, Recall@10, MRR@10 for the expected sections (Step B search);
- analysis abstain rate and citation-verification pass rate (Step D pipeline);
- analysis and strategy schema-validity rate: share of model outputs that
  validated without falling back to the mock (always 1.0 for --provider mock);
- strategy node verification rate (Step E).
Nothing is written to the database. --write updates DOCS/eval_results.md.
"""

import argparse
import asyncio
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession

BACKEND = Path(__file__).resolve().parents[1]
PATTERNS = Path(__file__).with_name("fact_patterns.jsonl")
RESULTS_MD = BACKEND.parent / "DOCS" / "eval_results.md"


def _rank(hits, expected) -> int | None:
    for i, hit in enumerate(hits, start=1):
        for e in expected:
            if hit.act_id == e["act_id"] and (hit.section_number == e["section"]
                                              or any(a.section_number == e["section"] for a in hit.alternates)):
                return i
    return None


async def evaluate(provider: str, limit: int | None) -> dict:
    from app.ai.llm import resolve_provider
    from app.ai.structured import generate_structured
    from app.case_analysis.analyzer import SYSTEM_PROMPT, FactInput, ProvisionInput, build_user_prompt, mock_analysis
    from app.case_analysis.schemas import AnalysisDraft
    from app.case_analysis.service import _retrieve, _verify
    from app.config import Settings
    from app.rag.ingest.repository import create_ingest_engine
    from app.rag.search.providers import get_query_embedder, get_reranker
    from app.rag.search.retrieval import hybrid_search
    from app.rag.verifier import load_chunks
    from app.strategy_tree.schemas import StrategyDraft
    from app.strategy_tree import service as strategy

    settings = Settings(llm_provider=provider, llm_approved_providers=f"mock,{provider}")
    llm = resolve_provider(settings)
    if provider != "mock" and llm is None:
        raise SystemExit(f"{provider} is not configured here (key, model, or environment)")
    rows = [json.loads(l) for l in PATTERNS.read_text("utf-8").splitlines() if l.strip()][:limit]
    engine = create_ingest_engine(os.environ["LEGAL_INGEST_DATABASE_URL"])
    embedder, reranker = get_query_embedder(), get_reranker("mock")
    per_pattern = []
    started = time.perf_counter()
    try:
        for row in rows:
            async with AsyncSession(engine) as session, session.begin():
                search = await hybrid_search(session, query=row["fact"], embedder=embedder, reranker=reranker, k=10)
                rank = _rank(search.hits, row["expected"])
                fact = FactInput(uuid4(), row["fact"], row["category"], "lawyer_entered", "undisputed")
                ranked, _ = await _retrieve(session, [fact], embedder, reranker, None, None)
                relevant = [e for e in ranked if e["score"] >= settings.analysis_min_similarity][:8]
                provisions = [ProvisionInput(e["hit"].chunk_id, e["hit"].act_title, e["hit"].section_number,
                                             e["hit"].text) for e in relevant]
                chunks = await load_chunks(session, [p.chunk_id for p in provisions])
            entry = {"id": row["id"], "language": row["language"], "rank": rank, "abstained": not provisions}
            if provisions:
                analysis = await generate_structured(llm, AnalysisDraft, SYSTEM_PROMPT,
                                                     build_user_prompt([fact], provisions),
                                                     lambda: mock_analysis([fact], provisions), True)
                findings, summary = _verify(analysis.value, chunks, {fact.id}, None,
                                            {p.chunk_id for p in provisions}, False)
                tree_draft = await generate_structured(
                    llm, StrategyDraft, strategy.SYSTEM_PROMPT, strategy._prompt(findings, chunks, [
                        {"id": fact.id, "statement": fact.statement}]),
                    lambda: strategy.mock_strategy(findings), True)
                root, tree_summary = strategy.build_tree(tree_draft.value, chunks, {p.chunk_id for p in provisions},
                                                         None, False, "eval")
                entry.update({
                    "citations": summary["citations_verified"] + summary["citations_failed"],
                    "citations_verified": summary["citations_verified"],
                    "analysis_valid": analysis.origin == "ai" or llm is None,
                    "strategy_valid": tree_draft.origin == "ai" or llm is None,
                    "nodes": tree_summary["nodes"], "nodes_verified": tree_summary["nodes_verified"],
                    "no_verified_finding": not any(f["verification"] == "verified" for f in findings),
                })
                if llm is not None:
                    await asyncio.sleep(4)  # stay under free-tier request limits
            per_pattern.append(entry)
    finally:
        await engine.dispose()

    def rate(num, den):
        return round(num / den, 3) if den else None

    n = len(per_pattern)
    ran = [p for p in per_pattern if not p["abstained"]]
    ranks = [p["rank"] for p in per_pattern]
    metrics = {
        "patterns": n, "en": sum(p["language"] == "en" for p in per_pattern),
        "bn": sum(p["language"] == "bn" for p in per_pattern),
        "recall_at_5": rate(sum(1 for r in ranks if r and r <= 5), n),
        "recall_at_10": rate(sum(1 for r in ranks if r and r <= 10), n),
        "mrr_at_10": round(sum(1 / r for r in ranks if r) / n, 3) if n else None,
        "abstain_rate": rate(sum(p["abstained"] for p in per_pattern), n),
        "citation_verification_pass_rate": rate(sum(p.get("citations_verified", 0) for p in ran),
                                                sum(p.get("citations", 0) for p in ran)),
        "analysis_schema_validity": rate(sum(p["analysis_valid"] for p in ran), len(ran)),
        "strategy_schema_validity": rate(sum(p["strategy_valid"] for p in ran), len(ran)),
        "strategy_node_verification_rate": rate(sum(p["nodes_verified"] for p in ran), sum(p["nodes"] for p in ran)),
        "seconds": round(time.perf_counter() - started, 1),
    }
    for language in ("en", "bn"):
        subset = [p["rank"] for p in per_pattern if p["language"] == language]
        metrics[f"recall_at_10_{language}"] = rate(sum(1 for r in subset if r and r <= 10), len(subset))
    return {"provider": provider, "model": getattr(llm, "model", None), "metrics": metrics, "patterns": per_pattern}


def to_markdown(results: list[dict]) -> str:
    keys = ["patterns", "recall_at_5", "recall_at_10", "recall_at_10_en", "recall_at_10_bn", "mrr_at_10",
            "abstain_rate", "citation_verification_pass_rate", "analysis_schema_validity",
            "strategy_schema_validity", "strategy_node_verification_rate", "seconds"]
    header = "| Metric | " + " | ".join(f"{r['provider']}" + (f" ({r['model']})" if r["model"] else "") for r in results) + " |"
    lines = [header, "|---|" + "---|" * len(results)]
    lines += [f"| {k} | " + " | ".join(str(r["metrics"].get(k)) for r in results) + " |" for k in keys]
    base = results[0]["patterns"]
    misses = [p["id"] for p in base if not p["rank"] or p["rank"] > 10]
    return "\n".join(lines) + f"\n\nRetrieval misses at 10 ({results[0]['provider']} run): {', '.join(misses) or 'none'}\n"


def main() -> None:
    load_dotenv(BACKEND / ".env")
    parser = argparse.ArgumentParser(prog="python -m eval.run", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", action="append", choices=("mock", "gemini", "ollama"),
                        help="Repeat to compare providers (default: mock)")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--write", action="store_true", help=f"Write {RESULTS_MD.name}")
    args = parser.parse_args()
    results = [asyncio.run(evaluate(p, args.limit)) for p in (args.provider or ["mock"])]
    print(json.dumps([{k: r[k] for k in ("provider", "model", "metrics")} for r in results], indent=2))
    if args.write:
        RESULTS_MD.write_text(
            "# Evaluation results\n\n"
            f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC by `uv run python -m eval.run "
            f"{' '.join('--provider ' + r['provider'] for r in results)} --write` against the local approved "
            "knowledge base. Fact patterns: `backend/eval/fact_patterns.jsonl` (synthetic, SAMPLE_DATA_NOT_REAL_LAW).\n\n"
            "Schema validity counts model outputs that validated without falling back to the mock (1.0 by "
            "definition for the mock). Citation verification is the deterministic verifier (Step D). Reranker: mock "
            "(fused order); abstain threshold: cosine similarity 0.79.\n\n" + to_markdown(results),
            encoding="utf-8")
        print(f"wrote {RESULTS_MD}")


if __name__ == "__main__":
    main()
