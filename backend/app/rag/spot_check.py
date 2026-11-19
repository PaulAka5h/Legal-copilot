"""Pick random pending legal source versions for a human spot-check before approval.

uv run python -m app.rag.spot_check [--n 25] [--seed N] [--json]

Read-only (as app_admin_ingest, LEGAL_INGEST_DATABASE_URL). Prints each sampled
Act's title, language, version, section count, version ID, and official source
URL, so a reviewer can compare the stored text with bdlaws before running
`python -m app.rag.approve`. --seed makes the sample reproducible.
"""

import argparse
import asyncio
import json
import os
import random
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

from app.rag.ingest.repository import create_ingest_engine

_PENDING = text(
    """
    SELECT v.id, s.external_id, s.language, s.title, s.source_url, v.version_no, v.amendment_note,
           (SELECT count(*) FROM public.legal_sections x WHERE x.legal_source_version_id = v.id) AS sections
    FROM public.legal_source_versions v JOIN public.legal_sources s ON s.id = v.legal_source_id
    WHERE v.review_status = 'pending'
    ORDER BY v.id
    """
)


async def sample_pending(url: str, n: int, seed: int | None) -> tuple[int, list[dict]]:
    engine = create_ingest_engine(url)
    try:
        async with engine.connect() as conn:
            rows = [dict(r._mapping) for r in await conn.execute(_PENDING)]
    finally:
        await engine.dispose()
    picked = random.Random(seed).sample(rows, min(n, len(rows)))
    picked.sort(key=lambda r: (r["external_id"].zfill(8), r["language"]))
    return len(rows), picked


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    parser = argparse.ArgumentParser(prog="python -m app.rag.spot_check", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=25, help="How many pending Acts to sample")
    parser.add_argument("--seed", type=int, help="Random seed for a reproducible sample")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a table")
    args = parser.parse_args()
    if args.n < 1:
        parser.error("--n must be at least 1")
    url = os.getenv("LEGAL_INGEST_DATABASE_URL")
    if not url:
        raise SystemExit("LEGAL_INGEST_DATABASE_URL is required")

    total, picked = asyncio.run(sample_pending(url, args.n, args.seed))
    if args.json:
        print(json.dumps({"pending_total": total, "seed": args.seed, "sample": [
            {**r, "id": str(r["id"])} for r in picked
        ]}, ensure_ascii=False, indent=2))
        return
    print(f"{len(picked)} of {total} pending versions (seed={args.seed})\n")
    for i, r in enumerate(picked, start=1):
        note = "  [re-chunk only]" if r["amendment_note"] else ""
        print(f"{i:>2}. Act {r['external_id']} ({r['language']}) v{r['version_no']}, {r['sections']} sections{note}")
        print(f"    {r['title']}")
        print(f"    {r['source_url']}")
        print(f"    version_id {r['id']}\n")


if __name__ == "__main__":
    main()
