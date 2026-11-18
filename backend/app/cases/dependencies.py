from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Path, status

from app.auth.dependencies import LawyerDep, UserSessionDep
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
