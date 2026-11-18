from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def resolve_actor_organization(
    session: AsyncSession,
    acting_user_id: UUID,
) -> UUID:
    result = await session.execute(
        text(
            """
            SELECT organization_id
            FROM public.organization_members
            WHERE user_id = :acting_user_id
              AND status = 'active'
              AND org_role IN ('owner', 'lawyer')
            ORDER BY organization_id
            LIMIT 2
            """
        ),
        {"acting_user_id": acting_user_id},
    )
    organization_ids = result.scalars().all()
    if not organization_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active organization membership was not found.",
        )
    if len(organization_ids) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization selection is required.",
        )
    return organization_ids[0]
