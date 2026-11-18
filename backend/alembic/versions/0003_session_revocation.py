"""Revoke sessions through a narrowly scoped security-definer function."""

from alembic import op

revision = "0003_session_revocation"
down_revision = "0002_auth_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        """
        CREATE FUNCTION app.revoke_sessions(p_session_id uuid)
        RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
          v_user_id uuid := app.current_user_id();
          v_revoked_count integer;
        BEGIN
          IF v_user_id IS NULL THEN
            RETURN 0;
          END IF;

          UPDATE public.sessions
          SET revoked_at = clock_timestamp()
          WHERE user_id = v_user_id
            AND revoked_at IS NULL
            AND (p_session_id IS NULL OR id = p_session_id);

          GET DIAGNOSTICS v_revoked_count = ROW_COUNT;
          RETURN v_revoked_count;
        END
        $$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION app.revoke_sessions(uuid) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION app.revoke_sessions(uuid) TO app_user"
    )
    op.execute(
        "REVOKE UPDATE (revoked_at) ON public.sessions FROM app_user"
    )
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        "GRANT UPDATE (revoked_at) ON public.sessions TO app_user"
    )
    op.execute("DROP FUNCTION app.revoke_sessions(uuid)")
    op.execute("RESET ROLE")
