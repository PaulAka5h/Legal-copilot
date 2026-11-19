"""Client task status updates and client-actor audit events.

Revision ID: 0011_dev1_client_task_audit
Revises: 0010_dev1_rls_and_claims
Create Date: 2026-11-19

1. ``app.client_set_task_status``: clients have only SELECT on ``client_tasks``,
   so ``PATCH /client/tasks/{id}`` could never update a row. This narrow
   SECURITY DEFINER function lets an active client of an open case change only
   ``status``/``completed_at`` of that case's tasks. No table-level UPDATE is
   granted to clients.
2. ``app.write_audit_event``: case-scoped events may now be written by an active
   client member as well as a lawyer member, so client actions (task status,
   document download) appear in the lawyer's case audit trail.

Local draft; not applied to any shared database.
"""

from alembic import op

revision = "0011_dev1_client_task_audit"
down_revision = "0010_dev1_rls_and_claims"
branch_labels = None
depends_on = None

AUDIT_SIGNATURE = "uuid,uuid,uuid,text,text,text,uuid,inet,text,text,jsonb"


def _audit_function(case_check: str) -> str:
    return f"""
    CREATE OR REPLACE FUNCTION app.write_audit_event(
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
         AND NOT ({case_check}) THEN
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
        p_request_id, COALESCE(p_details, '{{}}'::jsonb)
      )
      RETURNING id INTO v_id;
      RETURN v_id;
    END
    $$
    """


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        """
        CREATE FUNCTION app.client_set_task_status(p_task_id uuid, p_status text)
        RETURNS TABLE (
          id uuid, case_id uuid, title text, description text,
          due_date date, status text
        )
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        BEGIN
          IF p_status NOT IN ('open', 'done', 'cancelled') THEN
            RAISE EXCEPTION 'invalid task status' USING ERRCODE = '22023';
          END IF;
          RETURN QUERY
          UPDATE public.client_tasks t
          SET status = p_status,
              completed_at = CASE WHEN p_status = 'done' THEN clock_timestamp() ELSE NULL END
          WHERE t.id = p_task_id
            AND app.is_client_member(t.case_id)
            AND EXISTS (
              SELECT 1 FROM public.cases c
              WHERE c.id = t.case_id AND c.status = 'open')
          RETURNING t.id, t.case_id, t.title, t.description, t.due_date, t.status;
        END
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION app.client_set_task_status(uuid, text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.client_set_task_status(uuid, text) TO app_user")
    op.execute(
        _audit_function("app.is_lawyer_member(p_case_id) OR app.is_client_member(p_case_id)")
    )
    op.execute(f"REVOKE ALL ON FUNCTION app.write_audit_event({AUDIT_SIGNATURE}) FROM PUBLIC")
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(_audit_function("app.is_lawyer_member(p_case_id)"))
    op.execute("DROP FUNCTION app.client_set_task_status(uuid, text)")
    op.execute("RESET ROLE")
