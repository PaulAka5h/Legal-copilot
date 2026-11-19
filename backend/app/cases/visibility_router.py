"""Lawyer endpoints that publish data to the client portal.

Every write requires (in order): an authenticated lawyer session, active case
membership (404 otherwise), ``can_publish_updates`` or the lead-lawyer role (403),
and an open case (409). Each write is audited in the same transaction.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    LawyerDep,
    UserSessionDep,
    request_ip,
    require_same_origin_for_writes,
)
from app.auth.repository import write_audit_event
from app.auth.schemas import CurrentUser
from app.cases.dependencies import ClientVisibleWriteDep, authorize_client_visible_write
from app.cases.schemas import (
    ClientTaskCreate,
    ClientTaskCreatedResponse,
    ClientUpdateCreate,
    ClientUpdateResponse,
    SharedDocumentCreate,
    SharedDocumentResponse,
    VisibilityPatch,
)
from app.errors import problem_responses

router = APIRouter(
    prefix="/api/v1",
    tags=["client-visibility"],
    dependencies=[Depends(require_same_origin_for_writes)],
)

WRITE_ERRORS = problem_responses(401, 403, 404, 409, 422, 503)
UPDATE_NOT_FOUND = "Update was not found."
UPDATE_COLUMNS = "id, case_id, version, title, body, language, status"


async def _audit(
    session: AsyncSession,
    request: Request,
    user: CurrentUser,
    *,
    action: str,
    object_type: str,
    object_id: UUID,
    case_id: UUID,
) -> None:
    await write_audit_event(
        session,
        action=action,
        actor_user_id=user.id,
        actor_role=user.role,
        object_type=object_type,
        object_id=object_id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
        case_id=case_id,
    )


@router.post(
    "/cases/{case_id}/client-updates",
    summary="Create a client-visible update draft",
    description="Creates a draft update; it is never visible until published.",
    response_model=ClientUpdateResponse,
    status_code=status.HTTP_201_CREATED,
    responses=WRITE_ERRORS,
)
async def create_client_update(
    request: Request,
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: LawyerDep,
    session: UserSessionDep,
    access: ClientVisibleWriteDep,
    payload: Annotated[ClientUpdateCreate, Body(description="Client update draft")],
) -> ClientUpdateResponse:
    row = (
        await session.execute(
            text(
                f"""
                INSERT INTO public.client_visible_updates
                  (case_id, organization_id, title, body, language)
                SELECT c.id, c.organization_id, :title, :body, :language
                FROM public.cases c
                WHERE c.id = :case_id
                RETURNING {UPDATE_COLUMNS}
                """
            ),
            {
                "case_id": case_id,
                "title": payload.title,
                "body": payload.body,
                "language": payload.language,
            },
        )
    ).mappings().one()
    await _audit(
        session, request, user,
        action="client_update.drafted", object_type="client_update",
        object_id=row["id"], case_id=case_id,
    )
    return ClientUpdateResponse.model_validate(dict(row))


async def _set_update_status(
    request: Request,
    update_id: UUID,
    user: CurrentUser,
    session: AsyncSession,
    *,
    set_sql: str,
    action: str,
) -> ClientUpdateResponse:
    case_id = (
        await session.execute(
            text("SELECT case_id FROM public.client_visible_updates WHERE id = :update_id"),
            {"update_id": update_id},
        )
    ).scalar_one_or_none()
    if case_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=UPDATE_NOT_FOUND)
    await authorize_client_visible_write(session, acting_user_id=user.id, case_id=case_id)
    row = (
        await session.execute(
            text(
                f"""
                UPDATE public.client_visible_updates
                SET {set_sql}
                WHERE id = :update_id AND case_id = :case_id
                RETURNING {UPDATE_COLUMNS}
                """
            ),
            {"update_id": update_id, "case_id": case_id, "user_id": user.id},
        )
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=UPDATE_NOT_FOUND)
    await _audit(
        session, request, user,
        action=action, object_type="client_update", object_id=update_id, case_id=case_id,
    )
    return ClientUpdateResponse.model_validate(dict(row))


@router.post(
    "/client-updates/{update_id}/publish",
    summary="Publish a client-visible update",
    description=(
        "Makes an update visible to active client members. Requires case membership, "
        "the publish permission, and an open case."
    ),
    response_model=ClientUpdateResponse,
    responses=WRITE_ERRORS,
)
async def publish_client_update(
    request: Request,
    update_id: Annotated[UUID, Path(description="Update ID")],
    user: LawyerDep,
    session: UserSessionDep,
) -> ClientUpdateResponse:
    return await _set_update_status(
        request, update_id, user, session,
        set_sql="status = 'published', approved_by = :user_id, published_at = now(), withdrawn_at = NULL",
        action="client_update.published",
    )


@router.post(
    "/client-updates/{update_id}/withdraw",
    summary="Withdraw a published client update",
    description="Immediately removes an update from the client view.",
    response_model=ClientUpdateResponse,
    responses=WRITE_ERRORS,
)
async def withdraw_client_update(
    request: Request,
    update_id: Annotated[UUID, Path(description="Update ID")],
    user: LawyerDep,
    session: UserSessionDep,
) -> ClientUpdateResponse:
    return await _set_update_status(
        request, update_id, user, session,
        set_sql="status = 'withdrawn', withdrawn_at = now()",
        action="client_update.withdrawn",
    )


@router.post(
    "/cases/{case_id}/shared-documents",
    summary="Share a document with a client",
    description=(
        "Shares a document UUID with the case's active clients, or re-shares a "
        "previously revoked one. Document existence is not checked until the "
        "documents table exists (Dev 2)."
    ),
    response_model=SharedDocumentResponse,
    responses=WRITE_ERRORS,
)
async def share_document(
    request: Request,
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: LawyerDep,
    session: UserSessionDep,
    access: ClientVisibleWriteDep,
    payload: Annotated[SharedDocumentCreate, Body(description="Shared document")],
) -> SharedDocumentResponse:
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
                RETURNING id, case_id, document_id, display_name, shared_at
                """
            ),
            {
                "case_id": case_id,
                "document_id": payload.document_id,
                "display_name": payload.display_name,
                "user_id": user.id,
            },
        )
    ).mappings().one()
    await _audit(
        session, request, user,
        action="client_document.shared", object_type="shared_document",
        object_id=row["id"], case_id=case_id,
    )
    return SharedDocumentResponse.model_validate(dict(row))


