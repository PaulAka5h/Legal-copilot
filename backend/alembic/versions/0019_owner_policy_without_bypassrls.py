"""Owner-only RLS policy where app_owner could not be given BYPASSRLS (Neon).

The SECURITY DEFINER helpers in schema `app` run as app_owner and read tables
that FORCE row level security; they rely on app_owner bypassing RLS. Managed
Postgres (Neon) may not let the bootstrap role grant BYPASSRLS (see 0001). There,
each RLS table gets one extra PERMISSIVE policy `app_owner_unrestricted ... TO
app_owner USING (true)`: app_owner sees what BYPASSRLS would have shown it, and
nothing changes for app_user or app_admin_ingest (their policies are untouched,
RLS stays enabled and forced). Where app_owner already has BYPASSRLS (local
Compose, any superuser bootstrap) this is a no-op.

Later migrations that add an RLS table call `SELECT app.ensure_owner_policies()`
as app_owner after creating it.
"""

from alembic import op

revision = "0019_owner_policy_no_bypass"
down_revision = "0018_hearing_reassessment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        """
        CREATE FUNCTION app.ensure_owner_policies() RETURNS integer
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
          t record;
          created integer := 0;
        BEGIN
          IF (SELECT rolbypassrls FROM pg_roles WHERE rolname = 'app_owner') THEN
            RETURN 0;
          END IF;
          FOR t IN
            SELECT c.relname
            FROM pg_class c
            WHERE c.relnamespace = 'public'::regnamespace
              AND c.relkind IN ('r', 'p')
              AND c.relrowsecurity
              AND pg_get_userbyid(c.relowner) = 'app_owner'
              AND NOT EXISTS (
                SELECT 1 FROM pg_policies p
                WHERE p.schemaname = 'public' AND p.tablename = c.relname
                  AND p.policyname = 'app_owner_unrestricted')
          LOOP
            EXECUTE format(
              'CREATE POLICY app_owner_unrestricted ON public.%I AS PERMISSIVE '
              'FOR ALL TO app_owner USING (true) WITH CHECK (true)', t.relname);
            created := created + 1;
          END LOOP;
          RETURN created;
        END
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION app.ensure_owner_policies() FROM PUBLIC")
    op.execute("SELECT app.ensure_owner_policies()")
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        """
        DO $$
        DECLARE t record;
        BEGIN
          FOR t IN SELECT tablename FROM pg_policies
                   WHERE schemaname = 'public' AND policyname = 'app_owner_unrestricted'
          LOOP
            EXECUTE format('DROP POLICY app_owner_unrestricted ON public.%I', t.tablename);
          END LOOP;
        END
        $$
        """
    )
    op.execute("DROP FUNCTION app.ensure_owner_policies()")
    op.execute("RESET ROLE")
