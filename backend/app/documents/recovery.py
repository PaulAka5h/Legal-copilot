"""Crash recovery: mark documents stuck in 'processing' as failed (retryable).

Calls app.fail_stuck_documents (migration 0015), which updates only stuck rows
across all cases and writes one audit event per document. Runs at app startup
(Settings.sweep_stuck_documents_on_startup) and from the CLI:

    uv run python -m app.documents.recovery [--older-than-minutes N]
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.database import create_database_engine

MIN_MINUTES = 5


async def sweep_stuck_documents(engine: AsyncEngine, older_than_minutes: int) -> int:
    if older_than_minutes < MIN_MINUTES:
        raise ValueError(f"older_than_minutes must be at least {MIN_MINUTES}")
    async with engine.begin() as conn:
        return await conn.scalar(
            text("SELECT app.fail_stuck_documents(make_interval(mins => :m))"), {"m": older_than_minutes}
        )


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    parser = argparse.ArgumentParser(prog="python -m app.documents.recovery", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--older-than-minutes", type=int, default=int(os.getenv("STUCK_PROCESSING_MINUTES", 30)))
    args = parser.parse_args()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL (app_user) is required")

    async def run() -> int:
        engine = create_database_engine(url)
        try:
            return await sweep_stuck_documents(engine, args.older_than_minutes)
        finally:
            await engine.dispose()

    print(json.dumps({"marked_failed": asyncio.run(run()), "older_than_minutes": args.older_than_minutes}))


if __name__ == "__main__":
    main()
