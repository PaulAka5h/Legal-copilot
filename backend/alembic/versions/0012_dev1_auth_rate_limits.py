"""Generic auth rate limits; fix password reset token SELECT policy.

Revision ID: 0012_dev1_auth_rate_limits
Revises: 0011_dev1_client_task_audit
Create Date: 2026-11-19

1. ``auth_rate_limits`` + ``app.consume_rate_limit(bucket, key, limit, window)``:
   fixed-window counters for password forgot/reset and MFA verification. Keys
   are stored as SHA-256 hashes (no raw emails or IPs). No table grants; access
   only through the SECURITY DEFINER function.
2. ``password_reset_tokens_self`` (0001) only exposed unused, unexpired rows.
   PostgreSQL checks an UPDATE's new row against SELECT policies, so marking an
   earlier token used in ``/password/forgot`` always failed (500 on any second
   request). The policy now exposes the user's own tokens; validity is still
   enforced by ``app.lookup_password_reset`` / ``app.consume_password_reset``.

Local draft; not applied to any shared database.
"""

from alembic import op

revision = "0012_dev1_auth_rate_limits"
down_revision = "0011_dev1_client_task_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        """
        CREATE TABLE public.auth_rate_limits (
          bucket text NOT NULL,
          key_hash bytea NOT NULL,
          window_started_at timestamptz NOT NULL,
          attempt_count integer NOT NULL CHECK (attempt_count > 0),
          updated_at timestamptz NOT NULL,
          PRIMARY KEY (bucket, key_hash)
        )
        """
    )
    op.execute("CREATE INDEX ix_auth_rate_limits_updated ON public.auth_rate_limits (updated_at)")
    op.execute("ALTER TABLE public.auth_rate_limits ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.auth_rate_limits FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE FUNCTION app.consume_rate_limit(
          p_bucket text, p_key text, p_limit integer, p_window_seconds integer
        )
        RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
          v_now timestamptz := clock_timestamp();
          v_window interval := make_interval(secs => p_window_seconds);
          v_attempts integer;
        BEGIN
          IF p_limit < 1 OR p_window_seconds < 1 OR p_bucket = '' THEN
            RAISE EXCEPTION 'invalid rate limit' USING ERRCODE = '22023';
          END IF;
          DELETE FROM public.auth_rate_limits WHERE updated_at < v_now - interval '1 day';
          INSERT INTO public.auth_rate_limits AS r
            (bucket, key_hash, window_started_at, attempt_count, updated_at)
          VALUES (p_bucket, sha256(convert_to(p_key, 'UTF8')), v_now, 1, v_now)
          ON CONFLICT (bucket, key_hash) DO UPDATE SET
            window_started_at = CASE WHEN r.window_started_at <= v_now - v_window
                                     THEN v_now ELSE r.window_started_at END,
            attempt_count = CASE WHEN r.window_started_at <= v_now - v_window
                                 THEN 1 ELSE LEAST(r.attempt_count + 1, 2147483647) END,
            updated_at = v_now
          RETURNING attempt_count INTO v_attempts;
          RETURN v_attempts <= p_limit;
        END
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION app.consume_rate_limit(text, text, integer, integer) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.consume_rate_limit(text, text, integer, integer) TO app_user")

    op.execute("DROP POLICY password_reset_tokens_self ON public.password_reset_tokens")
    op.execute(
        """
        CREATE POLICY password_reset_tokens_self ON public.password_reset_tokens
        FOR SELECT TO app_user
        USING (user_id = app.current_user_id())
        """
    )
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute("DROP POLICY password_reset_tokens_self ON public.password_reset_tokens")
    op.execute(
        """
        CREATE POLICY password_reset_tokens_self ON public.password_reset_tokens
        FOR SELECT TO app_user
        USING (user_id = app.current_user_id() AND used_at IS NULL AND expires_at > now())
        """
    )
    op.execute("DROP FUNCTION app.consume_rate_limit(text, text, integer, integer)")
    op.execute("DROP TABLE public.auth_rate_limits")
    op.execute("RESET ROLE")
