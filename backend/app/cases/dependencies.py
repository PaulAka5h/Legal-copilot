from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Path, status

from app.auth.dependencies import LawyerDep, SessionFactoryDep, UserSessionDep
from app.database import user_transaction
from app.cases.repository import get_case_membership
from app.cases.schemas import CaseAccess


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
            detail="Case was not found.",
        )
    return access


CaseAccessDep = Annotated[CaseAccess, Depends(get_case_access)]


async def get_case_access_short(
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: LawyerDep,
    session_factory: SessionFactoryDep,
) -> CaseAccess:
    """Membership check in its own short transaction (no connection held for the request).

    Use on long-running routes (upload, OCR, AI runs) so one request never holds a
    pooled connection while doing slow work.
    """
    async with user_transaction(session_factory, user.id) as session:
        access = await get_case_membership(session, acting_user_id=user.id, case_id=case_id)
    if access is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case was not found.")
    return access


CaseAccessShortDep = Annotated[CaseAccess, Depends(get_case_access_short)]


def require_case_permission(access: CaseAccess, permission: str) -> None:
    """Lead lawyers have every case permission; others need the explicit flag."""
    if access.role == "lead_lawyer" or access.permissions.get(permission, False):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Case permission {permission} is required.")
