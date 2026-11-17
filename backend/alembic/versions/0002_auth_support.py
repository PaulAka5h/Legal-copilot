"""Add constrained authentication lookups, IP throttling, and audit events."""

from alembic import op

revision = "0002_auth_support"
down_revision = "0001_phase1_baseline"
branch_labels = None
depends_on = None


FUNCTIONS = (
    ("record_login_result", "uuid, boolean"),
    ("consume_login_attempt", "inet"),
    ("lookup_session", "bytea"),
    ("lookup_login_user", "text"),
)


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        """
        CREATE TABLE public.auth_login_ip_limits (
          ip inet PRIMARY KEY,
          window_started_at timestamptz NOT NULL,
          attempt_count integer NOT NULL CHECK (attempt_count > 0),
          updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_auth_login_ip_limits_updated "
        "ON public.auth_login_ip_limits (updated_at)"
    )
    op.execute(
        "ALTER TABLE public.auth_login_ip_limits ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.auth_login_ip_limits FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        CREATE TABLE public.audit_logs (
          id bigserial PRIMARY KEY,
          occurred_at timestamptz NOT NULL DEFAULT now(),
          organization_id uuid,
          case_id uuid,
          actor_user_id uuid,
          actor_role text,
          action text NOT NULL,
          object_type text,
          object_id uuid,
          ip inet,
          user_agent text,
          request_id text,
          details jsonb NOT NULL DEFAULT CAST('{}' AS jsonb),
          prev_hash bytea,
          row_hash bytea
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_audit_logs_case_time "
        "ON public.audit_logs (case_id, occurred_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_audit_logs_actor_time "
        "ON public.audit_logs (actor_user_id, occurred_at DESC)"
    )
    op.execute("ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.audit_logs FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY audit_logs_insert ON public.audit_logs
        FOR INSERT TO app_user
        WITH CHECK (
          (actor_user_id IS NULL OR actor_user_id = app.current_user_id())
          AND (case_id IS NULL OR app.is_lawyer_member(case_id))
        )
        """
    )
    op.execute(
        """
        CREATE POLICY audit_logs_read ON public.audit_logs
        FOR SELECT TO app_user
        USING (
          actor_user_id = app.current_user_id()
          OR (case_id IS NOT NULL AND app.is_lawyer_member(case_id))
        )
        """
    )
    op.execute(
        "GRANT INSERT, SELECT ON public.audit_logs TO app_user"
    )
    op.execute(
        "GRANT USAGE, SELECT ON SEQUENCE public.audit_logs_id_seq TO app_user"
    )
    op.execute(
        "REVOKE UPDATE, DELETE, TRUNCATE ON public.audit_logs FROM app_user"
    )

    op.execute(
        """
        CREATE FUNCTION app.lookup_login_user(p_email text)
        RETURNS TABLE (
          user_id uuid,
          password_hash text,
          user_role text,
          user_status text,
          failed_logins integer,
          locked_until timestamptz
        )
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT u.id, u.password_hash, u.role, u.status,
                 u.failed_logins, u.locked_until
          FROM public.users AS u
          WHERE u.email = p_email::public.citext
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION app.lookup_session(p_token_hash bytea)
        RETURNS TABLE (
          session_id uuid,
          user_id uuid,
          user_role text,
          user_status text,
          expires_at timestamptz,
          last_seen_at timestamptz,
          revoked_at timestamptz,
          email text,
          full_name text,
          preferred_language text
        )
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT s.id, s.user_id, u.role, u.status, s.expires_at,
                 s.last_seen_at, s.revoked_at, u.email::text,
                 u.full_name, u.preferred_language
          FROM public.sessions AS s
          JOIN public.users AS u ON u.id = s.user_id
          WHERE s.token_hash = p_token_hash
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION app.consume_login_attempt(p_ip inet)
        RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
          attempts integer;
          v_now timestamptz := clock_timestamp();
        BEGIN
          DELETE FROM public.auth_login_ip_limits
          WHERE updated_at < v_now - interval '1 day';

          INSERT INTO public.auth_login_ip_limits
            (ip, window_started_at, attempt_count, updated_at)
          VALUES (p_ip, v_now, 1, v_now)
          ON CONFLICT (ip) DO UPDATE SET
            window_started_at = CASE
              WHEN public.auth_login_ip_limits.window_started_at
                   <= v_now - interval '15 minutes'
                THEN v_now
              ELSE public.auth_login_ip_limits.window_started_at
            END,
            attempt_count = CASE
              WHEN public.auth_login_ip_limits.window_started_at
                   <= v_now - interval '15 minutes'
                THEN 1
              ELSE LEAST(public.auth_login_ip_limits.attempt_count + 1, 2147483647)
            END,
            updated_at = v_now
          RETURNING attempt_count INTO attempts;

          RETURN attempts <= 10;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION app.record_login_result(
          p_user_id uuid, p_succeeded boolean
        )
        RETURNS void
        LANGUAGE sql SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          UPDATE public.users AS u
          SET failed_logins = CASE
                WHEN p_succeeded THEN 0 ELSE u.failed_logins + 1 END,
              locked_until = CASE
                WHEN p_succeeded THEN NULL
                WHEN u.failed_logins + 1 >= 5 THEN
                  clock_timestamp() + make_interval(secs => LEAST(
                    3600,
                    (30 * power(
                      2::numeric,
                      LEAST(GREATEST(u.failed_logins - 4, 0), 7)
                    ))::integer
                  ))
                ELSE u.locked_until
              END,
              last_login_at = CASE
                WHEN p_succeeded THEN clock_timestamp()
                ELSE u.last_login_at
              END,
              updated_at = clock_timestamp()
          WHERE u.id = p_user_id AND u.status = 'active'
        $$
        """
    )
    for name, signature in FUNCTIONS:
        op.execute(
            f"REVOKE ALL ON FUNCTION app.{name}({signature}) FROM PUBLIC"
        )
    op.execute("GRANT EXECUTE ON FUNCTION app.lookup_login_user(text) TO app_user")
    op.execute("GRANT EXECUTE ON FUNCTION app.lookup_session(bytea) TO app_user")
    op.execute("GRANT EXECUTE ON FUNCTION app.consume_login_attempt(inet) TO app_user")
    op.execute(
        "GRANT EXECUTE ON FUNCTION app.record_login_result(uuid, boolean) TO app_user"
    )
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    for name, signature in FUNCTIONS:
        op.execute(f"DROP FUNCTION IF EXISTS app.{name}({signature})")
    op.execute("DROP TABLE public.audit_logs")
    op.execute("DROP TABLE public.auth_login_ip_limits")
    op.execute("RESET ROLE")