@router.post(
    "/cases/{case_id}/tasks",
    summary="Create a client task",
    description="Creates a task that is visible to the case's active clients.",
    response_model=ClientTaskCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    responses=WRITE_ERRORS,
)
async def create_client_task(
    request: Request,
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: LawyerDep,
    session: UserSessionDep,
    access: ClientVisibleWriteDep,
    payload: Annotated[ClientTaskCreate, Body(description="Client task")],
) -> ClientTaskCreatedResponse:
    row = (
        await session.execute(
            text(
                """
                INSERT INTO public.client_tasks
                  (case_id, organization_id, title, description, due_date, created_by)
                SELECT c.id, c.organization_id, :title, :description, :due_date, :user_id
                FROM public.cases c
                WHERE c.id = :case_id
                RETURNING id, case_id, title, description, due_date, status
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
    ).mappings().one()
    await _audit(
        session, request, user,
        action="client_task.created", object_type="client_task",
        object_id=row["id"], case_id=case_id,
    )
    return ClientTaskCreatedResponse.model_validate(dict(row))


@router.patch(
    "/cases/{case_id}/client-visibility",
    summary="Patch client-visible case fields",
    description="Updates lawyer-controlled status and stage labels shown to the client.",
    response_model=VisibilityPatch,
    responses=WRITE_ERRORS,
)
async def patch_client_visibility(
    request: Request,
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: LawyerDep,
    session: UserSessionDep,
    access: ClientVisibleWriteDep,
    payload: Annotated[VisibilityPatch, Body(description="Visibility fields")],
) -> VisibilityPatch:
    row = (
        await session.execute(
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
    ).mappings().one()
    await _audit(
        session, request, user,
        action="client_visibility.updated", object_type="case",
        object_id=case_id, case_id=case_id,
    )
    return VisibilityPatch.model_validate(dict(row))
