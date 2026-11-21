"""Lawyer-set client passwords with a forced change at first sign-in.

- users.must_change_password: true for client accounts whose password a lawyer
  set or reset. The API refuses everything except password change and logout
  until the client picks a new password.
- app.lookup_session returns the flag so every request can enforce it.
- app.set_client_temporary_password: a lawyer of the client's organization
  creates the client's login (first time) or resets it (revokes the client's
  sessions and unused reset tokens). Only the Argon2 hash reaches the database.
- app.complete_password_change: the signed-in user sets a new password, clears
  the flag, and revokes their other sessions.
- app.accept_case_invitation also accepts an invitation for a profile whose
  lawyer-created login still has its temporary password, so invitations stay
  optional. It revokes that login's earlier sessions and never overwrites a
  password the client chose.
"""

from alembic import op

revision = "0020_client_password_onboarding"
down_revision = "0019_owner_policy_no_bypass"
branch_labels = None
depends_on = None

_ACCEPT_SIGNATURE = "bytea,text,bytea,timestamptz,inet,text,text"

# {linked_profile} is the branch for a profile that already has a login.
_ACCEPT_INVITATION = """
CREATE OR REPLACE FUNCTION app.accept_case_invitation(
  p_token_hash bytea,
  p_password_hash text,
  p_session_hash bytea,
  p_expires_at timestamptz,
  p_ip inet,
  p_user_agent text,
  p_request_id text
)
RETURNS TABLE (
  result_user_id uuid,
  result_session_id uuid,
  result_email text,
  result_full_name text
)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  v_invitation public.case_invitations%ROWTYPE;
  v_profile public.client_profiles%ROWTYPE;
  v_new_user_id uuid;
  v_new_session_id uuid;
BEGIN
  SELECT i.* INTO v_invitation
  FROM public.case_invitations i
  WHERE i.token_hash = p_token_hash
    AND i.accepted_at IS NULL
    AND i.revoked_at IS NULL
    AND i.expires_at > clock_timestamp()
  FOR UPDATE;
  IF v_invitation.id IS NULL THEN
    RETURN;
  END IF;
  SELECT cp.* INTO v_profile
  FROM public.client_profiles cp
  WHERE cp.id = v_invitation.client_profile_id;
  IF v_profile.id IS NULL THEN
    RETURN;
  END IF;
  IF v_profile.email IS NULL
     OR v_profile.email::text != v_invitation.email::text THEN
    RETURN;
  END IF;
  {linked_profile}
  SELECT u.id INTO v_new_user_id
  FROM public.users u
  WHERE u.email = v_invitation.email::public.citext
    AND u.role = 'client'
  LIMIT 1;
  IF v_new_user_id IS NOT NULL AND EXISTS (
    SELECT 1 FROM public.client_profiles cp
    WHERE cp.user_id = v_new_user_id
      AND cp.id != v_profile.id
  ) THEN
    RETURN;
  END IF;
  IF v_new_user_id IS NULL THEN
    v_new_user_id := gen_random_uuid();
    INSERT INTO public.users
      (id, email, password_hash, role, status, full_name)
    VALUES (
      v_new_user_id,
      v_invitation.email,
      p_password_hash,
      'client',
      'active',
      v_profile.display_name
    );
  ELSE
    UPDATE public.users
    SET password_hash = p_password_hash,
        status = 'active',
        failed_logins = 0,
        locked_until = NULL,
        updated_at = clock_timestamp()
    WHERE id = v_new_user_id;
  END IF;
  UPDATE public.client_profiles
  SET user_id = v_new_user_id
  WHERE id = v_profile.id;
  INSERT INTO public.case_members
    (case_id, organization_id, user_id, client_profile_id,
     role, permissions, granted_by)
  VALUES (
    v_invitation.case_id,
    v_invitation.organization_id,
    v_new_user_id,
    v_profile.id,
    'client',
    '{}'::jsonb,
    v_invitation.created_by
  )
  ON CONFLICT (case_id, user_id) DO UPDATE
    SET status = 'active',
        client_profile_id = EXCLUDED.client_profile_id,
        revoked_at = NULL,
        granted_by = EXCLUDED.granted_by;
  UPDATE public.case_invitations
  SET accepted_at = clock_timestamp()
  WHERE id = v_invitation.id;
  v_new_session_id := gen_random_uuid();
  INSERT INTO public.sessions
    (id, user_id, token_hash, expires_at, ip, user_agent)
  VALUES (
    v_new_session_id, v_new_user_id, p_session_hash, p_expires_at,
    p_ip, p_user_agent
  );
  RETURN QUERY
    SELECT v_new_user_id,
           v_new_session_id,
           v_invitation.email::text,
           v_profile.display_name;
END
$$
"""

