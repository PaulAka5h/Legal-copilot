from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import LawyerDep, UserSessionDep
from app.cases.repository import get_case_membership
from app.cases.schemas import CaseAccess

CASE_NOT_FOUND = "Case was not found."
PUBLISH_PERMISSION = "can_publish_updates"


async def get_case_access(
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: LawyerDep,
    session: UserSessionDep,
) -> CaseAccess:
    access = await get_case_membership(
        session,
        acting_user_id=user.id,
        case_id=case_id,
    )
    if access is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=CASE_NOT_FOUND,
        )
    return access


CaseAccessDep = Annotated[CaseAccess, Depends(get_case_access)]


def require_case_permission(access: CaseAccess, permission: str) -> None:
    """Lead lawyers hold every case permission; others need the explicit flag."""
    if access.role != "lead_lawyer" and not access.permissions.get(permission, False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Case permission is required for this action.",
        )


async def ensure_case_open(session: AsyncSession, case_id: UUID) -> None:
    case_status = (
        await session.execute(
            text("SELECT status FROM public.cases WHERE id = :case_id"),
            {"case_id": case_id},
        )
    ).scalar_one_or_none()
    if case_status is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=CASE_NOT_FOUND)
    if case_status == "closed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Closed cases are read-only.",
        )


async def authorize_case_write(
    session: AsyncSession,
    *,
    acting_user_id: UUID,
    case_id: UUID,
    permission: str,
) -> CaseAccess:
    """For routes whose path has no case_id: membership (404), ``permission`` (403),
    then open case (409). Resolve ``case_id`` from the resource under RLS first."""
    access = await get_case_membership(session, acting_user_id=acting_user_id, case_id=case_id)
    if access is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=CASE_NOT_FOUND)
    require_case_permission(access, permission)
    await ensure_case_open(session, case_id)
    return access


async def authorize_client_visible_write(
    session: AsyncSession,
    *,
    acting_user_id: UUID,
    case_id: UUID,
) -> CaseAccess:
    """Membership (404), ``can_publish_updates`` (403), then open case (409)."""
    return await authorize_case_write(
        session, acting_user_id=acting_user_id, case_id=case_id, permission=PUBLISH_PERMISSION
    )


async def get_client_visible_write_access(
    case_id: Annotated[UUID, Path(description="Case ID")],
    case_access: CaseAccessDep,
    session: UserSessionDep,
) -> CaseAccess:
    require_case_permission(case_access, PUBLISH_PERMISSION)
    await ensure_case_open(session, case_id)
    return case_access


ClientVisibleWriteDep = Annotated[CaseAccess, Depends(get_client_visible_write_access)]
