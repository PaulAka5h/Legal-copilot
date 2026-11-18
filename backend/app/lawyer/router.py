from fastapi import APIRouter

from app.auth.dependencies import LawyerDep, UserSessionDep
from app.errors import problem_responses
from app.lawyer.repository import (
    get_lawyer_overview,
    list_lawyer_activity,
    list_lawyer_team,
)
from app.lawyer.schemas import (
    LawyerActivityResponse,
    LawyerOverviewResponse,
    LawyerTeamMemberResponse,
)

router = APIRouter(
    prefix="/api/v1/lawyer",
    tags=["lawyer-dashboard"],
)


@router.get(
    "/dashboard/overview",
    summary="Get lawyer dashboard overview",
    description="Returns organization-scoped case and client counts.",
    response_model=LawyerOverviewResponse,
    responses=problem_responses(401, 403, 503),
)
async def dashboard_overview(
    user: LawyerDep,
    session: UserSessionDep,
) -> LawyerOverviewResponse:
    return await get_lawyer_overview(session, acting_user_id=user.id)


@router.get(
    "/dashboard/activity",
    summary="List recent lawyer activity",
    description="Returns recent audit activity visible to the lawyer organization.",
    response_model=list[LawyerActivityResponse],
    responses=problem_responses(401, 403, 503),
)
async def dashboard_activity(
    user: LawyerDep,
    session: UserSessionDep,
) -> list[LawyerActivityResponse]:
    return await list_lawyer_activity(session, acting_user_id=user.id)


@router.get(
    "/team",
    summary="List lawyer team",
    description="Lists active members in the acting lawyer organization.",
    response_model=list[LawyerTeamMemberResponse],
    responses=problem_responses(401, 403, 503),
)
async def team(
    user: LawyerDep,
    session: UserSessionDep,
) -> list[LawyerTeamMemberResponse]:
    return await list_lawyer_team(session, acting_user_id=user.id)
