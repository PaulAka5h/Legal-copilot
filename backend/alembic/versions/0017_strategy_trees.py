"""Versioned strategy game trees (Step E).

strategy_trees: one immutable row per tree version, built from one analysis
version (composite FK keeps it in the same case). The tree (3 plies: us ->
opponent/court -> us, at most 4 moves then 3 branches per node) and its
verification summary are stored as jsonb. No UPDATE/DELETE grants (Rule 6).
Lawyer members read; inserts need app.can_write_case; no client policy.

Revision ID: 0017_strategy_trees
Revises: 0016_case_analyses
Create Date: 2026-11-20
"""

from alembic import op

revision = "0017_strategy_trees"
down_revision = "0016_case_analyses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        """
        CREATE TABLE public.strategy_trees (
          id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          case_id         uuid NOT NULL REFERENCES public.cases(id),
          organization_id uuid NOT NULL REFERENCES public.organizations(id),
          version         int NOT NULL CHECK (version >= 1),
          supersedes_id   uuid REFERENCES public.strategy_trees(id),
          analysis_id     uuid NOT NULL,
          fact_set_hash   text NOT NULL CHECK (length(fact_set_hash) = 64),
          trigger         text NOT NULL CHECK (trigger IN ('manual','hearing_update')),
          trigger_ref_id  uuid,
          status          text NOT NULL CHECK (status IN ('succeeded','insufficient_information')),
          provider        text NOT NULL,
          origin          text NOT NULL CHECK (origin IN ('ai','ai_mock')),
          tree            jsonb NOT NULL CHECK (jsonb_typeof(tree) = 'object'),
          ai_run_id       uuid,
          created_by      uuid NOT NULL REFERENCES public.users(id),
          created_at      timestamptz NOT NULL DEFAULT now(),
          FOREIGN KEY (analysis_id, case_id) REFERENCES public.case_analyses(id, case_id),
          FOREIGN KEY (ai_run_id, case_id) REFERENCES public.ai_runs(id, case_id),
          UNIQUE (case_id, version),
          UNIQUE (id, case_id),
          CHECK ((version = 1) = (supersedes_id IS NULL))
        )
        """
    )
    op.execute("ALTER TABLE public.strategy_trees ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.strategy_trees FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY strategy_trees_lawyer_read ON public.strategy_trees "
        "FOR SELECT TO app_user USING (app.is_lawyer_member(case_id))"
    )
    op.execute(
        "CREATE POLICY strategy_trees_lawyer_insert ON public.strategy_trees "
        "FOR INSERT TO app_user WITH CHECK (app.can_write_case(case_id))"
    )
    op.execute("GRANT SELECT, INSERT ON public.strategy_trees TO app_user")
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute("DROP TABLE public.strategy_trees")
    op.execute("RESET ROLE")
