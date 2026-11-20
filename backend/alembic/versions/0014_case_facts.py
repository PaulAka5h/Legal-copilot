"""AI runs, case facts, and fact sources (Step C2/C3).

ai_runs: one row per AI call batch; stores provider, model, prompt version and
  an input hash, never prompts or document text. 'fact_extraction' run type and
  'extraction_failed' status added to database.md section 9.
case_facts: versioned by lineage (lineage_id, version, supersedes_id, is_current).
  Content columns are never updated: an edit inserts a new version. Only review
  and current-flag columns are updatable. Naming follows database.md section 8
  (fact_status, review_status), extended with category/attributes/origin.
  statement_type is the AGENTS.md Rule 3 label: document_says, lawyer_entered,
  ai_inference, assumption. origin is provenance (ai, ai_mock, lawyer).
  fact_status is the fact's standing (undisputed, disputed, ...).
  A document_says fact can be confirmed only if its quote check passed;
  only a lawyer can produce lawyer_entered.
case_facts_for_analysis (view, security_invoker): the only facts analysis may
  use: current, not rejected, and lawyer_entered or lawyer-confirmed.
case_fact_sources: page-level provenance pinned to a specific extracted_pages
  version, with the quote and its deterministic check result. Immutable.

Access: lawyer members read; writes require app.can_write_case. No client
policy. No DELETE grant.

Revision ID: 0014_case_facts
Revises: 0013_case_documents
Create Date: 2026-11-20
"""

from alembic import op

revision = "0014_case_facts"
down_revision = "0013_case_documents"
branch_labels = None
depends_on = None

