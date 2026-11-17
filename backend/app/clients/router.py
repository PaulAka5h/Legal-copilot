from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request, status
from sqlalchemy.exc import IntegrityError

from app.auth.dependencies import (
    LawyerDep,
    UserSessionDep,
    require_lawyer,
    require_same_origin,
    request_ip,
)
from app.auth.repository import write_audit_event
from app.clients.repository import (
    create_client,
    get_client,
    list_clients,
    patch_client,
)
from app.clients.schemas import ClientCreate, ClientPatch, ClientResponse
from app.errors import problem_responses

router = APIRouter(
    prefix="/api/v1/clients",
    tags=["clients"],
    dependencies=[Depends(require_lawyer)],
)


@router.get(
    "",
    summary="List clients",
    description="Lists client profiles in the lawyer's active organizations.",
    response_model=list[ClientResponse],
    responses=problem_responses(401, 403, 503),
)
async def list_clients_endpoint(
    user: LawyerDep,
    session: UserSessionDep,
) -> list[ClientResponse]:
    return await list_clients(session, acting_user_id=user.id)


@router.post(
    "",
    summary="Create a client profile",
    description="Creates a lawyer-managed client profile in the active organization.",
    response_model=ClientResponse,
    status_code=status.HTTP_201_CREATED,
    responses=problem_responses(401, 403, 404, 409, 422, 503),
    dependencies=[Depends(require_same_origin)],
)
async def create_client_endpoint(
    request: Request,
    user: LawyerDep,
    session: UserSessionDep,
    payload: Annotated[ClientCreate, Body(description="Client profile details")],
) -> ClientResponse:
    try:
        client = await create_client(
            session,
            acting_user_id=user.id,
            payload=payload,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Client profile conflicts with existing data.",
        ) from exc
    await write_audit_event(
        session,
        action="client.created",
        actor_user_id=user.id,
        actor_role=user.role,
        object_type="client_profile",
        object_id=client.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
        organization_id=client.organization_id,
        details={"fields": sorted(payload.model_fields_set)},
    )
    return client


@router.get(
    "/{client_id}",
    summary="Get a client profile",
    description="Returns a client profile only when it belongs to an active organization.",
    response_model=ClientResponse,
    responses=problem_responses(401, 403, 404, 422, 503),
)
async def get_client_endpoint(
    client_id: Annotated[UUID, Path(description="Client profile ID")],
    user: LawyerDep,
    session: UserSessionDep,
) -> ClientResponse:
    client = await get_client(
        session,
        acting_user_id=user.id,
        client_id=client_id,
    )
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client profile was not found.",
        )
    return client


@router.patch(
    "/{client_id}",
    summary="Update a client profile",
    description="Updates permitted lawyer-managed client profile fields.",
    response_model=ClientResponse,
    responses=problem_responses(401, 403, 404, 409, 422, 503),
    dependencies=[Depends(require_same_origin)],
)
async def patch_client_endpoint(
    request: Request,
    client_id: Annotated[UUID, Path(description="Client profile ID")],
    user: LawyerDep,
    session: UserSessionDep,
    payload: Annotated[ClientPatch, Body(description="Client profile changes")],
) -> ClientResponse:
    try:
        client = await patch_client(
            session,
            acting_user_id=user.id,
            client_id=client_id,
            payload=payload,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Client profile conflicts with existing data.",
        ) from exc
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client profile was not found.",
        )
    await write_audit_event(
        session,
        action="client.updated",
        actor_user_id=user.id,
        actor_role=user.role,
        object_type="client_profile",
        object_id=client.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
        organization_id=client.organization_id,
        details={"fields": sorted(payload.model_fields_set)},
    )
    return client
