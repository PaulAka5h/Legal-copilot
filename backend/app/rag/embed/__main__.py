"""CLI for legal chunk embeddings (as app_admin_ingest, LEGAL_INGEST_DATABASE_URL).

  python -m app.rag.embed run     [--provider e5_small_onnx|local|gemini] [--threads N] [--device auto|cpu|cuda]
                                  [--batch-size N] [--limit N] [--dry-run]
  python -m app.rag.embed reembed --provider e5_small_onnx|local|gemini --yes [--batch-size N]
  python -m app.rag.embed export  --out chunks.jsonl [--limit N]
  python -m app.rag.embed import  --parquet embeddings.parquet [--reject-report PATH]

run embeds pending chunks with e5-small ONNX int8 on this CPU (e5_small_onnx; resumable,
idempotent by content_hash; several processes can share the queue, e.g. 4 x --threads 2),
with e5-large on this machine (local) or with the Gemini API
(gemini, GEMINI_API_KEY + GEMINI_EMBEDDING_MODEL; synthetic/public text only).
--provider defaults to EMBEDDING_PROVIDER (hf_api means local: same e5 model).
reembed switches the whole knowledge base to that provider's model: it clears every
vector made by another model (back them up first: deploy/embeddings_backup.sh) and
embeds again; it is resumable (run it again after an interruption).
export/import offload the configured provider's model to another machine
(scripts/kaggle_embed_e5small.py for e5_small_onnx, scripts/kaggle_embed.py for e5-large); only public
legal KB text is exported. Chunk text is never printed.
"""

import argparse
import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

from app.rag.embed.offload import export_pending, import_parquet
from app.config import Settings
from app.rag.embed.worker import (
    E5Embedder,
    EmbedStats,
    count_pending,
    embed_pending,
    is_out_of_memory,
    pick_device,
    relabel_for,
)
from app.rag.ingest.chunking import EMBEDDING_MODEL, EMBEDDING_VERSION
from app.rag.ingest.records import REPO_ROOT
from app.rag.ingest.repository import create_ingest_engine
from app.rag.search.e5_small_onnx import E5SmallDocumentEmbedder, E5SmallOnnx
from app.rag.search.gemini_embeddings import GeminiDocumentEmbedder
from app.rag.search.providers import embedding_target, gemini_client

DEFAULT_IMPORT_REPORT = REPO_ROOT / "data-scrapper" / "data" / "reports" / "embed_import_rejects.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m app.rag.embed", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="Embed pending chunks")
    reembed = commands.add_parser("reembed", help="Re-embed the whole knowledge base with another model")
    for sub in (run, reembed):
        sub.add_argument("--provider", choices=("e5_small_onnx", "local", "gemini"),
                         help="Default: EMBEDDING_PROVIDER")
        sub.add_argument("--threads", type=int, default=os.cpu_count() or 1,
                         help="e5_small_onnx: onnxruntime intra-op threads (default: all cores)")
        sub.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto", help="local only")
        sub.add_argument("--batch-size", type=int,
                         help="Chunks per transaction (default 32 e5_small_onnx, 16 local, 30 gemini)")
        sub.add_argument("--limit", type=int, help="Maximum chunks to process in this run")
        sub.add_argument("--per-minute", type=int, default=90,
                         help="gemini: texts sent per minute (free tier allows 100; default 90)")
    run.add_argument("--dry-run", action="store_true", help="Only report how many chunks are pending")
    reembed.add_argument("--yes", action="store_true", required=True,
                         help="Confirm: vectors from other models are cleared (back them up first)")

    export = commands.add_parser("export", help="Write pending chunks to JSONL for an external GPU")
    export.add_argument("--out", type=Path, required=True)
    export.add_argument("--limit", type=int)

    imp = commands.add_parser("import", help="Load embeddings from a parquet file")
    imp.add_argument("--parquet", type=Path, required=True)
    imp.add_argument("--reject-report", type=Path, default=DEFAULT_IMPORT_REPORT)

    args = parser.parse_args()
    for name in ("batch_size", "limit", "per_minute", "threads"):
        value = getattr(args, name, None)
        if value is not None and value < 1:
            parser.error(f"--{name.replace('_', '-')} must be at least 1")
    return args


def resolve_provider(args: argparse.Namespace) -> str:
    provider = args.provider or Settings().embedding_provider
    return "local" if provider == "hf_api" else provider  # hf_api: same e5-large vectors as local


