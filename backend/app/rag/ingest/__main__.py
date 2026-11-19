"""CLI: uv run python -m app.rag.ingest --input PATH [--language bn|en] [--limit N]
                                      [--act-id ID ...] [--force-rechunk] [--dry-run]

--limit counts Acts (one Act in one language), not sections, so no partial
source version is ever written. Writes need LEGAL_INGEST_DATABASE_URL
(postgresql+asyncpg as app_admin_ingest). Rejects are written to a JSON report
with IDs and issue names only. Legal text is never printed or logged.
"""

import argparse
import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

from app.rag.ingest.chunking import load_counter
from app.rag.ingest.pipeline import ingest_batches
from app.rag.ingest.records import REPO_ROOT, Rejects, iter_act_batches
from app.rag.ingest.repository import create_ingest_engine

DEFAULT_INPUT = REPO_ROOT / "data-scrapper" / "data" / "processed" / "sections.jsonl"
DEFAULT_REJECTS = REPO_ROOT / "data-scrapper" / "data" / "reports" / "ingest_rejects.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m app.rag.ingest", description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="sections.jsonl from the scraper")
    parser.add_argument("--language", choices=("bn", "en"), help="Only ingest this language")
    parser.add_argument("--limit", type=int, help="Maximum number of Acts to process")
    parser.add_argument("--act-id", action="append", help="Only this bdlaws Act ID (repeatable)")
    parser.add_argument(
        "--force-rechunk", action="store_true",
        help="Create a new version even if the text is unchanged (after a chunking change); needs re-approval",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate and chunk only; no database writes")
    parser.add_argument("--reject-report", type=Path, default=DEFAULT_REJECTS)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    return args


async def run(args: argparse.Namespace) -> dict:
    engine = None
    if not args.dry_run:
        url = os.getenv("LEGAL_INGEST_DATABASE_URL")
        if not url:
            raise SystemExit("LEGAL_INGEST_DATABASE_URL is required unless --dry-run is set")
        engine = create_ingest_engine(url)

    rejects = Rejects()
    try:
        summary = await ingest_batches(
            iter_act_batches(
                args.input, rejects, language=args.language,
                act_ids=set(args.act_id) if args.act_id else None,
            ),
            load_counter(),
            engine,
            limit=args.limit,
            force_rechunk=args.force_rechunk,
        )
    finally:
        if engine is not None:
            await engine.dispose()

    args.reject_report.parent.mkdir(parents=True, exist_ok=True)
    args.reject_report.write_text(
        json.dumps({"rejects": rejects.items, "chunk_errors": summary.chunk_errors}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    result = asdict(summary)
    result.pop("chunk_errors")
    return {
        "dry_run": args.dry_run,
        **result,
        "chunk_error_count": len(summary.chunk_errors),
        "rejected_records_seen": len(rejects.items),
        "reject_report": str(args.reject_report),
    }


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    print(json.dumps(asyncio.run(run(parse_args())), indent=2))


if __name__ == "__main__":
    main()
