"""Per-user fixed-window rate limits (profile photo upload and serving).

Same mechanism as the login limiter (0002, app.consume_login_attempt), keyed by
the signed-in user and a bucket name instead of an IP:
- public.user_rate_limits: one row per (user, bucket). RLS enabled and forced
  with no app_user policy and no grants, so app_user can only reach it through
  the function below.
- app.consume_user_rate_limit(bucket, limit, window_seconds): counts one request
  for app.current_user_id() and returns whether it is within the limit. Rows
  idle for a day are deleted on each call.

Revision ID: 0027_user_rate_limits
Revises: 0026_lawyer_profile_details
Create Date: 2026-11-23
"""

from alembic import op

revision = "0027_user_rate_limits"
down_revision = "0026_lawyer_profile_details"
branch_labels = None
depends_on = None

FUNCTION = "app.consume_user_rate_limit(text, integer, integer)"


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        """
        CREATE TABLE public.user_rate_limits (
          user_id uuid NOT NULL REFERENCES public.users(id),
          bucket text NOT NULL CHECK (char_length(bucket) BETWEEN 1 AND 50),
          window_started_at timestamptz NOT NULL,
          request_count integer NOT NULL CHECK (request_count > 0),
          updated_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY (user_id, bucket)
        )
        """
    )
    op.execute("CREATE INDEX ix_user_rate_limits_updated ON public.user_rate_limits (updated_at)")
    op.execute("ALTER TABLE public.user_rate_limits ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.user_rate_limits FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE FUNCTION app.consume_user_rate_limit(p_bucket text, p_limit integer, p_window_seconds integer)
        RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
          v_user uuid := app.current_user_id();
          v_now timestamptz := clock_timestamp();
          v_window interval := make_interval(secs => p_window_seconds);
          v_count integer;
        BEGIN
          IF v_user IS NULL OR p_limit < 1 OR p_window_seconds < 1 THEN
            RETURN false;
          END IF;

          DELETE FROM public.user_rate_limits
          WHERE updated_at < v_now - interval '1 day';

          INSERT INTO public.user_rate_limits
            (user_id, bucket, window_started_at, request_count, updated_at)
          VALUES (v_user, p_bucket, v_now, 1, v_now)
          ON CONFLICT (user_id, bucket) DO UPDATE SET
            window_started_at = CASE
              WHEN public.user_rate_limits.window_started_at <= v_now - v_window THEN v_now
              ELSE public.user_rate_limits.window_started_at
            END,
            request_count = CASE
              WHEN public.user_rate_limits.window_started_at <= v_now - v_window THEN 1
              ELSE LEAST(public.user_rate_limits.request_count + 1, 2147483647)
            END,
            updated_at = v_now
          RETURNING request_count INTO v_count;

          RETURN v_count <= p_limit;
        END
        $$
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {FUNCTION} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {FUNCTION} TO app_user")
    op.execute("SELECT app.ensure_owner_policies()")  # app_owner without BYPASSRLS (Neon; 0019)
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(f"DROP FUNCTION {FUNCTION}")
    op.execute("DROP TABLE public.user_rate_limits")
    op.execute("RESET ROLE")
