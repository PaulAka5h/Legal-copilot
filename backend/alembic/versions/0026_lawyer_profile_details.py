"""Lawyer profile details, profile photo and per-field client visibility.

New nullable columns on public.lawyer_profiles (bar_enrollment_no, courts and
practice_areas already exist since 0001):
- years_experience, office_address, languages, bio, public_phone, public_email
- avatar_id: the current photo's object id. Objects live at
  users/{user_id}/avatar/{avatar_id}-{512|96}.webp and are only served through
  authorized API endpoints (no public bucket URLs).
- client_visible_fields: which fields the lawyer shows on their clients' contact
  card. NULL means the default (photo, firm, phone). The name is always shown.
  Rows where 0025's show_contact_to_clients was false become {photo}, so nothing
  the lawyer hid becomes visible.

app.client_case_lawyer_contact is replaced: it returns every card field, each one
NULL unless the lawyer allowed it, plus the avatar id when the photo is allowed and the lawyer's user id (used by
the API to build the photo's storage key; never returned to the client).
Still SECURITY DEFINER, still limited to client members of an open case (Rule 8).

Revision ID: 0026_lawyer_profile_details
Revises: 0025_client_docs_lawyer_contact
Create Date: 2026-11-23
"""

from alembic import op

revision = "0026_lawyer_profile_details"
down_revision = "0025_client_docs_lawyer_contact"
branch_labels = None
depends_on = None

CONTACT = "app.client_case_lawyer_contact(uuid)"
NEW_COLUMNS = ("years_experience", "office_address", "languages", "bio", "public_phone", "public_email",
               "client_visible_fields", "avatar_id")

OLD_CONTACT = """
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

NEW_CONTACT = """
CREATE FUNCTION app.client_case_lawyer_contact(p_case uuid)
RETURNS TABLE (lawyer_user_id uuid, full_name text, avatar_id uuid, firm text, phone text, email text,
               bar_enrollment_no text, courts text[], practice_areas text[], years_experience smallint,
               office_address text, languages text[], bio text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
  WITH lead AS (
    SELECT u.id AS lawyer_user_id, u.full_name, u.phone AS account_phone, o.name AS organization_name, lp.*,
           COALESCE(lp.client_visible_fields, ARRAY['photo', 'firm', 'phone']) AS visible
    FROM public.cases c
    JOIN public.case_members m
      ON m.case_id = c.id AND m.role = 'lead_lawyer' AND m.status = 'active'
    JOIN public.users u ON u.id = m.user_id
    JOIN public.organizations o ON o.id = c.organization_id
    LEFT JOIN public.lawyer_profiles lp ON lp.user_id = u.id
    WHERE c.id = p_case
      AND c.status = 'open'
      AND app.is_client_member(p_case)
    LIMIT 1
  )
  SELECT lawyer_user_id, full_name,
         CASE WHEN 'photo' = ANY (visible) THEN avatar_id END,
         CASE WHEN 'firm' = ANY (visible)
              THEN COALESCE(NULLIF(btrim(chamber_name), ''), NULLIF(btrim(organization_name), '')) END,
         CASE WHEN 'phone' = ANY (visible)
              THEN COALESCE(NULLIF(btrim(public_phone), ''), NULLIF(btrim(account_phone), '')) END,
         CASE WHEN 'email' = ANY (visible) THEN NULLIF(btrim(public_email), '') END,
         CASE WHEN 'bar_enrollment_no' = ANY (visible) THEN NULLIF(btrim(bar_enrollment_no), '') END,
         CASE WHEN 'courts' = ANY (visible) THEN courts END,
         CASE WHEN 'practice_areas' = ANY (visible) THEN practice_areas END,
         CASE WHEN 'years_experience' = ANY (visible) THEN years_experience END,
         CASE WHEN 'office_address' = ANY (visible) THEN NULLIF(btrim(office_address), '') END,
         CASE WHEN 'languages' = ANY (visible) THEN languages END,
         CASE WHEN 'bio' = ANY (visible) THEN NULLIF(btrim(bio), '') END
  FROM lead
$$
"""


def _grant_contact() -> None:
    op.execute(f"REVOKE ALL ON FUNCTION {CONTACT} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {CONTACT} TO app_user")


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        """
        ALTER TABLE public.lawyer_profiles
          ADD COLUMN years_experience smallint
            CHECK (years_experience BETWEEN 0 AND 80),
          ADD COLUMN office_address text CHECK (char_length(office_address) <= 300),
          ADD COLUMN languages text[],
          ADD COLUMN bio text CHECK (char_length(bio) <= 500),
          ADD COLUMN public_phone text CHECK (public_phone ~ '^\\+8801[3-9][0-9]{8}$'),
          ADD COLUMN public_email text CHECK (char_length(public_email) <= 254),
          ADD COLUMN client_visible_fields text[],
          ADD COLUMN avatar_id uuid,
          ADD COLUMN avatar_updated_at timestamptz
        """
    )
    op.execute(
        "UPDATE public.lawyer_profiles SET client_visible_fields = ARRAY['photo'] "
        "WHERE show_contact_to_clients = false"
    )
    op.execute(
        f"GRANT UPDATE ({', '.join(NEW_COLUMNS)}, avatar_updated_at) ON public.lawyer_profiles TO app_user"
    )
    op.execute(f"DROP FUNCTION {CONTACT}")
    op.execute(NEW_CONTACT)
    _grant_contact()
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(f"DROP FUNCTION {CONTACT}")
    op.execute(OLD_CONTACT)
    _grant_contact()
    op.execute(
        "ALTER TABLE public.lawyer_profiles "
        + ", ".join(f"DROP COLUMN {c}" for c in (*NEW_COLUMNS, "avatar_updated_at"))
    )
    op.execute("RESET ROLE")
