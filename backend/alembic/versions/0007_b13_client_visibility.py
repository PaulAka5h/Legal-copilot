"""Add client-visible Phase 2 tables and RLS."""

from alembic import op

revision = "0007_b13_client_visibility"
down_revision = "0006_b12_invitations"
branch_labels = None
depends_on = None


TABLES = (
    """
    CREATE TABLE public.hearings (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      case_id uuid NOT NULL REFERENCES public.cases(id),
      organization_id uuid NOT NULL,
      scheduled_at timestamptz,
      purpose text,
      court_room text,
      date_status text NOT NULL DEFAULT 'tentative'
        CHECK (date_status IN ('tentative','confirmed','postponed','held','cancelled')),
      date_confirmed_by uuid REFERENCES public.users(id),
      date_confirmed_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT fk_hearings_org FOREIGN KEY (case_id, organization_id)
        REFERENCES public.cases(id, organization_id)
    )
    """,
    """
    CREATE TABLE public.client_visible_updates (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      case_id uuid NOT NULL REFERENCES public.cases(id),
      organization_id uuid NOT NULL,
      version integer NOT NULL DEFAULT 1,
      supersedes_id uuid REFERENCES public.client_visible_updates(id),
      title text NOT NULL,
      body text NOT NULL,
      language text NOT NULL DEFAULT 'en' CHECK (language IN ('en','bn')),
      status text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft','published','withdrawn')),
      drafted_by_ai boolean NOT NULL DEFAULT false,
      approved_by uuid REFERENCES public.users(id),
      published_at timestamptz,
      withdrawn_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT fk_visible_updates_org FOREIGN KEY (case_id, organization_id)
        REFERENCES public.cases(id, organization_id)
    )
    """,
    """
    CREATE TABLE public.client_shared_documents (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      case_id uuid NOT NULL REFERENCES public.cases(id),
      organization_id uuid NOT NULL,
      document_id uuid NOT NULL,
      display_name text NOT NULL,
      shared_by uuid NOT NULL REFERENCES public.users(id),
      shared_at timestamptz NOT NULL DEFAULT now(),
      revoked_at timestamptz,
      UNIQUE (case_id, document_id),
      CONSTRAINT fk_shared_documents_org FOREIGN KEY (case_id, organization_id)
        REFERENCES public.cases(id, organization_id)
    )
    """,
    """
    CREATE TABLE public.client_tasks (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      case_id uuid NOT NULL REFERENCES public.cases(id),
      organization_id uuid NOT NULL,
      title text NOT NULL,
      description text,
      due_date date,
      status text NOT NULL DEFAULT 'open'
        CHECK (status IN ('open','done','cancelled')),
      created_by uuid NOT NULL REFERENCES public.users(id),
      created_at timestamptz NOT NULL DEFAULT now(),
      completed_at timestamptz,
      CONSTRAINT fk_client_tasks_org FOREIGN KEY (case_id, organization_id)
        REFERENCES public.cases(id, organization_id)
    )
    """,
    """
    CREATE TABLE public.client_visible_case_fields (
      case_id uuid PRIMARY KEY REFERENCES public.cases(id),
      organization_id uuid NOT NULL,
      status_label text,
      stage_label text,
      plain_explanation text,
      next_hearing_id uuid REFERENCES public.hearings(id),
      show_next_hearing boolean NOT NULL DEFAULT false,
      updated_by uuid REFERENCES public.users(id),
      updated_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT fk_visible_fields_org FOREIGN KEY (case_id, organization_id)
        REFERENCES public.cases(id, organization_id)
    )
    """,
    """
    CREATE TABLE public.notifications (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id uuid NOT NULL REFERENCES public.users(id),
      case_id uuid REFERENCES public.cases(id),
      audience text NOT NULL CHECK (audience IN ('lawyer','client')),
      kind text NOT NULL,
      title text NOT NULL,
      body text,
      read_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now()
    )
    """,
)


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    for statement in TABLES:
        op.execute(statement)
    for table in (
        "hearings",
        "client_visible_updates",
        "client_shared_documents",
        "client_tasks",
        "client_visible_case_fields",
        "notifications",
    ):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY lawyer_manage_visible_updates ON public.client_visible_updates
        FOR ALL TO app_user
        USING (app.is_lawyer_member(case_id))
        WITH CHECK (app.is_lawyer_member(case_id))
        """
    )
    op.execute(
        """
        CREATE POLICY client_read_published_updates ON public.client_visible_updates
        FOR SELECT TO app_user
        USING (status = 'published'
          AND app.is_client_member(case_id)
          AND EXISTS (SELECT 1 FROM public.cases c
                      WHERE c.id = case_id AND c.status = 'open'))
        """
    )
    op.execute(
        """
        CREATE POLICY lawyer_manage_shared_documents ON public.client_shared_documents
        FOR ALL TO app_user
        USING (app.is_lawyer_member(case_id))
        WITH CHECK (app.is_lawyer_member(case_id))
        """
    )
    op.execute(
        """
        CREATE POLICY client_read_shared_documents ON public.client_shared_documents
        FOR SELECT TO app_user
        USING (revoked_at IS NULL
          AND app.is_client_member(case_id)
          AND EXISTS (SELECT 1 FROM public.cases c
                      WHERE c.id = case_id AND c.status = 'open'))
        """
    )
    op.execute(
        """
        CREATE POLICY lawyer_manage_client_tasks ON public.client_tasks
        FOR ALL TO app_user
        USING (app.is_lawyer_member(case_id))
        WITH CHECK (app.is_lawyer_member(case_id))
        """
    )
    op.execute(
        """
        CREATE POLICY client_read_client_tasks ON public.client_tasks
        FOR SELECT TO app_user
        USING (app.is_client_member(case_id)
          AND EXISTS (SELECT 1 FROM public.cases c
                      WHERE c.id = case_id AND c.status = 'open'))
        """
    )
    op.execute(
        """
        CREATE POLICY lawyer_manage_case_fields ON public.client_visible_case_fields
        FOR ALL TO app_user
        USING (app.is_lawyer_member(case_id))
        WITH CHECK (app.is_lawyer_member(case_id))
        """
    )
    op.execute(
        """
        CREATE POLICY client_read_case_fields ON public.client_visible_case_fields
        FOR SELECT TO app_user
        USING (app.is_client_member(case_id)
          AND EXISTS (SELECT 1 FROM public.cases c
                      WHERE c.id = case_id AND c.status = 'open'))
        """
    )
    op.execute(
        """
        CREATE POLICY hearings_lawyer ON public.hearings
        FOR ALL TO app_user
        USING (app.is_lawyer_member(case_id))
        WITH CHECK (app.is_lawyer_member(case_id))
        """
    )
    op.execute(
        """
        CREATE POLICY hearings_client ON public.hearings
        FOR SELECT TO app_user
        USING (date_status = 'confirmed'
          AND app.is_client_member(case_id)
          AND EXISTS (SELECT 1 FROM public.cases c
                      WHERE c.id = case_id AND c.status = 'open'))
        """
    )
    op.execute(
        """
        CREATE POLICY notification_owner ON public.notifications
        FOR ALL TO app_user
        USING (user_id = app.current_user_id())
        WITH CHECK (user_id = app.current_user_id())
        """
    )
    for table in (
        "hearings",
        "client_visible_updates",
        "client_shared_documents",
        "client_tasks",
        "client_visible_case_fields",
        "notifications",
    ):
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON public.{table} TO app_user")
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    for table in (
        "notifications",
        "client_visible_case_fields",
        "client_tasks",
        "client_shared_documents",
        "client_visible_updates",
        "hearings",
    ):
        op.execute(f"DROP TABLE IF EXISTS public.{table}")
    op.execute("RESET ROLE")
