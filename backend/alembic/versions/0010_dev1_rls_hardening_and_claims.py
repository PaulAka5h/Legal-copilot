"""Dev 1 RLS hardening: strategy grants and FKs, membership policy fix, claims schema.

Revision ID: 0010_dev1_rls_and_claims
Revises: 0009_phase6_strategy_engine
Create Date: 2026-11-19

1. Strategy tables (0009): grant app_user the minimum it needs. Content stays
   immutable: INSERT/SELECT only, plus column-level UPDATE for lifecycle fields.
   Add (case_id, organization_id) FKs to cases and keep scenario/comparison rows
   on the same case as their strategy.
2. case_members_create (0001): qualify the client-profile subquery. Unqualified
   ``organization_id``/``user_id`` resolved to client_profiles' own columns, so the
   check was a tautology and a case lawyer could grant client access to any user.
3. Claims & verification schema (database.md §9, Dev 1 per orchestration Phase 5):
   claims, claim_sources, verification_results with RLS, insert-only grants, and a
   deferred constraint trigger: a claim needs at least one source unless it is an
   assumption or a prediction. Links to Dev 2 tables that do not exist yet
   (analyses, ai_runs, document_chunks, legal_source_versions) are plain UUIDs;
   FKs follow when those tables land.

Local draft; not applied to any shared database.
"""

from alembic import op

revision = "0010_dev1_rls_and_claims"
down_revision = "0009_phase6_strategy_engine"
branch_labels = None
depends_on = None

STRATEGY_LIFECYCLE_COLUMNS = "status, is_current_strategy, approved_by, approved_at, updated_at"
CLAIM_TABLES = ("claims", "claim_sources", "verification_results")

CASE_MEMBERS_CREATE_FIXED = """
CREATE POLICY case_members_create ON public.case_members
FOR INSERT TO app_user
WITH CHECK (
  granted_by = app.current_user_id()
  AND (
    app.is_lawyer_member(case_id)
    OR (user_id = app.current_user_id()
      AND role = 'lead_lawyer'
      AND app.is_case_creator(case_id)
      AND app.is_org_member_user(organization_id, user_id)))
  AND (
    (role IN ('lead_lawyer','team_lawyer','assistant')
      AND app.is_org_member_user(organization_id, user_id))
    OR (role = 'client'
      AND EXISTS (
        SELECT 1 FROM public.client_profiles cp
        WHERE cp.id = case_members.client_profile_id
          AND cp.organization_id = case_members.organization_id
          AND cp.user_id = case_members.user_id)))
  AND (
    user_id = app.current_user_id()
    OR app.is_case_lead_lawyer(case_id)))
"""

# Original 0001 text, restored verbatim on downgrade.
CASE_MEMBERS_CREATE_ORIGINAL = """
CREATE POLICY case_members_create ON public.case_members
FOR INSERT TO app_user
WITH CHECK (
  granted_by = app.current_user_id()
  AND (
    app.is_lawyer_member(case_id)
    OR (user_id = app.current_user_id()
      AND role = 'lead_lawyer'
      AND app.is_case_creator(case_id)
      AND app.is_org_member_user(organization_id, user_id)))
  AND (
    (role IN ('lead_lawyer','team_lawyer','assistant')
      AND app.is_org_member_user(organization_id, user_id))
    OR (role = 'client'
      AND EXISTS (
        SELECT 1 FROM public.client_profiles cp
        WHERE cp.id = client_profile_id
          AND cp.organization_id = organization_id
          AND cp.user_id = user_id)))
  AND (
    user_id = app.current_user_id()
    OR app.is_case_lead_lawyer(case_id)))
"""


def _add_validated_fk(table: str, name: str, definition: str) -> None:
    op.execute(f"ALTER TABLE public.{table} ADD CONSTRAINT {name} {definition} NOT VALID")
    op.execute(f"ALTER TABLE public.{table} VALIDATE CONSTRAINT {name}")


def _strategy_hardening() -> None:
    op.execute("ALTER TABLE public.strategies ADD CONSTRAINT uq_strategies_id_case UNIQUE (id, case_id)")
    for table in ("strategies", "strategy_scenarios", "strategy_comparisons"):
        _add_validated_fk(
            table,
            f"fk_{table}_case_org",
            "FOREIGN KEY (case_id, organization_id) REFERENCES public.cases(id, organization_id)",
        )
    _add_validated_fk(
        "strategy_scenarios",
        "fk_strategy_scenarios_same_case",
        "FOREIGN KEY (strategy_id, case_id) REFERENCES public.strategies(id, case_id) ON DELETE CASCADE",
    )
    _add_validated_fk(
        "strategy_comparisons",
        "fk_strategy_comparisons_best_same_case",
        "FOREIGN KEY (best_supported_strategy_id, case_id) REFERENCES public.strategies(id, case_id)",
    )
    op.execute("GRANT SELECT, INSERT ON public.strategies TO app_user")
    op.execute(f"GRANT UPDATE ({STRATEGY_LIFECYCLE_COLUMNS}) ON public.strategies TO app_user")
    op.execute("GRANT SELECT, INSERT ON public.strategy_scenarios TO app_user")
    op.execute("GRANT SELECT, INSERT ON public.strategy_comparisons TO app_user")
    op.execute("GRANT UPDATE (review_status) ON public.strategy_comparisons TO app_user")


