"""Lawyer: share case documents with the client (default off, revocable, audit-logged).

Sharing inserts or re-activates a client_shared_documents row; revoking sets
revoked_at (nothing is deleted, history is kept). The client lists and downloads
only shared, unrevoked documents of open cases they are a member of.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.auth.dependencies import LawyerDep, UserSessionDep, request_ip, require_lawyer, require_same_origin
from app.auth.repository import write_audit_event
from app.cases.dependencies import CaseAccessDep, require_case_permission
from app.errors import problem_responses

router = APIRouter(prefix="/api/v1/cases/{case_id}/shared-documents", tags=["client-visibility"],
                   dependencies=[Depends(require_lawyer)])


class SharedDocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    document_id: UUID
    display_name: str | None = Field(default=None, min_length=1, max_length=300,
                                     description="Name the client sees; defaults to the original filename")


class SharedDocumentOut(BaseModel):
    document_id: UUID
    display_name: str
    shared_at: datetime
    revoked_at: datetime | None = Field(description="Set when sharing was turned off; the client no longer sees it")


_FIELDS = "document_id, display_name, shared_at, revoked_at"


async def _audit(session, request: Request, user, action: str, case_id: UUID, document_id: UUID) -> None:
    await write_audit_event(
        session, action=action, actor_user_id=user.id, actor_role=user.role, object_type="document",
        object_id=document_id, case_id=case_id, ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("", summary="List documents shared with the client",
            description="Every share record of the case, including revoked ones (history).",
            response_model=list[SharedDocumentOut], responses=problem_responses(401, 403, 404, 422))
async def list_shared(access: CaseAccessDep, session: UserSessionDep) -> list[SharedDocumentOut]:
    rows = await session.execute(text(f"SELECT {_FIELDS} FROM public.client_shared_documents "
                                      "WHERE case_id = :c ORDER BY shared_at DESC"), {"c": access.case_id})
    return [SharedDocumentOut.model_validate(dict(row)) for row in rows.mappings()]


@router.post(
    "",
    summary="Share a document with the client",
    description=("Shares one document of this case with its client members (open cases only). The document must "
                 "belong to the case and not be deleted or infected. Requires can_edit_case. Audit-logged."),
    response_model=SharedDocumentOut,
    status_code=status.HTTP_201_CREATED,
    responses=problem_responses(401, 403, 404, 409, 422),
    dependencies=[Depends(require_same_origin)],
)
async def share(request: Request, access: CaseAccessDep, user: LawyerDep, session: UserSessionDep,
                payload: Annotated[SharedDocumentCreate, Body(description="Document to share")]) -> SharedDocumentOut:
    require_case_permission(access, "can_edit_case")
    document = (await session.execute(text(
        """
        SELECT d.original_filename, d.organization_id, c.status
        FROM public.documents d JOIN public.cases c ON c.id = d.case_id
        WHERE d.id = :d AND d.case_id = :c AND d.deleted_at IS NULL
          AND d.processing_status <> 'deleted' AND d.scan_status <> 'infected'
        """), {"d": payload.document_id, "c": access.case_id})).mappings().one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document was not found in this case.")
    if document["status"] == "closed":
        raise HTTPException(status_code=409, detail="Closed cases are read-only.")
    row = (await session.execute(text(
        f"""
        INSERT INTO public.client_shared_documents (case_id, organization_id, document_id, display_name, shared_by)
        VALUES (:c, :o, :d, :name, :u)
        ON CONFLICT (case_id, document_id) DO UPDATE
          SET display_name = EXCLUDED.display_name, revoked_at = NULL, shared_at = now(),
              shared_by = EXCLUDED.shared_by
        RETURNING {_FIELDS}
        """), {"c": access.case_id, "o": document["organization_id"], "d": payload.document_id,
               "name": payload.display_name or document["original_filename"], "u": user.id})).mappings().one()
    await _audit(session, request, user, "client_document.shared", access.case_id, payload.document_id)
    return SharedDocumentOut.model_validate(dict(row))


@router.delete(
    "/{document_id}",
    summary="Stop sharing a document with the client",
    description="Revokes the share at once (the record is kept with revoked_at). Requires can_edit_case. Audit-logged.",
    response_model=SharedDocumentOut,
    responses=problem_responses(401, 403, 404, 422),
    dependencies=[Depends(require_same_origin)],
)
async def revoke(request: Request, access: CaseAccessDep, user: LawyerDep, session: UserSessionDep,
                 document_id: Annotated[UUID, Path(description="Document ID")]) -> SharedDocumentOut:
    require_case_permission(access, "can_edit_case")
    row = (await session.execute(text(
        f"""
        UPDATE public.client_shared_documents SET revoked_at = now()
        WHERE case_id = :c AND document_id = :d AND revoked_at IS NULL
        RETURNING {_FIELDS}
        """), {"c": access.case_id, "d": document_id})).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="The document is not shared.")
    await _audit(session, request, user, "client_document.unshared", access.case_id, document_id)
    return SharedDocumentOut.model_validate(dict(row))
