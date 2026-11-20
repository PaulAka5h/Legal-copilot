"""Hearing reassessment (Step F).

- app_user may read and insert hearing_updates (0010 created the table with a
  lawyer-member policy but no grants). Updates are append-only: a correction is
  a new version with supersedes_id.
- case_reassessments: one immutable row per hearing update, linking the update,
  the analysis and strategy tree versions before and after, the diff (changes,
  closed and new options, tasks, an AI-suggested next date as a draft only), and
  the draft client update it created in client_visible_updates (published only
  by a lawyer through the existing client-update flow). No client policy.

Revision ID: 0018_hearing_reassessment
Revises: 0017_strategy_trees
Create Date: 2026-11-20
"""

from alembic import op

revision = "0018_hearing_reassessment"
down_revision = "0017_strategy_trees"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute("GRANT SELECT, INSERT ON public.hearing_updates TO app_user")
    op.execute(
        """
        CREATE TABLE public.case_reassessments (
          id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          case_id              uuid NOT NULL REFERENCES public.cases(id),
          organization_id      uuid NOT NULL REFERENCES public.organizations(id),
          hearing_id           uuid NOT NULL REFERENCES public.hearings(id),
          hearing_update_id    uuid NOT NULL REFERENCES public.hearing_updates(id),
          previous_analysis_id uuid,
          analysis_id          uuid NOT NULL,
          previous_tree_id     uuid,
          tree_id              uuid,
          diff                 jsonb NOT NULL CHECK (jsonb_typeof(diff) = 'object'),
          client_update_id     uuid REFERENCES public.client_visible_updates(id),
          created_by           uuid NOT NULL REFERENCES public.users(id),
          created_at           timestamptz NOT NULL DEFAULT now(),
          FOREIGN KEY (analysis_id, case_id) REFERENCES public.case_analyses(id, case_id),
          FOREIGN KEY (previous_analysis_id, case_id) REFERENCES public.case_analyses(id, case_id),
          FOREIGN KEY (tree_id, case_id) REFERENCES public.strategy_trees(id, case_id),
          FOREIGN KEY (previous_tree_id, case_id) REFERENCES public.strategy_trees(id, case_id),
          UNIQUE (hearing_update_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_case_reassessments_case ON public.case_reassessments (case_id, created_at DESC)")
    op.execute("ALTER TABLE public.case_reassessments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.case_reassessments FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY case_reassessments_lawyer_read ON public.case_reassessments "
        "FOR SELECT TO app_user USING (app.is_lawyer_member(case_id))"
    )
    op.execute(
        "CREATE POLICY case_reassessments_lawyer_insert ON public.case_reassessments "
        "FOR INSERT TO app_user WITH CHECK (app.can_write_case(case_id))"
    )
    op.execute("GRANT SELECT, INSERT ON public.case_reassessments TO app_user")
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute("DROP TABLE public.case_reassessments")
    op.execute("REVOKE SELECT, INSERT ON public.hearing_updates FROM app_user")
    op.execute("RESET ROLE")
