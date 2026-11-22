"""Lawyer-edited hearing summary versions (append-only, Rule 6).

Version 1 is the AI draft the frontend builds from the reassessment. Each save
inserts version n+1 that supersedes version n; nothing is updated or deleted.
The client never reads this table (Rule 8): the client sees only the published
client update.
"""

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth.dependencies import LawyerDep, UserSessionDep, request_ip, require_same_origin
from app.auth.repository import write_audit_event
from app.cases.dependencies import CaseAccessDep
from app.errors import problem_responses
from app.hearing_updates.summary_schemas import SummaryVersionCreate, SummaryVersionOut

router = APIRouter(prefix="/api/v1/lawyer/cases/{case_id}/hearings/{hearing_id}", tags=["hearings"])

_FIELDS = "id, hearing_id, version, supersedes_id, sections, created_by, created_at"
HearingIdPath = Annotated[UUID, Path(description="Hearing ID")]


@router.get(
    "/summary-versions",
    summary="List edited summary versions",
    description="Lawyer-saved versions of the hearing summary, oldest first. Version 1 (the AI draft) is not stored.",
    response_model=list[SummaryVersionOut],
    responses=problem_responses(401, 403, 404, 422),
)
async def list_summary_versions(
    access: CaseAccessDep, session: UserSessionDep, hearing_id: HearingIdPath
) -> list[SummaryVersionOut]:
    rows = await session.execute(
        text(f"SELECT {_FIELDS} FROM public.hearing_summary_versions "
             "WHERE case_id = :c AND hearing_id = :h ORDER BY version"),
        {"c": access.case_id, "h": hearing_id},
    )
    return [SummaryVersionOut.model_validate(dict(row)) for row in rows.mappings()]


@router.post(
    "/summary-versions",
    summary="Save an edited summary version",
    description=(
        "Saves the lawyer's edit as a new version (never overwrites). base_version must be the latest "
        "version (1 when none was saved), otherwise 409: the summary changed since it was opened. "
        "Closed cases are read-only. Audit-logged."
    ),
    response_model=SummaryVersionOut,
    status_code=status.HTTP_201_CREATED,
    responses=problem_responses(401, 403, 404, 409, 422),
    dependencies=[Depends(require_same_origin)],
)
async def save_summary_version(
    request: Request,
    access: CaseAccessDep,
    user: LawyerDep,
    session: UserSessionDep,
    hearing_id: HearingIdPath,
    payload: Annotated[SummaryVersionCreate, Body(description="Edited sections and the version they are based on")],
) -> SummaryVersionOut:
    hearing = (await session.execute(
        text("SELECT h.organization_id, c.status FROM public.hearings h JOIN public.cases c ON c.id = h.case_id "
             "WHERE h.id = :h AND h.case_id = :c"),
        {"h": hearing_id, "c": access.case_id},
    )).mappings().one_or_none()
    if hearing is None:
        raise HTTPException(status_code=404, detail="Hearing was not found.")
    if hearing["status"] == "closed":
        raise HTTPException(status_code=409, detail="Closed cases are read-only.")
    latest = (await session.execute(
        text("SELECT id, version FROM public.hearing_summary_versions WHERE hearing_id = :h "
             "ORDER BY version DESC LIMIT 1"),
        {"h": hearing_id},
    )).mappings().one_or_none()
    latest_version = latest["version"] if latest else 1
    if payload.base_version != latest_version:
        raise HTTPException(status_code=409, detail="The summary changed since you opened it. Reload and edit again.")
    try:
        row = (await session.execute(
            text(f"""
                INSERT INTO public.hearing_summary_versions
                  (case_id, organization_id, hearing_id, version, supersedes_id, sections, created_by)
                VALUES (:c, :o, :h, :v, :sup, CAST(:sections AS jsonb), :u)
                RETURNING {_FIELDS}
            """),
            {"c": access.case_id, "o": hearing["organization_id"], "h": hearing_id, "v": latest_version + 1,
             "sup": latest["id"] if latest else None, "u": user.id,
             "sections": json.dumps([s.model_dump() for s in payload.sections], ensure_ascii=False)},
        )).mappings().one()
    except IntegrityError as error:  # a concurrent save took this version number
        raise HTTPException(status_code=409, detail="The summary changed since you opened it.") from error
    await write_audit_event(
        session, action="hearing_summary.version_saved", actor_user_id=user.id, actor_role=user.role,
        object_type="hearing_summary_version", object_id=row["id"], case_id=access.case_id,
        organization_id=hearing["organization_id"], ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
        details={"hearing_id": str(hearing_id), "version": row["version"]},
    )
    return SummaryVersionOut.model_validate(dict(row))