# 0006 behaviour: a profile with a login cannot accept an invitation.
_LINKED_PROFILE_REFUSED = """
  IF v_profile.user_id IS NOT NULL THEN
    RETURN;
  END IF;
"""

# The lawyer created this client's login and the client has not chosen a
# password yet (must_change_password). The invitation sets the client's own
# password, revokes every earlier session (including any opened with the
# temporary password), and adds the case. A client who already chose a password
# is refused, as before: the invitation never overwrites it.
_LINKED_PROFILE_ACCEPTED = """
  IF v_profile.user_id IS NOT NULL THEN
    UPDATE public.users
    SET password_hash = p_password_hash,
        must_change_password = false,
        status = 'active',
        failed_logins = 0,
        locked_until = NULL,
        updated_at = clock_timestamp()
    WHERE id = v_profile.user_id
      AND role = 'client'
      AND must_change_password
      AND email = v_invitation.email::public.citext
    RETURNING id INTO v_new_user_id;
    IF v_new_user_id IS NULL THEN
      RETURN;
    END IF;
    UPDATE public.sessions
    SET revoked_at = clock_timestamp()
    WHERE user_id = v_new_user_id AND revoked_at IS NULL;
    UPDATE public.password_reset_tokens
    SET used_at = clock_timestamp()
    WHERE user_id = v_new_user_id AND used_at IS NULL;
    INSERT INTO public.case_members
      (case_id, organization_id, user_id, client_profile_id,
       role, permissions, granted_by)
    VALUES (
      v_invitation.case_id,
      v_invitation.organization_id,
      v_new_user_id,
      v_profile.id,
      'client',
      '{}'::jsonb,
      v_invitation.created_by
    )
    ON CONFLICT (case_id, user_id) DO UPDATE
      SET status = 'active',
          client_profile_id = EXCLUDED.client_profile_id,
          revoked_at = NULL,
          granted_by = EXCLUDED.granted_by;
    UPDATE public.case_invitations
    SET accepted_at = clock_timestamp()
    WHERE id = v_invitation.id;
    v_new_session_id := gen_random_uuid();
    INSERT INTO public.sessions
      (id, user_id, token_hash, expires_at, ip, user_agent)
    VALUES (
      v_new_session_id, v_new_user_id, p_session_hash, p_expires_at,
      p_ip, p_user_agent
    );
    RETURN QUERY
      SELECT v_new_user_id,
             v_new_session_id,
             v_invitation.email::text,
             v_profile.display_name;
    RETURN;
  END IF;
"""


def _lookup_session(with_flag: bool) -> str:
    flag_column = ",\n          must_change_password boolean" if with_flag else ""
    flag_value = ", u.must_change_password" if with_flag else ""
    return f"""
        CREATE FUNCTION app.lookup_session(p_token_hash bytea)
        RETURNS TABLE (
          session_id uuid,
          user_id uuid,
          user_role text,
          user_status text,
          expires_at timestamptz,
          last_seen_at timestamptz,
          revoked_at timestamptz,
          email text,
          full_name text,
          preferred_language text{flag_column}
        )
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT s.id, s.user_id, u.role, u.status, s.expires_at,
                 s.last_seen_at, s.revoked_at, u.email::text,
                 u.full_name, u.preferred_language{flag_value}
          FROM public.sessions AS s
          JOIN public.users AS u ON u.id = s.user_id
          WHERE s.token_hash = p_token_hash
        $$
        """


def _replace_lookup_session(with_flag: bool) -> None:
    op.execute("DROP FUNCTION app.lookup_session(bytea)")
    op.execute(_lookup_session(with_flag))
    op.execute("REVOKE ALL ON FUNCTION app.lookup_session(bytea) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.lookup_session(bytea) TO app_user")


