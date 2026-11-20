"""CLI: approve legal source versions for search after human review.

uv run python -m app.rag.approve (--version-id ID [--version-id ID ...] | --all-pending)
                                 --reviewer-email EMAIL [--note TEXT] [--dry-run]

Nothing is approved automatically: a person names the versions (or explicitly
asks for all pending) and the reviewer, who must be an active lawyer or admin.
Each approval records reviewed_by/reviewed_at and an audit event (migration 0012).
All selected versions are approved in one transaction: all or nothing.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv
from sqlalchemy import text

from app.rag.ingest.repository import create_ingest_engine

_TARGETS = text(
    """
    SELECT v.id, s.external_id, s.language, v.version_no, v.review_status, s.title,
           (SELECT count(*) FROM public.legal_sections x WHERE x.legal_source_version_id = v.id) AS sections
    FROM public.legal_source_versions v JOIN public.legal_sources s ON s.id = v.legal_source_id
    WHERE (:all_pending AND v.review_status = 'pending') OR v.id = ANY(CAST(:ids AS uuid[]))
    ORDER BY s.external_id, s.language, v.version_no
    """
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m app.rag.approve", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--version-id", type=UUID, action="append", help="Version to approve (repeatable)")
    target.add_argument("--all-pending", action="store_true", help="Approve every pending version")
    parser.add_argument("--reviewer-email", required=True, help="Active lawyer or admin who reviewed the text")
    parser.add_argument("--note", help="Optional review note stored in the audit event")
    parser.add_argument("--dry-run", action="store_true", help="List what would be approved; change nothing")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> dict:
    url = os.getenv("LEGAL_INGEST_DATABASE_URL")
    if not url:
        raise SystemExit("LEGAL_INGEST_DATABASE_URL is required")
    engine = create_ingest_engine(url)
    try:
        async with engine.begin() as conn:
            reviewer = await conn.scalar(
                text("SELECT app.find_legal_reviewer(:email)"), {"email": args.reviewer_email}
            )
            rows = (
                await conn.execute(
                    _TARGETS, {"all_pending": args.all_pending, "ids": args.version_id or []}
                )
            ).all()
            missing = sorted({str(i) for i in args.version_id or []} - {str(r.id) for r in rows})
            not_pending = [str(r.id) for r in rows if r.review_status != "pending"]
            versions = [
                {"version_id": str(r.id), "act_id": r.external_id, "language": r.language,
                 "version_no": r.version_no, "title": r.title, "sections": r.sections}
                for r in rows if r.review_status == "pending"
            ]
            result = {
                "dry_run": args.dry_run,
                "reviewer_eligible": reviewer is not None,
                "to_approve": len(versions),
                "unknown_version_ids": missing,
                "not_pending_version_ids": not_pending,
                "versions": versions,
            }
            if args.dry_run:
                return result
            if reviewer is None:
                raise SystemExit("Reviewer must be an active lawyer or admin; nothing approved")
            if missing or not_pending:
                raise SystemExit("Some version IDs are unknown or not pending; nothing approved")
            for version in versions:
                await conn.execute(
                    text("SELECT app.approve_legal_source_version(:id, :email, :note)"),
                    {"id": UUID(version["version_id"]), "email": args.reviewer_email, "note": args.note},
                )
            return {**result, "approved": len(versions)}
    finally:
        await engine.dispose()


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    print(json.dumps(asyncio.run(run(parse_args())), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
