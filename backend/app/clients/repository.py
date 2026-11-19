from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.schemas import ClientCreate, ClientPatch, ClientResponse
from app.tenancy import resolve_actor_organization

_CLIENT_FIELDS = """
    cp.id, cp.organization_id, cp.display_name, cp.email::text AS email,
    cp.phone, cp.address, cp.created_at
"""


async def list_clients(
    session: AsyncSession,
    *,
    acting_user_id: UUID,
    limit: int,
    after: tuple[datetime, UUID] | None = None,
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
              AND (CAST(:after_at AS timestamptz) IS NULL
                   OR (cp.created_at, cp.id) < (:after_at, :after_id))
            ORDER BY cp.created_at DESC, cp.id DESC
            LIMIT :limit
            """
        ),
        {
            "acting_user_id": acting_user_id,
            "limit": limit,
            "after_at": after[0] if after else None,
            "after_id": after[1] if after else None,
        },
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
            **payload.model_dump(),
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