def _replace_accept_invitation(linked_profile: str) -> None:
    op.execute(_ACCEPT_INVITATION.replace("{linked_profile}", linked_profile))
    op.execute(f"REVOKE ALL ON FUNCTION app.accept_case_invitation({_ACCEPT_SIGNATURE}) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION app.accept_case_invitation({_ACCEPT_SIGNATURE}) TO app_user")


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        "ALTER TABLE public.users "
        "ADD COLUMN must_change_password boolean NOT NULL DEFAULT false"
    )
    _replace_lookup_session(with_flag=True)
    op.execute(
        """
        CREATE FUNCTION app.set_client_temporary_password(
          p_client_profile_id uuid,
          p_password_hash text
        )
        RETURNS TABLE (
          result_status text,
          result_user_id uuid,
          result_email text,
          result_revoked_sessions integer
        )
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
          v_profile public.client_profiles%ROWTYPE;
          v_user_id uuid;
          v_revoked integer := 0;
        BEGIN
          IF app.current_user_id() IS NULL OR p_password_hash IS NULL THEN
            RETURN QUERY SELECT 'not_found'::text, NULL::uuid, NULL::text, 0;
            RETURN;
          END IF;
          SELECT cp.* INTO v_profile
          FROM public.client_profiles cp
          WHERE cp.id = p_client_profile_id
          FOR UPDATE;
          IF v_profile.id IS NULL OR NOT app.is_org_lawyer(v_profile.organization_id) THEN
            RETURN QUERY SELECT 'not_found'::text, NULL::uuid, NULL::text, 0;
            RETURN;
          END IF;

          IF v_profile.user_id IS NULL THEN
            IF v_profile.email IS NULL THEN
              RETURN QUERY SELECT 'no_email'::text, NULL::uuid, NULL::text, 0;
              RETURN;
            END IF;
            IF EXISTS (SELECT 1 FROM public.users u WHERE u.email = v_profile.email) THEN
              RETURN QUERY SELECT 'email_taken'::text, NULL::uuid, NULL::text, 0;
              RETURN;
            END IF;
            v_user_id := gen_random_uuid();
            INSERT INTO public.users
              (id, email, password_hash, role, status, full_name,
               must_change_password)
            VALUES (v_user_id, v_profile.email, p_password_hash, 'client',
                    'active', v_profile.display_name, true);
            UPDATE public.client_profiles SET user_id = v_user_id
            WHERE id = v_profile.id;
            RETURN QUERY SELECT 'created'::text, v_user_id, v_profile.email::text, 0;
            RETURN;
          END IF;

          UPDATE public.users
          SET password_hash = p_password_hash,
              must_change_password = true,
              failed_logins = 0,
              locked_until = NULL,
              updated_at = clock_timestamp()
          WHERE id = v_profile.user_id
            AND role = 'client'
          RETURNING id INTO v_user_id;
          IF v_user_id IS NULL THEN
            RETURN QUERY SELECT 'not_found'::text, NULL::uuid, NULL::text, 0;
            RETURN;
          END IF;
          UPDATE public.sessions
          SET revoked_at = clock_timestamp()
          WHERE user_id = v_user_id AND revoked_at IS NULL;
          GET DIAGNOSTICS v_revoked = ROW_COUNT;
          UPDATE public.password_reset_tokens
          SET used_at = clock_timestamp()
          WHERE user_id = v_user_id AND used_at IS NULL;
          RETURN QUERY
            SELECT 'reset'::text, v_user_id,
                   (SELECT u.email::text FROM public.users u WHERE u.id = v_user_id),
                   v_revoked;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION app.complete_password_change(
          p_password_hash text,
          p_keep_session_id uuid
        )
        RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
          v_user_id uuid := app.current_user_id();
          v_revoked integer;
        BEGIN
          IF v_user_id IS NULL OR p_password_hash IS NULL THEN
            RETURN NULL;
          END IF;
          UPDATE public.users
          SET password_hash = p_password_hash,
              must_change_password = false,
              updated_at = clock_timestamp()
          WHERE id = v_user_id;
          UPDATE public.sessions
          SET revoked_at = clock_timestamp()
          WHERE user_id = v_user_id
            AND revoked_at IS NULL
            AND id IS DISTINCT FROM p_keep_session_id;
          GET DIAGNOSTICS v_revoked = ROW_COUNT;
          RETURN v_revoked;
        END
        $$
        """
    )
    for signature in (
        "set_client_temporary_password(uuid, text)",
        "complete_password_change(text, uuid)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION app.{signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{signature} TO app_user")
    _replace_accept_invitation(_LINKED_PROFILE_ACCEPTED)
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    _replace_accept_invitation(_LINKED_PROFILE_REFUSED)
    op.execute("DROP FUNCTION app.complete_password_change(text, uuid)")
    op.execute("DROP FUNCTION app.set_client_temporary_password(uuid, text)")
    _replace_lookup_session(with_flag=False)
    op.execute("ALTER TABLE public.users DROP COLUMN must_change_password")
    op.execute("RESET ROLE")
