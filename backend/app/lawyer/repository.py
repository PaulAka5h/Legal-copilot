from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.lawyer.schemas import (
    LawyerActivityResponse,
    LawyerOverviewResponse,
    LawyerTeamMemberResponse,
)
from app.tenancy import resolve_actor_organization


async def get_lawyer_overview(
    session: AsyncSession,
    *,
    acting_user_id,
) -> LawyerOverviewResponse:
    organization_id = await resolve_actor_organization(session, acting_user_id)
    result = (
        await session.execute(
            text(
                """
                SELECT
                  count(*) FILTER (WHERE c.status = 'open') AS active_cases,
                  count(*) AS total_matters,
                  (SELECT count(*) FROM public.client_profiles cp
                   WHERE cp.organization_id = :organization_id) AS total_clients
                FROM public.cases c
                WHERE c.organization_id = :organization_id
                  AND c.archived_at IS NULL
                  AND EXISTS (
                    SELECT 1 FROM public.case_members cm
                    WHERE cm.case_id = c.id
                      AND cm.user_id = :acting_user_id
                      AND cm.status = 'active')
                """
            ),
            {
                "organization_id": organization_id,
                "acting_user_id": acting_user_id,
            },
        )
    ).mappings().one()
    return LawyerOverviewResponse(
        active_cases=int(result["active_cases"]),
        total_matters=int(result["total_matters"]),
        total_clients=int(result["total_clients"]),
        next_hearing=None,
    )


async def list_lawyer_activity(
    session: AsyncSession,
    *,
    acting_user_id,
) -> list[LawyerActivityResponse]:
    organization_id = await resolve_actor_organization(session, acting_user_id)
    result = await session.execute(
        text(
            """
            SELECT id::text, action, object_type, object_id, occurred_at
            FROM public.audit_logs
            WHERE organization_id = :organization_id
            ORDER BY occurred_at DESC, id DESC
            LIMIT 50
            """
        ),
        {"organization_id": organization_id},
    )
    return [
        LawyerActivityResponse.model_validate(dict(row))
        for row in result.mappings().all()
    ]


async def list_lawyer_team(
    session: AsyncSession,
    *,
    acting_user_id,
) -> list[LawyerTeamMemberResponse]:
    organization_id = await resolve_actor_organization(session, acting_user_id)
    result = await session.execute(
        text(
            """
            SELECT om.user_id, u.full_name, u.email::text, om.org_role
            FROM public.organization_members om
            JOIN public.users u ON u.id = om.user_id
            WHERE om.organization_id = :organization_id
              AND om.status = 'active'
            ORDER BY u.full_name, u.id
            """
        ),
        {"organization_id": organization_id},
    )
    return [
        LawyerTeamMemberResponse.model_validate(dict(row))
        for row in result.mappings().all()
    ]
