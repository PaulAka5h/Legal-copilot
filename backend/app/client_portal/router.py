from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request
from sqlalchemy import text

from app.auth.dependencies import ClientDep, UserSessionDep, require_same_origin_for_writes
from app.errors import problem_responses
from app.client_portal.schemas import (
    ClientCaseResponse,
    ClientDocumentResponse,
    ClientNotificationResponse,
    ClientHearingResponse,
    DownloadUrlResponse,
    ClientTaskResponse,
    ClientUpdateResponse,
)
from app.cases.schemas import ClientTaskPatch
from app.auth.repository import write_audit_event
from app.auth.dependencies import request_ip

router = APIRouter(
    prefix="/api/v1/client",
    tags=["client-portal"],
    dependencies=[Depends(require_same_origin_for_writes)],
)


@router.get(
    "/cases",
    summary="List open client cases",
    description="Lists only cases with active client membership.",
    response_model=list[ClientCaseResponse],
    responses=problem_responses(401, 403, 503),
)
async def list_client_cases(
    user: ClientDep,
    session: UserSessionDep,
) -> list[ClientCaseResponse]:
    result = await session.execute(
        text(
            """
            SELECT c.id, c.title, c.status, c.case_type, c.court
            FROM public.cases c
            JOIN public.case_members cm
              ON cm.case_id = c.id
             AND cm.user_id = :user_id
             AND cm.status = 'active'
             AND cm.role = 'client'
            WHERE c.status = 'open'
            ORDER BY c.updated_at DESC
            """
        ),
        {"user_id": user.id},
    )
    return [
        ClientCaseResponse.model_validate(dict(row))
        for row in result.mappings().all()
    ]


@router.get(
    "/cases/{case_id}/updates",
    summary="List published client updates",
    description="Returns published updates for an open client case only.",
    response_model=list[ClientUpdateResponse],
    responses=problem_responses(401, 403, 404, 422, 503),
)
async def list_client_updates(
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: ClientDep,
    session: UserSessionDep,
) -> list[ClientUpdateResponse]:
    result = await session.execute(
        text(
            """
            SELECT id, version, title, body, language, published_at
            FROM public.client_visible_updates
            WHERE case_id = :case_id AND status = 'published'
            ORDER BY published_at DESC, version DESC
            """
        ),
        {"case_id": case_id},
    )
    rows = result.mappings().all()
    if not rows:
        # RLS and membership determine whether this is a 404 or an empty result.
        access = await session.scalar(
            text(
                """
                SELECT EXISTS (
                  SELECT 1 FROM public.cases c
                  JOIN public.case_members cm ON cm.case_id = c.id
                  WHERE c.id = :case_id AND c.status = 'open'
                    AND cm.user_id = :user_id
                    AND cm.status = 'active' AND cm.role = 'client'
                )
                """
            ),
            {"case_id": case_id, "user_id": user.id},
        )
        if not access:
            raise HTTPException(status_code=404, detail="Case was not found.")
    return [
        ClientUpdateResponse.model_validate(dict(row))
        for row in rows
    ]


@router.get(
    "/cases/{case_id}/hearing",
    summary="Get next confirmed hearing",
    description="Returns the next confirmed hearing for an open client case.",
    response_model=ClientHearingResponse | None,
    responses=problem_responses(401, 403, 404, 422, 503),
)
async def client_hearing(
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: ClientDep,
    session: UserSessionDep,
) -> ClientHearingResponse | None:
    row = (
        await session.execute(
            text(
                """
                SELECT id, scheduled_at, purpose, court_room
                FROM public.hearings
                WHERE case_id = :case_id
                  AND date_status = 'confirmed'
                  AND scheduled_at >= now()
                ORDER BY scheduled_at
                LIMIT 1
                """
            ),
            {"case_id": case_id},
        )
    ).mappings().one_or_none()
    if row is None:
        return None
    return ClientHearingResponse.model_validate(dict(row))


