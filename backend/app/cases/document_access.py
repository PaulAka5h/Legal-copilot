"""Authorization contract for case document endpoints (Dev 1, Phase 3).

Backend Dev 2 owns the document routes (TRD §3.2). They must authorize through
these helpers so every document endpoint behaves the same way:

| Route (TRD)                                   | Use                                   |
|-----------------------------------------------|---------------------------------------|
| ``GET  /cases/{case_id}/documents``           | ``DocumentReadDep``                   |
| ``POST /cases/{case_id}/documents``           | ``DocumentWriteDep``                  |
| ``GET  /documents/{id}``, ``/pages``, ``/download-url`` | ``authorize_document_read``  |
| ``PATCH /documents/{id}/pages/{n}``, ``POST /reprocess`` | ``authorize_document_write`` |
| ``DELETE /documents/{id}``                    | ``authorize_document_write`` + ``check_document_delete`` |

Rules: an unknown document, a document in another tenant's case and a case the
caller is not an active member of all return the same 404. Writes need
``can_upload`` (lead lawyers hold every permission) and an open case (409 when
closed). Each call writes one of ``DOCUMENT_AUDIT_ACTIONS`` with the case_id.
For ``/documents/{id}`` routes, resolve ``case_id`` with
``SELECT case_id FROM public.documents WHERE id = :id`` under the user's RLS
session first, and treat "no row" as 404.
"""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import UserSessionDep
from app.cases.dependencies import (
    CASE_NOT_FOUND,
    CaseAccessDep,
    authorize_case_write,
    ensure_case_open,
    require_case_permission,
)
from app.cases.repository import get_case_membership
from app.cases.schemas import CaseAccess

UPLOAD_PERMISSION = "can_upload"
MIN_DELETE_REASON_LENGTH = 10
DOCUMENT_AUDIT_ACTIONS = {
    "upload": "document.upload",
    "view": "document.view",
    "download": "document.download",
    "correct": "document.correct",
    "delete": "document.delete",
}

DocumentReadDep = CaseAccessDep


async def get_document_write_access(
    case_id: Annotated[UUID, Path(description="Case ID")],
    case_access: CaseAccessDep,
    session: UserSessionDep,
) -> CaseAccess:
    require_case_permission(case_access, UPLOAD_PERMISSION)
    await ensure_case_open(session, case_id)
    return case_access


DocumentWriteDep = Annotated[CaseAccess, Depends(get_document_write_access)]


async def authorize_document_read(
    session: AsyncSession,
    *,
    acting_user_id: UUID,
    case_id: UUID | None,
) -> CaseAccess:
    """``case_id`` is the resolved owner case of the document, or None if not found."""
    access = (
        await get_case_membership(session, acting_user_id=acting_user_id, case_id=case_id)
        if case_id is not None
        else None
    )
    if access is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=CASE_NOT_FOUND)
    return access


async def authorize_document_write(
    session: AsyncSession,
    *,
    acting_user_id: UUID,
    case_id: UUID | None,
) -> CaseAccess:
    if case_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=CASE_NOT_FOUND)
    return await authorize_case_write(
        session, acting_user_id=acting_user_id, case_id=case_id, permission=UPLOAD_PERMISSION
    )


def check_document_delete(reason: str | None, retention_until: date | None, today: date) -> str:
    """Delete needs a reason and must not cut a retention hold short. Returns the reason."""
    cleaned = (reason or "").strip()
    if len(cleaned) < MIN_DELETE_REASON_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"A deletion reason of at least {MIN_DELETE_REASON_LENGTH} characters is required.",
        )
    if retention_until is not None and retention_until > today:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The document is under a retention hold and cannot be deleted yet.",
        )
    return cleaned
