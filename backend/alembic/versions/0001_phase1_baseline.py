"""Phase 1 identity, tenancy, and case baseline."""

from alembic import op

revision = "0001_phase1_baseline"
down_revision = None
branch_labels = None
depends_on = None

TABLES = (
    "case_invitations",
    "case_members",
    "case_stages",
    "cases",
    "password_reset_tokens",
    "sessions",
    "client_profiles",
    "lawyer_profiles",
    "organization_members",
    "organizations",
    "users",
)


# Role attributes, applied one at a time and only where they differ. Managed
# Postgres (Neon) runs the bootstrap as a non-superuser with CREATEROLE, which may
# not even *mention* SUPERUSER, REPLICATION or BYPASSRLS in ALTER ROLE. Final state
# on a superuser bootstrap is unchanged. Safety rules:
# - app_user and app_admin_ingest must end NOSUPERUSER, NOBYPASSRLS, NOREPLICATION;
#   if that cannot be achieved the migration fails (never weaker isolation).
# - app_owner gets BYPASSRLS when the bootstrap role may grant it. Otherwise it stays
#   NOBYPASSRLS (stricter: FORCE RLS then applies to the owner too) with a WARNING.
# - A non-superuser bootstrap role is given SET (not INHERIT) on app_owner so the
#   SET ROLE / OWNER TO below work; with CREATEROLE it already administers the role.
_ROLE_ATTRIBUTES = """
DO $$
DECLARE
  r record;
  wanted_bypass boolean;
BEGIN
  FOR r IN
    SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolinherit, rolcanlogin,
           rolreplication, rolbypassrls
    FROM pg_roles WHERE rolname IN ('app_owner', 'app_user', 'app_admin_ingest')
  LOOP
    IF NOT r.rolcanlogin THEN EXECUTE format('ALTER ROLE %I LOGIN', r.rolname); END IF;
    IF r.rolcreatedb THEN EXECUTE format('ALTER ROLE %I NOCREATEDB', r.rolname); END IF;
    IF r.rolcreaterole THEN EXECUTE format('ALTER ROLE %I NOCREATEROLE', r.rolname); END IF;
    IF r.rolinherit THEN EXECUTE format('ALTER ROLE %I NOINHERIT', r.rolname); END IF;
    IF r.rolsuper THEN EXECUTE format('ALTER ROLE %I NOSUPERUSER', r.rolname); END IF;
    IF r.rolreplication THEN EXECUTE format('ALTER ROLE %I NOREPLICATION', r.rolname); END IF;
    wanted_bypass := r.rolname = 'app_owner';
    IF r.rolbypassrls AND NOT wanted_bypass THEN
      EXECUTE format('ALTER ROLE %I NOBYPASSRLS', r.rolname);
    ELSIF wanted_bypass AND NOT r.rolbypassrls THEN
      BEGIN
        ALTER ROLE app_owner BYPASSRLS;
      EXCEPTION WHEN insufficient_privilege THEN
        RAISE WARNING 'app_owner left NOBYPASSRLS: bootstrap role may not grant BYPASSRLS '
          '(managed Postgres). Row level security stays forced for the owner as well.';
      END;
    END IF;
  END LOOP;

  IF EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname IN ('app_owner', 'app_user', 'app_admin_ingest')
      AND (rolsuper OR rolreplication OR (rolbypassrls AND rolname <> 'app_owner'))
  ) THEN
    RAISE EXCEPTION 'runtime roles must be NOSUPERUSER NOREPLICATION and app_user/'
      'app_admin_ingest NOBYPASSRLS';
  END IF;

  IF NOT (SELECT rolsuper FROM pg_roles WHERE rolname = current_user)
     AND NOT pg_has_role(current_user, 'app_owner', 'SET') THEN
    EXECUTE format('GRANT app_owner TO %I WITH INHERIT FALSE, SET TRUE', current_user);
  END IF;
END
$$
"""


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_owner') THEN
            CREATE ROLE app_owner LOGIN;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            CREATE ROLE app_user LOGIN;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_admin_ingest') THEN
            CREATE ROLE app_admin_ingest LOGIN;
          END IF;
        END
        $$
        """
    )
    op.execute(_ROLE_ATTRIBUTES)
    for extension in ("vector", "pg_trgm", "citext"):
        op.execute(f"CREATE EXTENSION IF NOT EXISTS {extension}")
    op.execute("CREATE SCHEMA IF NOT EXISTS app AUTHORIZATION app_owner")
    op.execute("ALTER SCHEMA app OWNER TO app_owner")
    op.execute("GRANT USAGE, CREATE ON SCHEMA public TO app_owner")
    op.execute("GRANT USAGE ON SCHEMA public TO app_user")
    op.execute("SET ROLE app_owner")
    # As the schema owner, so a non-superuser bootstrap (Neon) may run them too.
    op.execute("GRANT USAGE ON SCHEMA app TO app_user")
    op.execute("REVOKE ALL ON SCHEMA app FROM PUBLIC")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA app "
        "REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC"
    )

    _create_tables()
    _create_functions()
    _create_policies()
    _grant_runtime_access()

    op.execute("RESET ROLE")
    op.execute(
        """
        DO $$
        BEGIN
          IF to_regclass('public.alembic_version') IS NOT NULL THEN
            ALTER TABLE public.alembic_version OWNER TO app_owner;
            -- A non-superuser bootstrap role (Neon) still has to record the
            -- remaining bootstrap revisions; grant it only this table.
            IF NOT (SELECT rolsuper FROM pg_roles WHERE rolname = current_user) THEN
              EXECUTE format(
                'SET LOCAL ROLE app_owner; '
                'GRANT SELECT, INSERT, UPDATE, DELETE ON public.alembic_version TO %I',
                current_user);
              RESET ROLE;
            END IF;
          END IF;
        END
        $$
        """
    )


def _create_tables() -> None:
    statements = (
        """
        CREATE TABLE public.users (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          email citext NOT NULL UNIQUE,
          password_hash text,
          role text NOT NULL CHECK (role IN ('lawyer','client','admin')),
          status text NOT NULL DEFAULT 'active'
            CHECK (status IN ('invited','active','suspended','deactivated')),
          full_name text NOT NULL,
          phone text,
          preferred_language text NOT NULL DEFAULT 'en'
            CHECK (preferred_language IN ('en','bn')),
          mfa_secret_enc bytea,
          mfa_enabled boolean NOT NULL DEFAULT false,
          failed_logins integer NOT NULL DEFAULT 0,
          locked_until timestamptz,
          last_login_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE public.organizations (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          name text NOT NULL,
          kind text NOT NULL DEFAULT 'individual'
            CHECK (kind IN ('individual','chamber','firm')),
          created_by uuid NOT NULL REFERENCES public.users(id),
          created_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE public.organization_members (
          organization_id uuid NOT NULL REFERENCES public.organizations(id),
          user_id uuid NOT NULL REFERENCES public.users(id),
          org_role text NOT NULL CHECK (org_role IN ('owner','lawyer','assistant')),
          status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','removed')),
          PRIMARY KEY (organization_id, user_id)
        )
        """,
        """
        CREATE TABLE public.lawyer_profiles (
          user_id uuid PRIMARY KEY REFERENCES public.users(id),
          bar_enrollment_no text,
          practice_areas text[],
          courts text[],
          chamber_name text
        )
        """,
        """
        CREATE TABLE public.client_profiles (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          organization_id uuid NOT NULL REFERENCES public.organizations(id),
          user_id uuid UNIQUE REFERENCES public.users(id),
          display_name text NOT NULL,
          email citext,
          phone text,
          address text,
          national_id_enc bytea,
          internal_notes text,
          created_by uuid NOT NULL REFERENCES public.users(id),
          created_at timestamptz NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE public.sessions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id uuid NOT NULL REFERENCES public.users(id),
          token_hash bytea NOT NULL UNIQUE,
          created_at timestamptz NOT NULL DEFAULT now(),
          last_seen_at timestamptz NOT NULL DEFAULT now(),
          expires_at timestamptz NOT NULL,
          revoked_at timestamptz,
          ip inet,
          user_agent text
        )
        """,
        """
        CREATE TABLE public.password_reset_tokens (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id uuid NOT NULL REFERENCES public.users(id),
          token_hash bytea NOT NULL UNIQUE,
          expires_at timestamptz NOT NULL,
          used_at timestamptz
        )
        """,
        """
        CREATE TABLE public.cases (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          organization_id uuid NOT NULL REFERENCES public.organizations(id),
          reference_no text NOT NULL,
          title text NOT NULL,
          case_type text NOT NULL,
          workflow_template_id uuid,
          court text,
          court_case_no text,
          jurisdiction text,
          opposing_party text,
          description text,
          internal_notes text,
          client_objectives text,
          status text NOT NULL DEFAULT 'open'
            CHECK (status IN ('draft','open','on_hold','closed')),
          current_stage text,
          key_dates jsonb NOT NULL DEFAULT CAST('{}' AS jsonb),
          closed_at timestamptz,
          closed_by uuid REFERENCES public.users(id),
          retention_until date,
          created_by uuid NOT NULL REFERENCES public.users(id),
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE (organization_id, reference_no),
          UNIQUE (id, organization_id)
        )
        """,
        """
        CREATE TABLE public.case_stages (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          case_id uuid NOT NULL REFERENCES public.cases(id),
          organization_id uuid NOT NULL,
          position integer NOT NULL,
          name text NOT NULL,
          client_label text,
          status text NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending','current','done','skipped')),
          UNIQUE (case_id, position),
          CONSTRAINT fk_case_stages_case_org
            FOREIGN KEY (case_id, organization_id)
            REFERENCES public.cases(id, organization_id)
        )
        """,
        """
        CREATE TABLE public.case_members (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          case_id uuid NOT NULL REFERENCES public.cases(id),
          organization_id uuid NOT NULL,
          user_id uuid NOT NULL REFERENCES public.users(id),
          client_profile_id uuid REFERENCES public.client_profiles(id),
          role text NOT NULL
            CHECK (role IN ('lead_lawyer','team_lawyer','assistant','client')),
          permissions jsonb NOT NULL DEFAULT CAST('{}' AS jsonb),
          status text NOT NULL DEFAULT 'active'
            CHECK (status IN ('active','read_only','revoked')),
          granted_by uuid NOT NULL REFERENCES public.users(id),
          granted_at timestamptz NOT NULL DEFAULT now(),
          revoked_at timestamptz,
          UNIQUE (case_id, user_id),
          CHECK ((role = 'client') = (client_profile_id IS NOT NULL)),
          CONSTRAINT fk_case_members_case_org
            FOREIGN KEY (case_id, organization_id)
            REFERENCES public.cases(id, organization_id)
        )
        """,
        """
        CREATE TABLE public.case_invitations (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          case_id uuid NOT NULL REFERENCES public.cases(id),
          organization_id uuid NOT NULL,
          client_profile_id uuid NOT NULL REFERENCES public.client_profiles(id),
          email citext NOT NULL,
          client_reference text NOT NULL,
          token_hash bytea NOT NULL UNIQUE,
          expires_at timestamptz NOT NULL,
          accepted_at timestamptz,
          revoked_at timestamptz,
          created_by uuid NOT NULL REFERENCES public.users(id),
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT fk_case_invitations_case_org
            FOREIGN KEY (case_id, organization_id)
            REFERENCES public.cases(id, organization_id)
        )
        """,
    )
    for statement in statements:
        op.execute(statement)

    op.execute(
        "CREATE INDEX ix_client_profiles_organization_id "
        "ON public.client_profiles (organization_id)"
    )
    op.execute(
        "CREATE INDEX ix_sessions_user_active ON public.sessions (user_id) "
        "WHERE revoked_at IS NULL"
    )
    op.execute(
        "CREATE INDEX ix_cases_organization_status "
        "ON public.cases (organization_id, status)"
    )
    op.execute(
        "CREATE INDEX ix_case_members_user_status "
        "ON public.case_members (user_id, status)"
    )


def _create_functions() -> None:
    statements = (
        """
        CREATE FUNCTION app.current_user_id() RETURNS uuid
        LANGUAGE sql STABLE
        AS $$
          SELECT CAST(NULLIF(current_setting('app.current_user_id', true), '') AS uuid)
        $$
        """,
        """
        CREATE FUNCTION app.is_org_member(p_organization uuid) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM public.organization_members m
            WHERE m.organization_id = p_organization
              AND m.user_id = app.current_user_id()
              AND m.status = 'active')
        $$
        """,
        """
        CREATE FUNCTION app.is_org_member_user(
          p_organization uuid, p_user uuid) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM public.organization_members m
            JOIN public.users u ON u.id = m.user_id
            WHERE m.organization_id = p_organization
              AND m.user_id = p_user
              AND m.status = 'active'
              AND u.role = 'lawyer'
              AND u.status = 'active'
              AND (p_user = app.current_user_id()
                OR app.is_org_member(p_organization)))
        $$
        """,
        """
        CREATE FUNCTION app.is_case_lead_lawyer(p_case uuid) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM public.case_members m
            WHERE m.case_id = p_case
              AND m.user_id = app.current_user_id()
              AND m.status = 'active'
              AND m.role = 'lead_lawyer')
        $$
        """,
        """
        CREATE FUNCTION app.is_org_lawyer(p_organization uuid) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM public.organization_members m
            WHERE m.organization_id = p_organization
              AND m.user_id = app.current_user_id()
              AND m.status = 'active'
              AND m.org_role IN ('owner','lawyer'))
        $$
        """,
        """
        CREATE FUNCTION app.is_org_owner(p_organization uuid) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM public.organization_members m
            WHERE m.organization_id = p_organization
              AND m.user_id = app.current_user_id()
              AND m.status = 'active'
              AND m.org_role = 'owner')
        $$
        """,
        """
        CREATE FUNCTION app.is_org_creator(p_organization uuid) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM public.organizations o
            WHERE o.id = p_organization
              AND o.created_by = app.current_user_id())
        $$
        """,
        """
        CREATE FUNCTION app.is_case_creator(p_case uuid) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM public.cases c
            WHERE c.id = p_case
              AND c.created_by = app.current_user_id())
        $$
        """,
        """
        CREATE FUNCTION app.is_lawyer_member(p_case uuid) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM public.case_members m
            WHERE m.case_id = p_case
              AND m.user_id = app.current_user_id()
              AND m.status = 'active'
              AND m.role IN ('lead_lawyer','team_lawyer','assistant'))
        $$
        """,
        """
        CREATE FUNCTION app.is_client_member(p_case uuid) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT EXISTS (
            SELECT 1 FROM public.case_members m
            WHERE m.case_id = p_case
              AND m.user_id = app.current_user_id()
              AND m.status = 'active'
              AND m.role = 'client')
        $$
        """,
    )
    for statement in statements:
        op.execute(statement)


def _create_policies() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")

    policies = (
        """
        CREATE POLICY organizations_read_members ON public.organizations
        FOR SELECT TO app_user USING (app.is_org_member(id))
        """,
        """
        CREATE POLICY organizations_create_self ON public.organizations
        FOR INSERT TO app_user WITH CHECK (created_by = app.current_user_id())
        """,
        """
        CREATE POLICY organizations_update_owner ON public.organizations
        FOR UPDATE TO app_user USING (app.is_org_owner(id))
        WITH CHECK (app.is_org_owner(id))
        """,
        """
        CREATE POLICY users_read_self ON public.users
        FOR SELECT TO app_user USING (id = app.current_user_id())
        """,
        """
        CREATE POLICY users_create_lawyer_self ON public.users
        FOR INSERT TO app_user
        WITH CHECK (id = app.current_user_id() AND role = 'lawyer')
        """,
        """
        CREATE POLICY users_update_self ON public.users
        FOR UPDATE TO app_user USING (id = app.current_user_id())
        WITH CHECK (id = app.current_user_id())
        """,
        """
        CREATE POLICY organization_members_read ON public.organization_members
        FOR SELECT TO app_user
        USING (user_id = app.current_user_id() OR app.is_org_member(organization_id))
        """,
        """
        CREATE POLICY organization_members_create_owner ON public.organization_members
        FOR INSERT TO app_user
        WITH CHECK (
          (user_id = app.current_user_id() AND org_role = 'owner'
            AND app.is_org_creator(organization_id))
          OR app.is_org_owner(organization_id))
        """,
        """
        CREATE POLICY organization_members_update_owner ON public.organization_members
        FOR UPDATE TO app_user USING (app.is_org_owner(organization_id))
        WITH CHECK (app.is_org_owner(organization_id))
        """,
        """
        CREATE POLICY organization_members_delete_owner ON public.organization_members
        FOR DELETE TO app_user USING (app.is_org_owner(organization_id))
        """,
        """
        CREATE POLICY lawyer_profiles_self ON public.lawyer_profiles
        FOR ALL TO app_user USING (user_id = app.current_user_id())
        WITH CHECK (user_id = app.current_user_id())
        """,
        """
        CREATE POLICY client_profiles_read ON public.client_profiles
        FOR SELECT TO app_user
        USING (app.is_org_member(organization_id) OR user_id = app.current_user_id())
        """,
        """
        CREATE POLICY client_profiles_create_lawyer ON public.client_profiles
        FOR INSERT TO app_user
        WITH CHECK (
          app.is_org_lawyer(organization_id)
          AND created_by = app.current_user_id()
          AND user_id IS NULL)
        """,
        """
        CREATE POLICY client_profiles_update_lawyer ON public.client_profiles
        FOR UPDATE TO app_user USING (app.is_org_lawyer(organization_id))
        WITH CHECK (app.is_org_lawyer(organization_id))
        """,
        """
        CREATE POLICY sessions_self ON public.sessions
        FOR SELECT TO app_user
        USING (
          user_id = app.current_user_id()
          AND revoked_at IS NULL
          AND expires_at > now())
        """,
        """
        CREATE POLICY sessions_create_self ON public.sessions
        FOR INSERT TO app_user WITH CHECK (user_id = app.current_user_id())
        """,
        """
        CREATE POLICY sessions_update_self ON public.sessions
        FOR UPDATE TO app_user USING (user_id = app.current_user_id())
        WITH CHECK (user_id = app.current_user_id())
        """,
        """
        CREATE POLICY sessions_delete_self ON public.sessions
        FOR DELETE TO app_user USING (user_id = app.current_user_id())
        """,
        """
        CREATE POLICY password_reset_tokens_self ON public.password_reset_tokens
        FOR SELECT TO app_user
        USING (
          user_id = app.current_user_id()
          AND used_at IS NULL
          AND expires_at > now())
        """,
        """
        CREATE POLICY password_reset_tokens_create_self
        ON public.password_reset_tokens FOR INSERT TO app_user
        WITH CHECK (user_id = app.current_user_id())
        """,
        """
        CREATE POLICY password_reset_tokens_update_self
        ON public.password_reset_tokens FOR UPDATE TO app_user
        USING (user_id = app.current_user_id())
        WITH CHECK (user_id = app.current_user_id())
        """,
        """
        CREATE POLICY lawyer_cases ON public.cases
        FOR SELECT TO app_user USING (app.is_lawyer_member(id))
        """,
        """
        CREATE POLICY lawyer_create_cases ON public.cases
        FOR INSERT TO app_user
        WITH CHECK (
          app.is_org_lawyer(organization_id)
          AND created_by = app.current_user_id())
        """,
        """
        CREATE POLICY lawyer_update_cases ON public.cases
        FOR UPDATE TO app_user USING (app.is_lawyer_member(id))
        WITH CHECK (app.is_org_lawyer(organization_id))
        """,
        """
        CREATE POLICY lawyer_case_stages ON public.case_stages
        FOR ALL TO app_user USING (app.is_lawyer_member(case_id))
        WITH CHECK (app.is_lawyer_member(case_id))
        """,
        """
        CREATE POLICY case_members_read ON public.case_members
        FOR SELECT TO app_user
        USING (app.is_lawyer_member(case_id) OR user_id = app.current_user_id())
        """,
        """
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
        """,
        """
        CREATE POLICY case_members_update ON public.case_members
        FOR UPDATE TO app_user USING (app.is_case_lead_lawyer(case_id))
        WITH CHECK (app.is_case_lead_lawyer(case_id))
        """,
        """
        CREATE POLICY lawyer_case_invitations ON public.case_invitations
        FOR ALL TO app_user USING (app.is_case_lead_lawyer(case_id))
        WITH CHECK (
          app.is_case_lead_lawyer(case_id)
          AND created_by = app.current_user_id()
          AND EXISTS (
            SELECT 1 FROM public.client_profiles cp
            WHERE cp.id = client_profile_id
              AND cp.organization_id = organization_id))
        """,
    )
    for policy in policies:
        op.execute(policy)


def _grant_runtime_access() -> None:
    statements = (
        "GRANT SELECT, INSERT ON public.organizations TO app_user",
        "GRANT UPDATE (name, kind) ON public.organizations TO app_user",
        """
        GRANT SELECT ON public.users TO app_user
        """,
        """
        GRANT INSERT (id, email, password_hash, role, full_name, phone,
          preferred_language) ON public.users TO app_user
        """,
        """
        GRANT UPDATE (email, password_hash, full_name, phone, preferred_language,
          mfa_secret_enc, mfa_enabled, failed_logins, locked_until, last_login_at,
          updated_at) ON public.users TO app_user
        """,
        "GRANT SELECT ON public.organization_members TO app_user",
        "GRANT INSERT ON public.organization_members TO app_user",
        "GRANT UPDATE (org_role, status) ON public.organization_members TO app_user",
        "GRANT SELECT, INSERT ON public.lawyer_profiles TO app_user",
        """
        GRANT UPDATE (bar_enrollment_no, practice_areas, courts, chamber_name)
          ON public.lawyer_profiles TO app_user
        """,
        "GRANT SELECT, INSERT ON public.client_profiles TO app_user",
        """
        GRANT UPDATE (display_name, email, phone, address, national_id_enc,
          internal_notes) ON public.client_profiles TO app_user
        """,
        "GRANT SELECT, INSERT, DELETE ON public.sessions TO app_user",
        """
        GRANT UPDATE (token_hash, last_seen_at, expires_at, revoked_at, ip,
          user_agent) ON public.sessions TO app_user
        """,
        "GRANT SELECT, INSERT ON public.password_reset_tokens TO app_user",
        "GRANT UPDATE (expires_at, used_at) ON public.password_reset_tokens TO app_user",
        "GRANT SELECT, INSERT ON public.cases TO app_user",
        """
        GRANT UPDATE (reference_no, title, case_type, workflow_template_id, court,
          court_case_no, jurisdiction, opposing_party, description, internal_notes,
          client_objectives, status, current_stage, key_dates, closed_at, closed_by,
          retention_until, updated_at) ON public.cases TO app_user
        """,
        "GRANT SELECT, INSERT, DELETE ON public.case_stages TO app_user",
        "GRANT UPDATE (position, name, client_label, status) ON public.case_stages TO app_user",
        "GRANT SELECT, INSERT ON public.case_members TO app_user",
        "GRANT UPDATE (permissions, status, revoked_at) ON public.case_members TO app_user",
        "GRANT SELECT, INSERT ON public.case_invitations TO app_user",
        "GRANT UPDATE (accepted_at, revoked_at) ON public.case_invitations TO app_user",
        "GRANT EXECUTE ON FUNCTION app.current_user_id() TO app_user",
        "GRANT EXECUTE ON FUNCTION app.is_org_member(uuid) TO app_user",
        "GRANT EXECUTE ON FUNCTION app.is_org_lawyer(uuid) TO app_user",
        "GRANT EXECUTE ON FUNCTION app.is_org_owner(uuid) TO app_user",
        "GRANT EXECUTE ON FUNCTION app.is_org_member_user(uuid, uuid) TO app_user",
        "GRANT EXECUTE ON FUNCTION app.is_org_creator(uuid) TO app_user",
        "GRANT EXECUTE ON FUNCTION app.is_case_creator(uuid) TO app_user",
        "GRANT EXECUTE ON FUNCTION app.is_case_lead_lawyer(uuid) TO app_user",
        "GRANT EXECUTE ON FUNCTION app.is_lawyer_member(uuid) TO app_user",
        "GRANT EXECUTE ON FUNCTION app.is_client_member(uuid) TO app_user",
    )
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    for table in TABLES:
        op.execute(f"DROP TABLE public.{table}")
    functions = (
        ("is_client_member", "uuid"),
        ("is_lawyer_member", "uuid"),
        ("is_case_lead_lawyer", "uuid"),
        ("is_case_creator", "uuid"),
        ("is_org_creator", "uuid"),
        ("is_org_owner", "uuid"),
        ("is_org_member_user", "uuid, uuid"),
        ("is_org_lawyer", "uuid"),
        ("is_org_member", "uuid"),
        ("current_user_id", ""),
    )
    for name, argument in functions:
        suffix = f"({argument})" if argument else "()"
        op.execute(f"DROP FUNCTION IF EXISTS app.{name}{suffix}")
    op.execute("DROP SCHEMA app")
    op.execute("RESET ROLE")
