"""Human approval of legal source versions, recorded with reviewer, time, and audit event.

Search only uses versions with review_status = 'approved' (database.md 12.4).
Ingestion never approves. app_admin_ingest gets EXECUTE on two narrow functions
instead of UPDATE on review columns or SELECT on users:

- app.find_legal_reviewer(email) -> user id of an active lawyer/admin, else NULL
- app.approve_legal_source_version(version, reviewer_email, note) -> reviewer id;
  approves a pending version only, sets reviewed_by/reviewed_at, and writes
  'legal_source_version.approved' through app.write_audit_event.

Revision ID: 0012_legal_version_approval
Revises: 0011_legal_knowledge_base
Create Date: 2026-11-20
"""

from alembic import op

revision = "0012_legal_version_approval"
down_revision = "0011_legal_knowledge_base"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        """
        CREATE FUNCTION app.find_legal_reviewer(p_email text) RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT u.id FROM public.users u
          WHERE u.email = p_email::citext
            AND u.status = 'active'
            AND u.role IN ('lawyer', 'admin')
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION app.approve_legal_source_version(
          p_version uuid, p_reviewer_email text, p_note text
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
          v_reviewer uuid;
          v_role text;
        BEGIN
          v_reviewer := app.find_legal_reviewer(p_reviewer_email);
          IF v_reviewer IS NULL THEN
            RAISE EXCEPTION 'reviewer must be an active lawyer or admin';
          END IF;
          SELECT role INTO v_role FROM public.users WHERE id = v_reviewer;

          UPDATE public.legal_source_versions
          SET review_status = 'approved', reviewed_by = v_reviewer, reviewed_at = now()
          WHERE id = p_version AND review_status = 'pending';
          IF NOT FOUND THEN
            RAISE EXCEPTION 'legal source version % is not pending', p_version;
          END IF;

          -- write_audit_event requires the actor to be the transaction user.
          PERFORM set_config('app.current_user_id', v_reviewer::text, true);
          PERFORM app.write_audit_event(
            NULL, NULL, v_reviewer, v_role,
            'legal_source_version.approved', 'legal_source_version', p_version,
            NULL, NULL, NULL,
            jsonb_build_object('channel', 'cli', 'note', p_note)
          );
          RETURN v_reviewer;
        END
        $$
        """
    )
    for signature in ("app.find_legal_reviewer(text)", "app.approve_legal_source_version(uuid, text, text)"):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO app_admin_ingest")
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute("DROP FUNCTION app.approve_legal_source_version(uuid, text, text)")
    op.execute("DROP FUNCTION app.find_legal_reviewer(text)")
    op.execute("RESET ROLE")
