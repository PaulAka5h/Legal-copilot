"""CLI: uv run python -m app.rag.embed [--device auto|cpu|cuda] [--batch-size N] [--limit N] [--dry-run]

Embeds pending legal chunks as app_admin_ingest (LEGAL_INGEST_DATABASE_URL).
--device auto picks CUDA when available; if CUDA runs out of memory the batch
rolls back and the worker continues on CPU. Chunk text is never printed.
"""

import argparse
import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

from app.rag.embed.worker import E5Embedder, EmbedStats, count_pending, embed_pending, is_out_of_memory, pick_device
from app.rag.ingest.chunking import EMBEDDING_MODEL, EMBEDDING_VERSION
from app.rag.ingest.repository import create_ingest_engine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m app.rag.embed", description=__doc__)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--batch-size", type=int, default=16, help="Chunks per transaction and model batch")
    parser.add_argument("--limit", type=int, help="Maximum chunks to process in this run")
    parser.add_argument("--dry-run", action="store_true", help="Only report how many chunks are pending")
    args = parser.parse_args()
    if args.batch_size < 1 or (args.limit is not None and args.limit < 1):
        parser.error("--batch-size and --limit must be at least 1")
    return args


async def run(args: argparse.Namespace) -> dict:
    url = os.getenv("LEGAL_INGEST_DATABASE_URL")
    if not url:
        raise SystemExit("LEGAL_INGEST_DATABASE_URL is required")
    engine = create_ingest_engine(url)
    try:
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
    finally:
        await engine.dispose()


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    print(json.dumps(asyncio.run(run(parse_args())), indent=2))


if __name__ == "__main__":
    main()
