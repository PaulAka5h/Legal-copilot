"""Exact page span for fact quotes.

case_fact_sources gets quote_start / quote_end (offsets into the cited page
version's text) and quote_match (exact | normalized). When a quote is found,
the stored quote is exactly page_text[quote_start:quote_end]; when it is not
found the offsets stay NULL and quote_check is 'failed' (shown as unverified).
Existing rows keep NULL offsets. Sources stay immutable (INSERT only).

Revision ID: 0024_fact_quote_span
Revises: 0023_archive_summary_versions
Create Date: 2026-11-23
"""

from alembic import op

revision = "0024_fact_quote_span"
down_revision = "0023_archive_summary_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        """
        ALTER TABLE public.case_fact_sources
          ADD COLUMN quote_start integer,
          ADD COLUMN quote_end integer,
          ADD COLUMN quote_match text CHECK (quote_match IN ('exact', 'normalized')),
          ADD CONSTRAINT case_fact_sources_span_check CHECK (
            (quote_start IS NULL AND quote_end IS NULL AND quote_match IS NULL)
            OR (quote_start >= 0 AND quote_end > quote_start AND quote_match IS NOT NULL
                AND quote_check = 'passed'))
        """
    )
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        "ALTER TABLE public.case_fact_sources DROP CONSTRAINT case_fact_sources_span_check, "
        "DROP COLUMN quote_match, DROP COLUMN quote_end, DROP COLUMN quote_start"
    )
    op.execute("RESET ROLE")
