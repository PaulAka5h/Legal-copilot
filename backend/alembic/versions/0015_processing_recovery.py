"""Crash recovery for document processing.

- documents.processing_started_at: set when processing starts (queue time is not
  counted as stuck time once ARQ queues documents).
- app.fail_stuck_documents(older_than interval): marks documents that have been
  'processing' longer than older_than as failed with processing_error
  'processing_timeout' (retryable: process_document accepts failed documents
  without pages). SECURITY DEFINER so a startup or CLI sweep can cover all cases
  without RLS bypass for app_user; it changes nothing else. Refuses intervals
  under 5 minutes. One audit event per document (case id in details, since the
  sweep runs without a user).

Revision ID: 0015_processing_recovery
Revises: 0014_case_facts
Create Date: 2026-11-20
"""

from alembic import op

revision = "0015_processing_recovery"
down_revision = "0014_case_facts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute("ALTER TABLE public.documents ADD COLUMN processing_started_at timestamptz")
    op.execute("GRANT UPDATE (processing_started_at) ON public.documents TO app_user")
    op.execute(
        """
        CREATE FUNCTION app.fail_stuck_documents(p_older_than interval) RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
          v_id uuid;
          v_case uuid;
          v_count integer := 0;
        BEGIN
          IF p_older_than IS NULL OR p_older_than < interval '5 minutes' THEN
            RAISE EXCEPTION 'older_than must be at least 5 minutes';
          END IF;
          FOR v_id, v_case IN
            UPDATE public.documents
            SET processing_status = 'failed', processing_error = 'processing_timeout'
            WHERE processing_status = 'processing'
              AND coalesce(processing_started_at, uploaded_at) < now() - p_older_than
            RETURNING id, case_id
          LOOP
            v_count := v_count + 1;
            PERFORM app.write_audit_event(
              NULL, NULL, NULL, 'system', 'document.processing_timed_out', 'document', v_id,
              NULL, NULL, NULL,
              jsonb_build_object('case_id', v_case, 'older_than', p_older_than::text)
            );
          END LOOP;
          RETURN v_count;
        END
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION app.fail_stuck_documents(interval) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.fail_stuck_documents(interval) TO app_user")
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute("DROP FUNCTION app.fail_stuck_documents(interval)")
    op.execute("ALTER TABLE public.documents DROP COLUMN processing_started_at")
    op.execute("RESET ROLE")
