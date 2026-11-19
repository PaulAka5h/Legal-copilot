"""Phase 7: Hearings updates, continuous strategy reassessments, diffs, and RLS.

Revision ID: 0010_phase7_hearings
Revises: 0009_phase6_strategy_engine
Create Date: 2026-11-19
"""

from alembic import op

revision = "0010_phase7_hearings"
down_revision = "0009_phase6_strategy_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE app_owner")

    # 1. Hearing Updates Table (versioned, append-only with supersedes_id)
    op.execute(
        """
        CREATE TABLE public.hearing_updates (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          case_id uuid NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
          organization_id uuid NOT NULL,
          hearing_id uuid NOT NULL REFERENCES public.hearings(id) ON DELETE CASCADE,
          author_id uuid NOT NULL REFERENCES public.users(id),
          happened text NOT NULL,
          our_arguments text,
          opposing_arguments text,
          judge_remarks text,
          new_evidence text,
          objections_procedural text,
          orders_directions text,
          next_hearing_date timestamptz,
          next_hearing_confirmed boolean NOT NULL DEFAULT false,
          follow_ups text,
          source_label text NOT NULL DEFAULT 'lawyer_entered'
            CHECK (source_label IN ('lawyer_entered', 'verified_court_record')),
          version int NOT NULL DEFAULT 1,
          supersedes_id uuid REFERENCES public.hearing_updates(id),
          created_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute("CREATE INDEX ix_hearing_updates_hearing_version ON public.hearing_updates (hearing_id, version DESC);")
    op.execute("CREATE INDEX ix_hearing_updates_case_created ON public.hearing_updates (case_id, created_at DESC);")

    # 2. Hearing Reassessments Table (Strategy diffing, posture recommendation, client draft)
    op.execute(
        """
        CREATE TABLE public.hearing_reassessments (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          case_id uuid NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
          hearing_id uuid NOT NULL REFERENCES public.hearings(id) ON DELETE CASCADE,
          hearing_update_id uuid NOT NULL REFERENCES public.hearing_updates(id) ON DELETE CASCADE,
          organization_id uuid NOT NULL,
          previous_strategy_id uuid REFERENCES public.strategies(id),
          reassessed_strategy_id uuid REFERENCES public.strategies(id),
          recommendation text NOT NULL CHECK (recommendation IN ('maintain', 'review', 'change_suggested')),
          recommendation_reason text NOT NULL,
          tree_diff jsonb NOT NULL DEFAULT '[]'::jsonb,
          rubric_diff jsonb NOT NULL DEFAULT '[]'::jsonb,
          new_risks jsonb NOT NULL DEFAULT '[]'::jsonb,
          new_evidence_needs jsonb NOT NULL DEFAULT '[]'::jsonb,
          draft_client_update jsonb NOT NULL DEFAULT '{}'::jsonb,
          review_status text NOT NULL DEFAULT 'draft' CHECK (review_status IN ('draft', 'lawyer_reviewed', 'lawyer_rejected')),
          created_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute("CREATE INDEX ix_hearing_reassessments_hearing ON public.hearing_reassessments (hearing_id, created_at DESC);")
    op.execute("CREATE INDEX ix_hearing_reassessments_case ON public.hearing_reassessments (case_id);")

    # 3. Row-Level Security (RLS)
    op.execute("ALTER TABLE public.hearing_updates ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.hearing_updates FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.hearing_reassessments ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.hearing_reassessments FORCE ROW LEVEL SECURITY;")

    # Lawyer case access policy
    op.execute(
        """
        CREATE POLICY hearing_updates_lawyer_manage ON public.hearing_updates
        FOR ALL TO app_user
        USING (app.is_lawyer_member(case_id))
        WITH CHECK (app.is_lawyer_member(case_id));
        """
    )
    op.execute(
        """
        CREATE POLICY hearing_reassessments_lawyer_manage ON public.hearing_reassessments
        FOR ALL TO app_user
        USING (app.is_lawyer_member(case_id))
        WITH CHECK (app.is_lawyer_member(case_id));
        """
    )

    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")

    op.execute("DROP POLICY IF EXISTS hearing_reassessments_lawyer_manage ON public.hearing_reassessments;")
    op.execute("DROP POLICY IF EXISTS hearing_updates_lawyer_manage ON public.hearing_updates;")

    op.execute("DROP TABLE IF EXISTS public.hearing_reassessments CASCADE;")
    op.execute("DROP TABLE IF EXISTS public.hearing_updates CASCADE;")

    op.execute("RESET ROLE")