async def run_e5_small(engine, args) -> dict:
    target = embedding_target(Settings(embedding_provider="e5_small_onnx"))
    pending_before = await count_pending(engine, target.model, target.version)
    result = {"model": target.model, "embedding_version": target.version, "pending_before": pending_before}
    if getattr(args, "dry_run", False) or pending_before == 0:
        return {**result, "dry_run": getattr(args, "dry_run", False)}
    embedder = E5SmallDocumentEmbedder(E5SmallOnnx(threads=args.threads))
    batch = args.batch_size or 32
    stats = await embed_pending(engine, embedder, batch, args.limit, EmbedStats())
    done = stats.embedded + stats.reused_by_content_hash
    return {**result, "device": embedder.device, "threads": args.threads, "batch_size": batch, **asdict(stats),
            "pending_after": await count_pending(engine, target.model, target.version),
            "seconds_per_100_chunks_total": round(100 * stats.total_seconds / done, 2) if done else None}


async def run_gemini(engine, args) -> dict:
    settings = Settings(embedding_provider="gemini")
    target = embedding_target(settings)
    pending_before = await count_pending(engine, target.model, target.version)
    result = {"model": target.model, "embedding_version": target.version, "pending_before": pending_before}
    if getattr(args, "dry_run", False) or pending_before == 0:
        return {**result, "dry_run": getattr(args, "dry_run", False)}
    # Bulk: patient retries (free-tier per-minute quotas reset within a minute).
    embedder = GeminiDocumentEmbedder(gemini_client(settings, attempts=10, backoff=2.0, max_wait=65.0,
                                                    texts_per_minute=args.per_minute))
    batch = args.batch_size or 30
    stats = await embed_pending(engine, embedder, batch, args.limit, EmbedStats())
    return {**result, "batch_size": batch, **asdict(stats),
            "pending_after": await count_pending(engine, target.model, target.version)}


async def run_local(engine, args) -> dict:
    pending_before = await count_pending(engine)
    result = {"model": EMBEDDING_MODEL, "embedding_version": EMBEDDING_VERSION, "pending_before": pending_before}
    if getattr(args, "dry_run", False) or pending_before == 0:
        return {**result, "dry_run": getattr(args, "dry_run", False)}
    args.batch_size = args.batch_size or 16

    device = pick_device(args.device)
    stats = EmbedStats()
    try:
        embedder = E5Embedder(device, args.batch_size)
        await embed_pending(engine, embedder, args.batch_size, args.limit, stats)
    except Exception as error:
        if device != "cuda" or not is_out_of_memory(error):
            raise
        device = "cpu"  # the failed batch rolled back; committed batches are kept
        embedder = E5Embedder(device, args.batch_size)
        await embed_pending(engine, embedder, args.batch_size, args.limit, stats)

    done = stats.embedded + stats.reused_by_content_hash
    return {
        **result,
        "device": device,
        "batch_size": args.batch_size,
        **asdict(stats),
        "pending_after": await count_pending(engine),
        "seconds_per_100_chunks_total": round(100 * stats.total_seconds / done, 2) if done else None,
        "seconds_per_100_chunks_encode": round(100 * stats.encode_seconds / stats.embedded, 2)
        if stats.embedded else None,
    }


async def run(args: argparse.Namespace) -> dict:
    url = os.getenv("LEGAL_INGEST_DATABASE_URL")
    if not url:
        raise SystemExit("LEGAL_INGEST_DATABASE_URL is required")
    engine = create_ingest_engine(url)
    try:
        if args.command in ("run", "reembed"):
            provider = resolve_provider(args)
            relabelled = None
            if args.command == "reembed":
                target = embedding_target(Settings(embedding_provider=provider))
                relabelled = await relabel_for(engine, target.model, target.version)
            runner = {"e5_small_onnx": run_e5_small, "gemini": run_gemini, "local": run_local}[provider]
            result = await runner(engine, args)
            return result if relabelled is None else {"relabelled": relabelled, **result}
        if args.command == "export":
            target = embedding_target(Settings())
            rows = await export_pending(engine, args.out, target, args.limit)
            return {"exported": rows, "out": str(args.out), "model": target.model,
                    "pending_total": await count_pending(engine, target.model, target.version)}
        target = embedding_target(Settings())
        stats = await import_parquet(engine, args.parquet, target)
        args.reject_report.parent.mkdir(parents=True, exist_ok=True)
        args.reject_report.write_text(json.dumps({"rejected": stats.rejected}, indent=2), encoding="utf-8")
        return {"rows": stats.rows, "imported": stats.imported, "already_embedded": stats.already_embedded,
                "rejected": len(stats.rejected), "reject_report": str(args.reject_report),
                "pending_after": await count_pending(engine, target.model, target.version)}
    finally:
        await engine.dispose()


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    print(json.dumps(asyncio.run(run(parse_args())), indent=2))


if __name__ == "__main__":
    main()
