"""Phase 6: Chess-Inspired Legal Strategy Engine tables, indexes, constraints, and RLS.

Revision ID: 0009_phase6_strategy_engine
Revises: 0008_b13_client_case_read
Create Date: 2026-11-19

Amended 2026-11-19 by Backend Dev 1 (integration fix, authorized by the project
owner): policies now use app.is_lawyer_member(case_id); the original referenced
app.has_case_access, which no revision defines. The client SELECT policy on
strategies was removed (Legal Product Rule 8). Local draft; not applied to any
shared database.
"""

from alembic import op

revision = "0009_phase6_strategy_engine"
down_revision = "0008_b13_client_case_read"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE app_owner")

    # 1. Strategies Table
    op.execute(
        """
        CREATE TABLE public.strategies (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          case_id uuid NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
          organization_id uuid NOT NULL,
          lineage_id uuid NOT NULL,
          version int NOT NULL,
          supersedes_id uuid REFERENCES public.strategies(id),
          name text NOT NULL,
          legal_basis text NOT NULL,
          details jsonb NOT NULL DEFAULT '{}'::jsonb,
          origin text NOT NULL CHECK (origin IN ('ai', 'ai_mock', 'lawyer')),
          status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'proposed', 'approved', 'current', 'rejected', 'superseded')),
          is_current_strategy boolean NOT NULL DEFAULT false,
          is_mock boolean NOT NULL DEFAULT false,
          supporting_facts jsonb NOT NULL DEFAULT '[]'::jsonb,
          source_references jsonb NOT NULL DEFAULT '[]'::jsonb,
          precedent_references jsonb NOT NULL DEFAULT '[]'::jsonb,
          rubric_evaluation jsonb NOT NULL DEFAULT '{}'::jsonb,
          created_by uuid REFERENCES public.users(id),
          approved_by uuid REFERENCES public.users(id),
          approved_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE (lineage_id, version)
        );
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX ix_strategies_current_per_case
        ON public.strategies (case_id)
        WHERE is_current_strategy AND status <> 'superseded';
        """
    )
    op.execute("CREATE INDEX ix_strategies_case_version ON public.strategies (case_id, version DESC);")

    # 2. Strategy Scenarios Table (2-ply scenario tree)
    op.execute(
        """
        CREATE TABLE public.strategy_scenarios (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          case_id uuid NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
          organization_id uuid NOT NULL,
          strategy_id uuid NOT NULL REFERENCES public.strategies(id) ON DELETE CASCADE,
          parent_id uuid REFERENCES public.strategy_scenarios(id) ON DELETE CASCADE,
          depth int NOT NULL DEFAULT 0,
          node_type text NOT NULL CHECK (node_type IN ('strategy_root', 'opposing_argument', 'our_response')),
          text text NOT NULL,
          legal_ground text,
          plausibility text CHECK (plausibility IN ('likely', 'possible', 'unlikely')),
          pruned boolean NOT NULL DEFAULT false,
          prune_reason text,
          residual_risk jsonb NOT NULL DEFAULT '{}'::jsonb,
          supporting_authorities jsonb NOT NULL DEFAULT '[]'::jsonb,
          position int NOT NULL DEFAULT 0,
          created_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute("CREATE INDEX ix_strategy_scenarios_tree ON public.strategy_scenarios (strategy_id, parent_id);")

    # 3. Strategy Comparisons Table (5-dimension qualitative rubric matrix)
    op.execute(
        """
        CREATE TABLE public.strategy_comparisons (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          case_id uuid NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
          organization_id uuid NOT NULL,
          version int NOT NULL,
          supersedes_id uuid REFERENCES public.strategy_comparisons(id),
          ratings jsonb NOT NULL DEFAULT '{}'::jsonb,
          best_supported_strategy_id uuid REFERENCES public.strategies(id),
          recommendation text CHECK (recommendation IN ('maintain', 'review', 'change_suggested', 'initial')),
          recommendation_reason text,
          trade_offs_analysis text,
          uncertainties jsonb NOT NULL DEFAULT '[]'::jsonb,
          review_status text NOT NULL DEFAULT 'draft' CHECK (review_status IN ('draft', 'lawyer_reviewed', 'lawyer_rejected')),
          created_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE (case_id, version)
        );
        """
    )
    op.execute("CREATE INDEX ix_strategy_comparisons_case ON public.strategy_comparisons (case_id, version DESC);")

    # 4. Row Level Security Setup
    for tbl in ("strategies", "strategy_scenarios", "strategy_comparisons"):
        op.execute(f"ALTER TABLE public.{tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE public.{tbl} FORCE ROW LEVEL SECURITY;")

    # Lawyer management policies
    op.execute(
        """
        CREATE POLICY strategies_lawyer_manage ON public.strategies
        FOR ALL TO app_user
        USING (app.is_lawyer_member(case_id))
        WITH CHECK (app.is_lawyer_member(case_id));
        """
    )
    op.execute(
        """
        CREATE POLICY strategy_scenarios_lawyer_manage ON public.strategy_scenarios
        FOR ALL TO app_user
        USING (app.is_lawyer_member(case_id))
        WITH CHECK (app.is_lawyer_member(case_id));
        """
    )
    op.execute(
        """
        CREATE POLICY strategy_comparisons_lawyer_manage ON public.strategy_comparisons
        FOR ALL TO app_user
        USING (app.is_lawyer_member(case_id))
        WITH CHECK (app.is_lawyer_member(case_id));
        """
    )

    # No client policy: strategies are lawyer-side tables (database.md §12.1,
    # Legal Product Rule 8). Clients see strategy outcomes only through
    # lawyer-published client_visible_updates.

    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")

    op.execute("DROP POLICY IF EXISTS strategy_comparisons_lawyer_manage ON public.strategy_comparisons;")
    op.execute("DROP POLICY IF EXISTS strategy_scenarios_lawyer_manage ON public.strategy_scenarios;")
    op.execute("DROP POLICY IF EXISTS strategies_lawyer_manage ON public.strategies;")

    op.execute("DROP TABLE IF EXISTS public.strategy_comparisons CASCADE;")
    op.execute("DROP TABLE IF EXISTS public.strategy_scenarios CASCADE;")
    op.execute("DROP TABLE IF EXISTS public.strategies CASCADE;")

    op.execute("RESET ROLE")
