from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request, status
from sqlalchemy import text

from app.auth.dependencies import LawyerDep, UserSessionDep, require_lawyer, require_same_origin
from app.auth.repository import write_audit_event
from app.auth.dependencies import request_ip
from app.cases.dependencies import CaseAccessDep
from app.cases.schemas import (
    ClientTaskCreate,
    ClientUpdateCreate,
    ClientUpdateResponse,
    SharedDocumentCreate,
    VisibilityPatch,
)
from app.errors import problem_responses

router = APIRouter(
    prefix="/api/v1",
    tags=["client-visibility"],
)


@router.post(
    "/cases/{case_id}/client-updates",
    summary="Create a client-visible update draft",
    description="Creates a draft update; it is never visible until published.",
    response_model=ClientUpdateResponse,
    status_code=status.HTTP_201_CREATED,
    responses=problem_responses(401, 403, 404, 422, 503),
)
async def create_client_update(
    request: Request,
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: LawyerDep,
    session: UserSessionDep,
    case_access: CaseAccessDep,
    payload: Annotated[ClientUpdateCreate, Body(description="Client update draft")],
) -> ClientUpdateResponse:
    row = (
        await session.execute(
            text(
                """
                INSERT INTO public.client_visible_updates
                  (case_id, organization_id, title, body, language)
                SELECT c.id, c.organization_id, :title, :body, :language
                FROM public.cases c
                WHERE c.id = :case_id
                RETURNING id, case_id, version, title, body, language, status
                """
            ),
            {
                "case_id": case_id,
                "title": payload.title,
                "body": payload.body,
                "language": payload.language,
            },
        )
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Case was not found.")
    await write_audit_event(
        session,
        action="client_update.drafted",
        actor_user_id=user.id,
        actor_role=user.role,
        object_type="client_update",
        object_id=row["id"],
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
        case_id=case_id,
    )
    return ClientUpdateResponse.model_validate(dict(row))


@router.post(
    "/client-updates/{update_id}/publish",
    summary="Publish a client-visible update",
    description=(
        "Lawyer approval: makes an update visible to active client members of an "
        "open case. Audit-logged."
    ),
    response_model=ClientUpdateResponse,
    responses=problem_responses(401, 403, 404, 422, 503),
    dependencies=[Depends(require_same_origin)],
)
async def publish_client_update(
    request: Request,
    update_id: Annotated[UUID, Path(description="Update ID")],
    user: LawyerDep,
    session: UserSessionDep,
) -> ClientUpdateResponse:
    row = (
        await session.execute(
            text(
                """
                UPDATE public.client_visible_updates
                SET status = 'published',
                    approved_by = :user_id,
                    published_at = now(),
                    withdrawn_at = NULL
                WHERE id = :update_id
                RETURNING id, case_id, version, title, body, language, status
                """
            ),
            {"update_id": update_id, "user_id": user.id},
        )
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Update was not found.")
    await write_audit_event(
        session,
        action="client_update.published",
        actor_user_id=user.id,
        actor_role=user.role,
        object_type="client_update",
        object_id=row["id"],
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
        case_id=row["case_id"],
    )
    return ClientUpdateResponse.model_validate(dict(row))


@router.post(
    "/cases/{case_id}/shared-documents",
    summary="Share a document with a client",
    description="Shares an existing document UUID with active client membership.",
    response_model=dict,
    responses=problem_responses(401, 403, 404, 422, 503),
)
async def share_document(
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: LawyerDep,
    session: UserSessionDep,
    case_access: CaseAccessDep,
    payload: Annotated[SharedDocumentCreate, Body(description="Shared document")],
) -> dict:
    row = (
        await session.execute(
            text(
                """
                INSERT INTO public.client_shared_documents
                  (case_id, organization_id, document_id, display_name, shared_by)
                SELECT c.id, c.organization_id, :document_id, :display_name, :user_id
                FROM public.cases c
                WHERE c.id = :case_id
                ON CONFLICT (case_id, document_id) DO UPDATE
                  SET display_name = EXCLUDED.display_name,
                      revoked_at = NULL,
                      shared_at = now()
                RETURNING id
                """
            ),
            {
                "case_id": case_id,
                "document_id": payload.document_id,
                "display_name": payload.display_name,
                "user_id": user.id,
            },
        )
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Case was not found.")
    return {"id": str(row["id"]), "document_id": str(payload.document_id)}


@router.post(
    "/cases/{case_id}/tasks",
    summary="Create a client task",
    description="Creates a task that can be visible to the client.",
    response_model=dict,
    responses=problem_responses(401, 403, 404, 422, 503),
)
async def create_client_task(
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: LawyerDep,
    session: UserSessionDep,
    case_access: CaseAccessDep,
    payload: Annotated[ClientTaskCreate, Body(description="Client task")],
) -> dict:
    row = (
        await session.execute(
            text(
                """
                INSERT INTO public.client_tasks
                  (case_id, organization_id, title, description, due_date, created_by)
                SELECT c.id, c.organization_id, :title, :description, :due_date, :user_id
                FROM public.cases c
                WHERE c.id = :case_id
                RETURNING id
                """
            ),
            {
                "case_id": case_id,
                "title": payload.title,
                "description": payload.description,
                "due_date": payload.due_date,
                "user_id": user.id,
            },
        )
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Case was not found.")
    return {"id": str(row["id"])}


@router.patch(
    "/cases/{case_id}/client-visibility",
    summary="Patch client-visible case fields",
    description="Updates lawyer-controlled status and stage labels.",
    response_model=VisibilityPatch,
    responses=problem_responses(401, 403, 404, 422, 503),
)
async def patch_client_visibility(
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: LawyerDep,
    session: UserSessionDep,
    case_access: CaseAccessDep,
    payload: Annotated[VisibilityPatch, Body(description="Visibility fields")],
) -> VisibilityPatch:
    result = await session.execute(
        text(
            """
            INSERT INTO public.client_visible_case_fields
              (case_id, organization_id, status_label, stage_label,
               plain_explanation, updated_by)
            SELECT c.id, c.organization_id, :status_label, :stage_label,
                   :plain_explanation, :user_id
            FROM public.cases c
            WHERE c.id = :case_id
            ON CONFLICT (case_id) DO UPDATE
              SET status_label = COALESCE(EXCLUDED.status_label,
                                          public.client_visible_case_fields.status_label),
                  stage_label = COALESCE(EXCLUDED.stage_label,
                                         public.client_visible_case_fields.stage_label),
                  plain_explanation = COALESCE(EXCLUDED.plain_explanation,
                                               public.client_visible_case_fields.plain_explanation),
                  updated_by = EXCLUDED.updated_by,
                  updated_at = now()
            RETURNING status_label, stage_label, plain_explanation
            """
        ),
        {
            "case_id": case_id,
            "status_label": payload.status_label,
            "stage_label": payload.stage_label,
            "plain_explanation": payload.plain_explanation,
            "user_id": user.id,
        },
    )
    row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Case was not found.")
    return VisibilityPatch.model_validate(dict(row))


@router.post(
    "/client-updates/{update_id}/withdraw",
    summary="Withdraw a published client update",
    description="Immediately removes an update from the client view.",
    response_model=ClientUpdateResponse,
    responses=problem_responses(401, 403, 404, 422, 503),
)
async def withdraw_client_update(
    update_id: Annotated[UUID, Path(description="Update ID")],
    user: LawyerDep,
    session: UserSessionDep,
) -> ClientUpdateResponse:
    row = (
        await session.execute(
            text(
                """
                UPDATE public.client_visible_updates
                SET status = 'withdrawn', withdrawn_at = now()
                WHERE id = :update_id
                RETURNING id, case_id, version, title, body, language, status
                """
            ),
            {"update_id": update_id},
        )
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Update was not found.")
    return ClientUpdateResponse.model_validate(dict(row))