def _claims_schema() -> None:
    op.execute(
        """
        CREATE TABLE public.claims (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          case_id uuid NOT NULL,
          organization_id uuid NOT NULL,
          analysis_id uuid,
          strategy_id uuid,
          text text NOT NULL,
          claim_type text NOT NULL CHECK (claim_type IN (
            'fact_from_document','lawyer_entered','verified_record',
            'inference','assumption','prediction')),
          confidence_label text NOT NULL CHECK (confidence_label IN ('high','medium','low','unverified')),
          needs_lawyer_review boolean NOT NULL DEFAULT false,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_claims_id_case UNIQUE (id, case_id),
          CONSTRAINT fk_claims_case_org FOREIGN KEY (case_id, organization_id)
            REFERENCES public.cases(id, organization_id),
          CONSTRAINT fk_claims_strategy_same_case FOREIGN KEY (strategy_id, case_id)
            REFERENCES public.strategies(id, case_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_claims_case_analysis ON public.claims (case_id, analysis_id)")
    op.execute(
        """
        CREATE TABLE public.claim_sources (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          claim_id uuid NOT NULL,
          case_id uuid NOT NULL,
          organization_id uuid NOT NULL,
          source_kind text NOT NULL CHECK (source_kind IN (
            'document_chunk','hearing_update','lawyer_note','legal_source_version')),
          document_chunk_id uuid,
          hearing_update_id uuid,
          legal_source_version_id uuid,
          provision_label text,
          quote_start int,
          quote_end int,
          CHECK (
            (source_kind = 'document_chunk' AND document_chunk_id IS NOT NULL) OR
            (source_kind = 'hearing_update' AND hearing_update_id IS NOT NULL) OR
            (source_kind = 'legal_source_version' AND legal_source_version_id IS NOT NULL) OR
            (source_kind = 'lawyer_note')
          ),
          CONSTRAINT fk_claim_sources_claim_same_case FOREIGN KEY (claim_id, case_id)
            REFERENCES public.claims(id, case_id) ON DELETE CASCADE,
          CONSTRAINT fk_claim_sources_case_org FOREIGN KEY (case_id, organization_id)
            REFERENCES public.cases(id, organization_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_claim_sources_claim ON public.claim_sources (claim_id)")
    op.execute(
        """
        CREATE TABLE public.verification_results (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          case_id uuid NOT NULL,
          organization_id uuid NOT NULL,
          claim_id uuid NOT NULL,
          verdict text NOT NULL CHECK (verdict IN (
            'supported','partially_supported','unsupported','cannot_verify')),
          reasons text,
          statute_status_checked boolean NOT NULL DEFAULT false,
          ai_run_id uuid,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_verification_claim_same_case FOREIGN KEY (claim_id, case_id)
            REFERENCES public.claims(id, case_id),
          CONSTRAINT fk_verification_case_org FOREIGN KEY (case_id, organization_id)
            REFERENCES public.cases(id, organization_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_verification_results_claim ON public.verification_results (claim_id)")

    op.execute(
        """
        CREATE FUNCTION app.check_claim_has_source() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $$
        BEGIN
          IF NEW.claim_type IN ('assumption', 'prediction') THEN
            RETURN NULL;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM public.claim_sources s WHERE s.claim_id = NEW.id) THEN
            RAISE EXCEPTION 'claim requires at least one source (claim_type %)', NEW.claim_type
              USING ERRCODE = '23514';
          END IF;
          RETURN NULL;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER claims_require_source
        AFTER INSERT ON public.claims
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION app.check_claim_has_source()
        """
    )

    for table in CLAIM_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY lawyer_case_access ON public.{table}
            FOR ALL TO app_user
            USING (app.is_lawyer_member(case_id))
            WITH CHECK (app.is_lawyer_member(case_id))
            """
        )
        op.execute(f"GRANT SELECT, INSERT ON public.{table} TO app_user")


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    _strategy_hardening()
    op.execute("DROP POLICY case_members_create ON public.case_members")
    op.execute(CASE_MEMBERS_CREATE_FIXED)
    _claims_schema()
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    for table in reversed(CLAIM_TABLES):
        op.execute(f"DROP TABLE public.{table}")
    op.execute("DROP FUNCTION app.check_claim_has_source()")

    op.execute("DROP POLICY case_members_create ON public.case_members")
    op.execute(CASE_MEMBERS_CREATE_ORIGINAL)

    op.execute("REVOKE UPDATE (review_status) ON public.strategy_comparisons FROM app_user")
    op.execute("REVOKE SELECT, INSERT ON public.strategy_comparisons FROM app_user")
    op.execute("REVOKE SELECT, INSERT ON public.strategy_scenarios FROM app_user")
    op.execute(f"REVOKE UPDATE ({STRATEGY_LIFECYCLE_COLUMNS}) ON public.strategies FROM app_user")
    op.execute("REVOKE SELECT, INSERT ON public.strategies FROM app_user")
    op.execute("ALTER TABLE public.strategy_comparisons DROP CONSTRAINT fk_strategy_comparisons_best_same_case")
    op.execute("ALTER TABLE public.strategy_scenarios DROP CONSTRAINT fk_strategy_scenarios_same_case")
    for table in ("strategies", "strategy_scenarios", "strategy_comparisons"):
        op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT fk_{table}_case_org")
    op.execute("ALTER TABLE public.strategies DROP CONSTRAINT uq_strategies_id_case")
    op.execute("RESET ROLE")
