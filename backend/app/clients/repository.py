from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine.row import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.schemas import ClientCreate, ClientPatch, ClientResponse
from app.tenancy import resolve_actor_organization

_CLIENT_FIELDS = """
    cp.id, cp.organization_id, cp.display_name, cp.email::text AS email,
    cp.phone, cp.address, cp.created_at,
    (cp.user_id IS NOT NULL) AS has_account
"""


async def list_clients(
    session: AsyncSession,
    *,
    acting_user_id: UUID,
) -> list[ClientResponse]:
    result = await session.execute(
        text(
            f"""
            SELECT {_CLIENT_FIELDS}
            FROM public.client_profiles AS cp
            WHERE EXISTS (
              SELECT 1 FROM public.organization_members AS om
              WHERE om.organization_id = cp.organization_id
                AND om.user_id = :acting_user_id
                AND om.status = 'active'
                AND om.org_role IN ('owner', 'lawyer'))
            ORDER BY cp.created_at DESC, cp.id
            """
        ),
        {"acting_user_id": acting_user_id},
    )
    return [
        ClientResponse.model_validate(dict(row))
        for row in result.mappings().all()
    ]


async def get_client(
    session: AsyncSession,
    *,
    acting_user_id: UUID,
    client_id: UUID,
) -> ClientResponse | None:
    result = await session.execute(
        text(
            f"""
            SELECT {_CLIENT_FIELDS}
            FROM public.client_profiles AS cp
            WHERE cp.id = :client_id
              AND EXISTS (
                SELECT 1 FROM public.organization_members AS om
                WHERE om.organization_id = cp.organization_id
                  AND om.user_id = :acting_user_id
                  AND om.status = 'active'
                  AND om.org_role IN ('owner', 'lawyer'))
            """
        ),
        {"acting_user_id": acting_user_id, "client_id": client_id},
    )
    row = result.mappings().one_or_none()
    return ClientResponse.model_validate(dict(row)) if row is not None else None


async def create_client(
    session: AsyncSession,
    *,
    acting_user_id: UUID,
    payload: ClientCreate,
) -> ClientResponse:
    organization_id = await resolve_actor_organization(session, acting_user_id)
    result = await session.execute(
        text(
            f"""
            INSERT INTO public.client_profiles AS cp
              (id, organization_id, display_name, email, phone, address,
               created_by)
            VALUES
              (:id, :organization_id, :display_name, :email, :phone, :address,
               :acting_user_id)
            RETURNING {_CLIENT_FIELDS}
            """
        ),
        {
            "id": uuid4(),
            "organization_id": organization_id,
            "acting_user_id": acting_user_id,
            **payload.model_dump(exclude={"password", "case_id"}),
        },
    )
    return ClientResponse.model_validate(dict(result.mappings().one()))


async def patch_client(
    session: AsyncSession,
    *,
    acting_user_id: UUID,
    client_id: UUID,
    payload: ClientPatch,
) -> ClientResponse | None:
    updates = payload.model_dump(exclude_unset=True)
    columns = {
        "display_name": "display_name",
        "email": "email",
        "phone": "phone",
        "address": "address",
    }
    assignments = ", ".join(f"{columns[field]} = :{field}" for field in updates)
    result = await session.execute(
        text(
            f"""
            UPDATE public.client_profiles AS cp
            SET {assignments}
            WHERE cp.id = :client_id
              AND EXISTS (
                SELECT 1 FROM public.organization_members AS om
                WHERE om.organization_id = cp.organization_id
                  AND om.user_id = :acting_user_id
                  AND om.status = 'active'
                  AND om.org_role IN ('owner', 'lawyer'))
            RETURNING {_CLIENT_FIELDS}
            """
        ),
        {
            **updates,
            "acting_user_id": acting_user_id,
            "client_id": client_id,
        },
    )
    row = result.mappings().one_or_none()
    return ClientResponse.model_validate(dict(row)) if row is not None else None


async def set_client_temporary_password(
    session: AsyncSession,
    *,
    client_id: UUID,
    password_hash: str,
) -> RowMapping:
    """Create the client's login or reset it; only the hash reaches the database.

    result_status: created | reset | not_found | no_email | email_taken.
    """
    result = await session.execute(
        text(
            "SELECT * FROM app.set_client_temporary_password("
            ":client_id, :password_hash)"
        ),
        {"client_id": client_id, "password_hash": password_hash},
    )
    return result.mappings().one()


async def link_client_to_case(
    session: AsyncSession,
    *,
    acting_user_id: UUID,
    case_id: UUID,
    client_id: UUID,
) -> UUID | None:
    """Add the client as a member of a case the acting user leads.

    Returns the case_members ID, or None when the case is not one the acting
    user leads, is closed, or belongs to another organization.
    """
    eligible = await session.execute(
        text(
            """
            SELECT c.organization_id, cp.user_id
            FROM public.cases AS c
            JOIN public.case_members AS cm
              ON cm.case_id = c.id
             AND cm.user_id = :acting_user_id
             AND cm.status = 'active'
             AND cm.role = 'lead_lawyer'
            JOIN public.client_profiles AS cp
              ON cp.id = :client_id
             AND cp.organization_id = c.organization_id
             AND cp.user_id IS NOT NULL
            WHERE c.id = :case_id
              AND c.status != 'closed'
            """
        ),
        {"acting_user_id": acting_user_id, "case_id": case_id, "client_id": client_id},
    )
    row = eligible.mappings().one_or_none()
    if row is None:
        return None
    return await session.scalar(
        text(
            """
            INSERT INTO public.case_members
              (case_id, organization_id, user_id, client_profile_id, role,
               permissions, granted_by)
            VALUES
              (:case_id, :organization_id, :user_id, :client_id, 'client',
               '{}'::jsonb, :acting_user_id)
            ON CONFLICT (case_id, user_id) DO UPDATE
              SET status = 'active', revoked_at = NULL
            RETURNING id
            """
        ),
        {
            "case_id": case_id,
            "organization_id": row["organization_id"],
            "user_id": row["user_id"],
            "client_id": client_id,
            "acting_user_id": acting_user_id,
        },
    )