@router.get(
    "/cases/{case_id}/tasks",
    summary="List client tasks",
    description="Lists tasks for an open client case.",
    response_model=list[ClientTaskResponse],
    responses=problem_responses(401, 403, 404, 422, 503),
)
async def client_tasks(
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: ClientDep,
    session: UserSessionDep,
) -> list[ClientTaskResponse]:
    result = await session.execute(
        text(
            """
            SELECT id, title, description, due_date::text, status
            FROM public.client_tasks
            WHERE case_id = :case_id
            ORDER BY due_date NULLS LAST, created_at
            """
        ),
        {"case_id": case_id},
    )
    return [
        ClientTaskResponse.model_validate(dict(row))
        for row in result.mappings().all()
    ]


@router.get(
    "/cases/{case_id}/documents",
    summary="List shared client documents",
    description="Lists currently shared documents for an open client case.",
    response_model=list[ClientDocumentResponse],
    responses=problem_responses(401, 403, 404, 422, 503),
)
async def client_documents(
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: ClientDep,
    session: UserSessionDep,
) -> list[ClientDocumentResponse]:
    result = await session.execute(
        text(
            """
            SELECT id, document_id, display_name, shared_at
            FROM public.client_shared_documents
            WHERE case_id = :case_id AND revoked_at IS NULL
            ORDER BY shared_at DESC
            """
        ),
        {"case_id": case_id},
    )
    return [
        ClientDocumentResponse.model_validate(dict(row))
        for row in result.mappings().all()
    ]

@router.patch(
    "/tasks/{task_id}",
    summary="Update a client task",
    description="Updates only the task status for a client-visible task.",
    response_model=ClientTaskResponse,
    responses=problem_responses(401, 403, 404, 422, 503),
)
async def patch_client_task(
    task_id: Annotated[UUID, Path(description="Task ID")],
    user: ClientDep,
    session: UserSessionDep,
    payload: Annotated[ClientTaskPatch, Body(description="Task status")],
) -> ClientTaskResponse:
    row = (
        await session.execute(
            text(
                """
                UPDATE public.client_tasks
                SET status = :status,
                    completed_at = CASE WHEN :status = 'done' THEN now() ELSE NULL END
                WHERE id = :task_id
                RETURNING id, title, description, due_date::text, status
                """
            ),
            {"task_id": task_id, "status": payload.status},
        )
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Task was not found.")
    return ClientTaskResponse.model_validate(dict(row))


@router.get(
    "/notifications",
    summary="List client notifications",
    description="Lists notifications belonging to the authenticated client.",
    response_model=list[ClientNotificationResponse],
    responses=problem_responses(401, 403, 503),
)
async def client_notifications(
    user: ClientDep,
    session: UserSessionDep,
) -> list[ClientNotificationResponse]:
    result = await session.execute(
        text(
            """
            SELECT id, kind, title, body, read_at, created_at
            FROM public.notifications
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT 100
            """
        ),
        {"user_id": user.id},
    )
    return [
        ClientNotificationResponse.model_validate(dict(row))
        for row in result.mappings().all()
    ]


@router.get(
    "/documents/{document_id}/download-url",
    summary="Get a client document download URL",
    description="Performs full authorization before returning the storage stub.",
    response_model=DownloadUrlResponse,
    responses=problem_responses(401, 403, 404, 422, 503),
)
async def client_document_download(
    request: Request,
    document_id: Annotated[UUID, Path(description="Document ID")],
    user: ClientDep,
    session: UserSessionDep,
) -> DownloadUrlResponse:
    row = (
        await session.execute(
            text(
                """
                SELECT id
                FROM public.client_shared_documents
                WHERE document_id = :document_id
                  AND revoked_at IS NULL
                """
            ),
            {"document_id": document_id},
        )
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Document was not found.")
    await write_audit_event(
        session,
        action="client.document_download_requested",
        actor_user_id=user.id,
        actor_role=user.role,
        object_type="shared_document",
        object_id=row["id"],
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
    )
    return DownloadUrlResponse(status="NOT_CONFIGURED")
