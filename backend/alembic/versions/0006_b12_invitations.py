"""Add constrained client-invitation acceptance."""

from alembic import op

revision = "0006_b12_invitations"
down_revision = "0005_b10_audit_writer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_case_invitation_active_profile
        ON public.case_invitations (case_id, client_profile_id)
        WHERE accepted_at IS NULL AND revoked_at IS NULL
        """
    )
    op.execute(
        """
        CREATE FUNCTION app.accept_case_invitation(
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
          IF v_profile.user_id IS NOT NULL THEN
            RETURN;
          END IF;
          IF v_profile.email IS NULL
             OR v_profile.email::text != v_invitation.email::text THEN
            RETURN;
          END IF;
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
    )
    op.execute(
        "REVOKE ALL ON FUNCTION app.accept_case_invitation("
        "bytea,text,bytea,timestamptz,inet,text,text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION app.accept_case_invitation("
        "bytea,text,bytea,timestamptz,inet,text,text) TO app_user"
    )
    op.execute("RESET ROLE")


def downgrade() -> None:
    op.execute("SET ROLE app_owner")
    op.execute(
        "DROP FUNCTION IF EXISTS app.accept_case_invitation("
        "bytea,text,bytea,timestamptz,inet,text,text)"
    )
    op.execute("DROP INDEX IF EXISTS public.uq_case_invitation_active_profile")
    op.execute("RESET ROLE")
