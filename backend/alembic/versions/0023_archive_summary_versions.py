"""Case archive (soft delete) and lawyer-edited hearing summary versions.

- cases.archived_at / archived_by: a lead lawyer may archive a case. Nothing is
  deleted; archived cases are hidden from lists by default and can be restored.
  Archive and restore are audit-logged by the API.
- hearing_summary_versions: append-only lawyer edits of a hearing summary. Each
  save is a new row (version n+1, supersedes_id = the previous row); rows are
  never updated or deleted (Rule 6). Lawyer case members only; no client policy
  (the client sees only published client updates, Rule 8).

Revision ID: 0023_archive_summary_versions
Revises: 0022_query_rewrite_cache
Create Date: 2026-11-23
"""

from alembic import op

revision = "0023_archive_summary_versions"
down_revision = "0022_query_rewrite_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        """
        ALTER TABLE public.cases
          ADD COLUMN archived_at timestamptz,
          ADD COLUMN archived_by uuid REFERENCES public.users(id)
        """
    )
    op.execute("GRANT UPDATE (archived_at, archived_by) ON public.cases TO app_user")
    op.execute(
        """
        CREATE TABLE public.hearing_summary_versions (
          id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          case_id         uuid NOT NULL REFERENCES public.cases(id),
          organization_id uuid NOT NULL REFERENCES public.organizations(id),
          hearing_id      uuid NOT NULL REFERENCES public.hearings(id),
          version         integer NOT NULL CHECK (version >= 2),
          supersedes_id   uuid REFERENCES public.hearing_summary_versions(id),
          sections        jsonb NOT NULL CHECK (jsonb_typeof(sections) = 'array'),
          created_by      uuid NOT NULL REFERENCES public.users(id),
          created_at      timestamptz NOT NULL DEFAULT now(),
          UNIQUE (hearing_id, version),
          CONSTRAINT fk_summary_versions_case_org FOREIGN KEY (case_id, organization_id)
            REFERENCES public.cases(id, organization_id)
        )
        """
    )
    op.execute("ALTER TABLE public.hearing_summary_versions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.hearing_summary_versions FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY summary_versions_lawyer_read ON public.hearing_summary_versions "
        "FOR SELECT TO app_user USING (app.is_lawyer_member(case_id))"
    )
    op.execute(
        "CREATE POLICY summary_versions_lawyer_insert ON public.hearing_summary_versions "
        "FOR INSERT TO app_user WITH CHECK (app.is_lawyer_member(case_id) "
        "AND created_by = app.current_user_id())"
    )
    op.execute("GRANT SELECT, INSERT ON public.hearing_summary_versions TO app_user")
    op.execute("SELECT app.ensure_owner_policies()")  # app_owner without BYPASSRLS (Neon; 0019)
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute("DROP TABLE public.hearing_summary_versions")
    op.execute("ALTER TABLE public.cases DROP COLUMN archived_by, DROP COLUMN archived_at")
    op.execute("RESET ROLE")
