"""CLI for legal chunk embeddings (as app_admin_ingest, LEGAL_INGEST_DATABASE_URL).

  python -m app.rag.embed run    [--device auto|cpu|cuda] [--batch-size N] [--limit N] [--dry-run]
  python -m app.rag.embed export --out chunks.jsonl [--limit N]
  python -m app.rag.embed import --parquet embeddings.parquet [--reject-report PATH]

run embeds locally. export/import offload the model to an external GPU
(scripts/kaggle_embed.py); only public legal KB text is exported.
Chunk text is never printed.
"""

import argparse
import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

from app.rag.embed.offload import export_pending, import_parquet
from app.rag.embed.worker import E5Embedder, EmbedStats, count_pending, embed_pending, is_out_of_memory, pick_device
from app.rag.ingest.chunking import EMBEDDING_MODEL, EMBEDDING_VERSION
from app.rag.ingest.records import REPO_ROOT
from app.rag.ingest.repository import create_ingest_engine

DEFAULT_IMPORT_REPORT = REPO_ROOT / "data-scrapper" / "data" / "reports" / "embed_import_rejects.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m app.rag.embed", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="Embed pending chunks on this machine")
    run.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    run.add_argument("--batch-size", type=int, default=16, help="Chunks per transaction and model batch")
    run.add_argument("--limit", type=int, help="Maximum chunks to process in this run")
    run.add_argument("--dry-run", action="store_true", help="Only report how many chunks are pending")

    export = commands.add_parser("export", help="Write pending chunks to JSONL for an external GPU")
    export.add_argument("--out", type=Path, required=True)
    export.add_argument("--limit", type=int)

    imp = commands.add_parser("import", help="Load embeddings from a parquet file")
    imp.add_argument("--parquet", type=Path, required=True)
    imp.add_argument("--reject-report", type=Path, default=DEFAULT_IMPORT_REPORT)

    args = parser.parse_args()
    for name in ("batch_size", "limit"):
        value = getattr(args, name, None)
        if value is not None and value < 1:
            parser.error(f"--{name.replace('_', '-')} must be at least 1")
    return args


async def run_local(engine, args) -> dict:
    pending_before = await count_pending(engine)
    result = {"model": EMBEDDING_MODEL, "embedding_version": EMBEDDING_VERSION, "pending_before": pending_before}
    if args.dry_run or pending_before == 0:
        return {**result, "dry_run": args.dry_run}

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
        if args.command == "run":
            return await run_local(engine, args)
        if args.command == "export":
            rows = await export_pending(engine, args.out, args.limit)
            return {"exported": rows, "out": str(args.out), "model": EMBEDDING_MODEL,
                    "pending_total": await count_pending(engine)}
        stats = await import_parquet(engine, args.parquet)
        args.reject_report.parent.mkdir(parents=True, exist_ok=True)
        args.reject_report.write_text(json.dumps({"rejected": stats.rejected}, indent=2), encoding="utf-8")
        return {"rows": stats.rows, "imported": stats.imported, "already_embedded": stats.already_embedded,
                "rejected": len(stats.rejected), "reject_report": str(args.reject_report),
                "pending_after": await count_pending(engine)}
    finally:
        await engine.dispose()


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    print(json.dumps(asyncio.run(run(parse_args())), indent=2))


if __name__ == "__main__":
    main()
