"""Centralize append-only audit inserts."""

from alembic import op

revision = "0005_b10_audit_writer"
down_revision = "0004_b9_auth_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute("REVOKE INSERT ON TABLE public.audit_logs FROM app_user")
    op.execute(
        """
        CREATE FUNCTION app.write_audit_event(
          p_organization_id uuid,
          p_case_id uuid,
          p_actor_user_id uuid,
          p_actor_role text,
          p_action text,
          p_object_type text,
          p_object_id uuid,
          p_ip inet,
          p_user_agent text,
          p_request_id text,
          p_details jsonb
        )
        RETURNS bigint
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
          v_id bigint;
        BEGIN
          IF p_actor_user_id IS NOT NULL
             AND p_actor_user_id != app.current_user_id() THEN
            RAISE EXCEPTION 'audit actor does not match transaction user';
          END IF;
          IF p_case_id IS NOT NULL
             AND NOT app.is_lawyer_member(p_case_id) THEN
            RAISE EXCEPTION 'audit case is not accessible';
          END IF;
          PERFORM pg_advisory_xact_lock(hashtext('legal_copilot.audit_logs'));
          INSERT INTO public.audit_logs (
            organization_id, case_id, actor_user_id, actor_role, action,
            object_type, object_id, ip, user_agent, request_id, details
          )
          VALUES (
            p_organization_id, p_case_id, p_actor_user_id, p_actor_role,
            p_action, p_object_type, p_object_id, p_ip, p_user_agent,
            p_request_id, COALESCE(p_details, '{}'::jsonb)
          )
          RETURNING id INTO v_id;
          RETURN v_id;
        END
        $$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION app.write_audit_event("
        "uuid,uuid,uuid,text,text,text,uuid,inet,text,text,jsonb) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION app.write_audit_event("
        "uuid,uuid,uuid,text,text,text,uuid,inet,text,text,jsonb) TO app_user"
    )
    op.execute(
        """
        CREATE FUNCTION app.prevent_audit_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          RAISE EXCEPTION 'audit_logs is append-only';
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_logs_append_only
        BEFORE UPDATE OR DELETE ON public.audit_logs
        FOR EACH ROW EXECUTE FUNCTION app.prevent_audit_mutation()
        """
    )
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute("DROP TRIGGER IF EXISTS audit_logs_append_only ON public.audit_logs")
    op.execute("DROP FUNCTION IF EXISTS app.prevent_audit_mutation()")
    op.execute(
        "DROP FUNCTION IF EXISTS app.write_audit_event("
        "uuid,uuid,uuid,text,text,text,uuid,inet,text,text,jsonb)"
    )
    op.execute("GRANT INSERT ON TABLE public.audit_logs TO app_user")
    op.execute("RESET ROLE")