TABLES = ("ai_runs", "case_facts", "case_fact_sources")


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        """
        CREATE TABLE public.ai_runs (
          id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          case_id         uuid NOT NULL REFERENCES public.cases(id),
          organization_id uuid NOT NULL REFERENCES public.organizations(id),
          requested_by    uuid NOT NULL REFERENCES public.users(id),
          run_type        text NOT NULL CHECK (run_type IN ('case_analysis','legal_research','strategy',
                            'reassessment','client_draft','verification','processing','fact_extraction')),
          agent           text,
          provider        text NOT NULL,
          model           text,
          prompt_version  text,
          input_hash      bytea CHECK (input_hash IS NULL OR octet_length(input_hash) = 32),
          settings        jsonb NOT NULL DEFAULT '{}'::jsonb,
          status          text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','succeeded',
                            'partial','failed','cancelled','extraction_failed','not_configured')),
          error           text,  -- error code only, never prompts or document text
          attempts        int NOT NULL DEFAULT 0 CHECK (attempts >= 0),
          tokens_in       int,
          tokens_out      int,
          started_at      timestamptz,
          finished_at     timestamptz,
          created_at      timestamptz NOT NULL DEFAULT now(),
          UNIQUE (id, case_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_ai_runs_case_created ON public.ai_runs (case_id, created_at DESC)")

    op.execute(
        """
        CREATE TABLE public.case_facts (
          id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          case_id           uuid NOT NULL REFERENCES public.cases(id),
          organization_id   uuid NOT NULL REFERENCES public.organizations(id),
          lineage_id        uuid NOT NULL,
          version           int NOT NULL CHECK (version >= 1),
          supersedes_id     uuid REFERENCES public.case_facts(id),
          is_current        boolean NOT NULL DEFAULT true,
          category          text NOT NULL CHECK (category IN ('party','date','place','act_or_omission',
                              'document','relief_sought','other')),
          statement         text NOT NULL CHECK (length(statement) BETWEEN 1 AND 4000),
          attributes        jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(attributes) = 'object'),
          statement_type    text NOT NULL CHECK (statement_type IN ('document_says','lawyer_entered',
                              'ai_inference','assumption')),
          fact_status       text NOT NULL DEFAULT 'undisputed' CHECK (fact_status IN ('undisputed',
                              'disputed','needs_clarification','verified_record')),
          origin            text NOT NULL CHECK (origin IN ('ai','ai_mock','lawyer')),
          source_check      text NOT NULL CHECK (source_check IN ('passed','failed','not_applicable')),
          review_status     text NOT NULL DEFAULT 'draft'
                              CHECK (review_status IN ('draft','lawyer_reviewed','lawyer_rejected')),
          review_note       text CHECK (review_note IS NULL OR length(review_note) <= 2000),
          reviewed_by       uuid REFERENCES public.users(id),
          reviewed_at       timestamptz,
          extraction_run_id uuid,
          created_by        uuid NOT NULL REFERENCES public.users(id),
          created_at        timestamptz NOT NULL DEFAULT now(),
          FOREIGN KEY (extraction_run_id, case_id) REFERENCES public.ai_runs(id, case_id),
          UNIQUE (lineage_id, version),
          UNIQUE (id, case_id),
          CHECK ((version = 1) = (supersedes_id IS NULL)),
          CHECK ((review_status = 'draft') = (reviewed_by IS NULL AND reviewed_at IS NULL)),
          CHECK ((origin = 'lawyer') = (extraction_run_id IS NULL)),
          CHECK (statement_type <> 'lawyer_entered' OR origin = 'lawyer'),
          CHECK (NOT (review_status = 'lawyer_reviewed' AND statement_type = 'document_says'
                      AND source_check <> 'passed'))
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX ux_case_facts_current ON public.case_facts (lineage_id) WHERE is_current")
    op.execute(
        "CREATE INDEX ix_case_facts_case_review ON public.case_facts (case_id, review_status) WHERE is_current"
    )

    op.execute(
        """
        CREATE TABLE public.case_fact_sources (
          id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          fact_id         uuid NOT NULL,
          case_id         uuid NOT NULL,
          organization_id uuid NOT NULL,
          source_kind     text NOT NULL CHECK (source_kind IN ('document_page','lawyer_note')),
          document_id     uuid,
          page_id         uuid,
          page_no         int CHECK (page_no IS NULL OR page_no >= 1),
          quote           text CHECK (quote IS NULL OR length(quote) BETWEEN 1 AND 2000),
          quote_check     text NOT NULL CHECK (quote_check IN ('passed','failed','not_applicable')),
          created_at      timestamptz NOT NULL DEFAULT now(),
          FOREIGN KEY (fact_id, case_id) REFERENCES public.case_facts(id, case_id),
          FOREIGN KEY (document_id, case_id) REFERENCES public.documents(id, case_id),
          FOREIGN KEY (page_id, case_id) REFERENCES public.extracted_pages(id, case_id),
          CHECK ((source_kind = 'document_page')
                 = (document_id IS NOT NULL AND page_id IS NOT NULL AND page_no IS NOT NULL)),
          CHECK (source_kind = 'document_page' OR quote_check = 'not_applicable')
        )
        """
    )
    op.execute("CREATE INDEX ix_case_fact_sources_fact ON public.case_fact_sources (fact_id)")

    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_lawyer_read ON public.{table} "
            "FOR SELECT TO app_user USING (app.is_lawyer_member(case_id))"
        )
        op.execute(
            f"CREATE POLICY {table}_lawyer_insert ON public.{table} "
            "FOR INSERT TO app_user WITH CHECK (app.can_write_case(case_id))"
        )
    for table in ("ai_runs", "case_facts"):
        op.execute(
            f"CREATE POLICY {table}_lawyer_update ON public.{table} "
            "FOR UPDATE TO app_user USING (app.can_write_case(case_id)) WITH CHECK (app.can_write_case(case_id))"
        )

    op.execute(
        """
        CREATE VIEW public.case_facts_for_analysis WITH (security_invoker = true) AS
        SELECT * FROM public.case_facts
        WHERE is_current
          AND review_status <> 'lawyer_rejected'
          AND (statement_type = 'lawyer_entered' OR review_status = 'lawyer_reviewed')
        """
    )
    op.execute("GRANT SELECT ON public.case_facts_for_analysis TO app_user")
    op.execute("GRANT SELECT, INSERT ON public.ai_runs, public.case_facts, public.case_fact_sources TO app_user")
    op.execute(
        "GRANT UPDATE (status, error, attempts, model, tokens_in, tokens_out, started_at, finished_at) "
        "ON public.ai_runs TO app_user"
    )
    op.execute(
        "GRANT UPDATE (is_current, review_status, review_note, reviewed_by, reviewed_at) "
        "ON public.case_facts TO app_user"
    )
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute("DROP VIEW public.case_facts_for_analysis")
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE public.{table}")
    op.execute("RESET ROLE")
