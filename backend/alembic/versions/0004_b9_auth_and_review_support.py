"""Add reset lookup support and MFA recovery codes."""

from alembic import op

revision = "0004_b9_auth_support"
down_revision = "0003_session_revocation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute("DROP FUNCTION IF EXISTS app.lookup_login_user(text)")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.lookup_login_user(p_email text)
        RETURNS TABLE (
          user_id uuid,
          password_hash text,
          user_role text,
          user_status text,
          failed_logins integer,
          locked_until timestamptz,
          mfa_enabled boolean,
          mfa_secret_enc bytea
        )
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT u.id, u.password_hash, u.role, u.status,
                 u.failed_logins, u.locked_until,
                 u.mfa_enabled, u.mfa_secret_enc
          FROM public.users AS u
          WHERE u.email = p_email::public.citext
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION app.lookup_login_user(text) FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION app.lookup_login_user(text) FROM app_user")
    op.execute("GRANT EXECUTE ON FUNCTION app.lookup_login_user(text) TO app_user")

    op.execute(
        """
        CREATE TABLE public.mfa_recovery_codes (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id uuid NOT NULL REFERENCES public.users(id),
          code_hash bytea NOT NULL UNIQUE,
          used_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_mfa_recovery_codes_user_unused "
        "ON public.mfa_recovery_codes (user_id) WHERE used_at IS NULL"
    )
    op.execute("ALTER TABLE public.mfa_recovery_codes ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.mfa_recovery_codes FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY mfa_recovery_codes_self ON public.mfa_recovery_codes
        FOR ALL TO app_user
        USING (user_id = app.current_user_id())
        WITH CHECK (user_id = app.current_user_id())
        """
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON public.mfa_recovery_codes TO app_user"
    )

    op.execute(
        """
        CREATE FUNCTION app.lookup_password_reset(p_token_hash bytea)
        RETURNS TABLE (token_id uuid, user_id uuid)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT t.id, t.user_id
          FROM public.password_reset_tokens AS t
          WHERE t.token_hash = p_token_hash
            AND t.used_at IS NULL
            AND t.expires_at > clock_timestamp()
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION app.consume_password_reset(
          p_token_hash bytea, p_password_hash text
        )
        RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
          v_user_id uuid;
        BEGIN
          SELECT user_id INTO v_user_id
          FROM public.password_reset_tokens
          WHERE token_hash = p_token_hash
            AND used_at IS NULL
            AND expires_at > clock_timestamp()
          FOR UPDATE;
          IF v_user_id IS NULL THEN
            RETURN NULL;
          END IF;
          UPDATE public.password_reset_tokens
          SET used_at = clock_timestamp()
          WHERE user_id = v_user_id AND used_at IS NULL;
          UPDATE public.users
          SET password_hash = p_password_hash,
              failed_logins = 0,
              locked_until = NULL,
              updated_at = clock_timestamp()
          WHERE id = v_user_id;
          UPDATE public.sessions
          SET revoked_at = clock_timestamp()
          WHERE user_id = v_user_id AND revoked_at IS NULL;
          RETURN v_user_id;
        END
        $$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION app.lookup_password_reset(bytea) FROM PUBLIC"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION app.consume_password_reset(bytea, text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION app.lookup_password_reset(bytea) TO app_user"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION app.consume_password_reset(bytea, text) TO app_user"
    )
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute("DROP FUNCTION IF EXISTS app.consume_password_reset(bytea, text)")
    op.execute("DROP FUNCTION IF EXISTS app.lookup_password_reset(bytea)")
    op.execute("DROP FUNCTION IF EXISTS app.lookup_login_user(text)")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.lookup_login_user(p_email text)
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
    op.execute("REVOKE ALL ON FUNCTION app.lookup_login_user(text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.lookup_login_user(text) TO app_user")
    op.execute("DROP TABLE public.mfa_recovery_codes")
    op.execute("RESET ROLE")
