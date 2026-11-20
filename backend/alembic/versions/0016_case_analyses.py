"""Versioned case analyses (Step D).

case_analyses: one immutable row per analysis version. Records the confirmed
fact set it used (fact_set_hash, fact version ids), the incident date, provider
and origin, the verified result (ViolationFinding list, retrieval provenance,
verification summary), and the abstain outcome. No UPDATE or DELETE grant:
versions are never overwritten (Rule 6). Lawyer members read; inserts require
app.can_write_case. No client policy.

Revision ID: 0016_case_analyses
Revises: 0015_processing_recovery
Create Date: 2026-11-20
"""

from alembic import op

revision = "0016_case_analyses"
down_revision = "0015_processing_recovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        """
        CREATE TABLE public.case_analyses (
          id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          case_id         uuid NOT NULL REFERENCES public.cases(id),
          organization_id uuid NOT NULL REFERENCES public.organizations(id),
          version         int NOT NULL CHECK (version >= 1),
          supersedes_id   uuid REFERENCES public.case_analyses(id),
          trigger         text NOT NULL CHECK (trigger IN ('manual','hearing_update')),
          trigger_ref_id  uuid,
          status          text NOT NULL CHECK (status IN ('succeeded','insufficient_information','failed')),
          fact_set_hash   text NOT NULL CHECK (length(fact_set_hash) = 64),
          fact_ids        uuid[] NOT NULL,
          incident_date   date,
          language        text CHECK (language IN ('bn','en')),
          provider        text NOT NULL,
          origin          text NOT NULL CHECK (origin IN ('ai','ai_mock')),
          result          jsonb NOT NULL CHECK (jsonb_typeof(result) = 'object'),
          ai_run_id       uuid,
          created_by      uuid NOT NULL REFERENCES public.users(id),
          created_at      timestamptz NOT NULL DEFAULT now(),
          FOREIGN KEY (ai_run_id, case_id) REFERENCES public.ai_runs(id, case_id),
          UNIQUE (case_id, version),
          UNIQUE (id, case_id),
          CHECK ((version = 1) = (supersedes_id IS NULL))
        )
        """
    )
    op.execute("ALTER TABLE public.case_analyses ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.case_analyses FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY case_analyses_lawyer_read ON public.case_analyses "
        "FOR SELECT TO app_user USING (app.is_lawyer_member(case_id))"
    )
    op.execute(
        "CREATE POLICY case_analyses_lawyer_insert ON public.case_analyses "
        "FOR INSERT TO app_user WITH CHECK (app.can_write_case(case_id))"
    )
    op.execute("GRANT SELECT, INSERT ON public.case_analyses TO app_user")
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute("DROP TABLE public.case_analyses")
    op.execute("RESET ROLE")
