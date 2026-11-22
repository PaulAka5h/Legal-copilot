"""Client document download and lawyer contact card.

- lawyer_profiles.show_contact_to_clients (default true): the lawyer's approval to
  show phone, email and firm on their clients' dashboards (name is always shown).
- app.client_case_lawyer_contact(case): for a client member of an OPEN case, the
  lead lawyer's name and, when approved, firm (chamber or organization), phone and
  email. Nothing else of the users/lawyer_profiles rows is exposed (Rule 8).
- app.client_shared_document_file(document): for a client member of an OPEN case,
  the storage key and file metadata of a document the lawyer shared and has not
  revoked (and that is not deleted or infected). The API streams the file, so
  clients never get a storage URL and never read the documents table.

Both functions are SECURITY DEFINER with a fixed search_path and check the caller
with app.current_user_id(); EXECUTE is granted to app_user only.

Revision ID: 0025_client_docs_lawyer_contact
Revises: 0024_fact_quote_span
Create Date: 2026-11-23
"""

from alembic import op

revision = "0025_client_docs_lawyer_contact"
down_revision = "0024_fact_quote_span"
branch_labels = None
depends_on = None

CONTACT = "app.client_case_lawyer_contact(uuid)"
DOCUMENT = "app.client_shared_document_file(uuid)"


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        "ALTER TABLE public.lawyer_profiles "
        "ADD COLUMN show_contact_to_clients boolean NOT NULL DEFAULT true"
    )
    op.execute("GRANT UPDATE (show_contact_to_clients) ON public.lawyer_profiles TO app_user")
    op.execute(
        """
        CREATE FUNCTION app.client_case_lawyer_contact(p_case uuid)
        RETURNS TABLE (full_name text, firm text, phone text, email text)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT u.full_name,
                 CASE WHEN COALESCE(lp.show_contact_to_clients, true)
                      THEN COALESCE(NULLIF(btrim(lp.chamber_name), ''), NULLIF(btrim(o.name), '')) END,
                 CASE WHEN COALESCE(lp.show_contact_to_clients, true) THEN NULLIF(btrim(u.phone), '') END,
                 CASE WHEN COALESCE(lp.show_contact_to_clients, true) THEN u.email::text END
          FROM public.cases c
          JOIN public.case_members lead
            ON lead.case_id = c.id AND lead.role = 'lead_lawyer' AND lead.status = 'active'
          JOIN public.users u ON u.id = lead.user_id
          JOIN public.organizations o ON o.id = c.organization_id
          LEFT JOIN public.lawyer_profiles lp ON lp.user_id = u.id
          WHERE c.id = p_case
            AND c.status = 'open'
            AND app.is_client_member(p_case)
          LIMIT 1
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION app.client_shared_document_file(p_document uuid)
        RETURNS TABLE (case_id uuid, shared_id uuid, storage_key text, mime_type text,
                       display_name text, original_filename text)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT s.case_id, s.id, d.storage_key, d.mime_type, s.display_name, d.original_filename
          FROM public.client_shared_documents s
          JOIN public.documents d ON d.id = s.document_id AND d.case_id = s.case_id
          JOIN public.cases c ON c.id = s.case_id
          WHERE s.document_id = p_document
            AND s.revoked_at IS NULL
            AND d.deleted_at IS NULL
            AND d.processing_status <> 'deleted'
            AND d.scan_status <> 'infected'
            AND c.status = 'open'
            AND app.is_client_member(s.case_id)
          LIMIT 1
        $$
        """
    )
    for signature in (CONTACT, DOCUMENT):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO app_user")
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(f"DROP FUNCTION {DOCUMENT}")
    op.execute(f"DROP FUNCTION {CONTACT}")
    op.execute("ALTER TABLE public.lawyer_profiles DROP COLUMN show_contact_to_clients")
    op.execute("RESET ROLE")
