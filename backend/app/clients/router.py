import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request, Response, status
from sqlalchemy.exc import IntegrityError

from app.auth.dependencies import (
    LawyerDep,
    UserSessionDep,
    require_lawyer,
    require_same_origin,
    request_ip,
)
from app.auth.repository import write_audit_event
from app.auth.schemas import CurrentUser
from app.auth.security import generate_temporary_password, hash_password
from app.clients.repository import (
    create_client,
    get_client,
    link_client_to_case,
    list_clients,
    patch_client,
    set_client_temporary_password,
)
from app.clients.schemas import (
    ClientCreate,
    ClientCreatedResponse,
    ClientPasswordResetResponse,
    ClientPatch,
    ClientResponse,
)
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


def _audit(request: Request, user: CurrentUser):
    """Common audit fields for this request. Passwords are never passed in."""
    return {
        "actor_user_id": user.id,
        "actor_role": user.role,
        "ip_address": request_ip(request),
        "user_agent": request.headers.get("user-agent", "")[:512] or None,
        "request_id": getattr(request.state, "request_id", None),
    }


_EMAIL_TAKEN = "An account with this email already exists."


@router.post(
    "",
    summary="Create a client profile and portal login",
    description=(
        "Creates a lawyer-managed client profile in the active organization. When an "
        "email is given, it also creates the client's portal login: the lawyer's "
        "`password` (12+ characters) or, if empty, a generated 16-character one. "
        "The plain password is returned once in `temporary_password` and is never "
        "stored or logged; the client must change it at first sign-in "
        "(PASSWORD_CHANGE_REQUIRED). With `case_id`, the client is linked to that "
        "case at once (lead lawyer of an open case only), so no invitation is needed."
    ),
    response_model=ClientCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    responses=problem_responses(401, 403, 404, 409, 422, 503),
    dependencies=[Depends(require_same_origin)],
)
async def create_client_endpoint(
    request: Request,
    response: Response,
    user: LawyerDep,
    session: UserSessionDep,
    payload: Annotated[ClientCreate, Body(description="Client profile details")],
) -> ClientCreatedResponse:
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
        object_type="client_profile",
        object_id=client.id,
        organization_id=client.organization_id,
        details={"fields": sorted(payload.model_fields_set - {"password"})},
        **_audit(request, user),
    )
    response.headers["Cache-Control"] = "no-store"
    if client.email is None:
        return ClientCreatedResponse(
            **client.model_dump(), temporary_password=None, linked_case_id=None
        )

    temporary_password = payload.password or generate_temporary_password()
    password_hash = await asyncio.to_thread(hash_password, temporary_password)
    try:
        account = await set_client_temporary_password(
            session, client_id=client.id, password_hash=password_hash
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_EMAIL_TAKEN) from exc
    if account["result_status"] == "email_taken":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_EMAIL_TAKEN)
    if account["result_status"] != "created":
        raise RuntimeError("client login was not created")
    await write_audit_event(
        session,
        action="client.account_created",
        object_type="user",
        object_id=account["result_user_id"],
        organization_id=client.organization_id,
        details={
            "client_profile_id": str(client.id),
            "password_source": "lawyer" if payload.password else "generated",
        },
        **_audit(request, user),
    )

    if payload.case_id is not None:
        member_id = await link_client_to_case(
            session,
            acting_user_id=user.id,
            case_id=payload.case_id,
            client_id=client.id,
        )
        if member_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case was not found, is closed, or you are not its lead lawyer.",
            )
        await write_audit_event(
            session,
            action="case.client_linked",
            object_type="case_member",
            object_id=member_id,
            organization_id=client.organization_id,
            case_id=payload.case_id,
            details={"client_profile_id": str(client.id)},
            **_audit(request, user),
        )

    return ClientCreatedResponse(
        **{**client.model_dump(), "has_account": True},
        temporary_password=temporary_password,
        linked_case_id=payload.case_id,
    )


@router.post(
    "/{client_id}/password-reset",
    summary="Reset a client's portal password",
    description=(
        "Generates a new 16-character temporary password, signs the client out of "
        "every session, and requires a password change at next sign-in. Creates the "
        "login first if the client has an email but no login yet. The plain password "
        "is returned once and is never stored or logged."
    ),
    response_model=ClientPasswordResetResponse,
    responses=problem_responses(400, 401, 403, 404, 409, 422, 503),
    dependencies=[Depends(require_same_origin)],
)
async def reset_client_password_endpoint(
    request: Request,
    response: Response,
    client_id: Annotated[UUID, Path(description="Client profile ID")],
    user: LawyerDep,
    session: UserSessionDep,
) -> ClientPasswordResetResponse:
    temporary_password = generate_temporary_password()
    password_hash = await asyncio.to_thread(hash_password, temporary_password)
    try:
        result = await set_client_temporary_password(
            session, client_id=client_id, password_hash=password_hash
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_EMAIL_TAKEN) from exc
    outcome = result["result_status"]
    if outcome == "not_found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client profile was not found.",
        )
    if outcome == "no_email":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add an email to this client before setting a password.",
        )
    if outcome == "email_taken":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_EMAIL_TAKEN)
    client = await get_client(session, acting_user_id=user.id, client_id=client_id)
    await write_audit_event(
        session,
        action="client.account_created" if outcome == "created" else "client.password_reset",
        object_type="user",
        object_id=result["result_user_id"],
        organization_id=client.organization_id if client else None,
        details={
            "client_profile_id": str(client_id),
            "sessions_revoked": result["result_revoked_sessions"],
        },
        **_audit(request, user),
    )
    response.headers["Cache-Control"] = "no-store"
    return ClientPasswordResetResponse(
        client_id=client_id,
        email=result["result_email"],
        temporary_password=temporary_password,
        created_account=outcome == "created",
        sessions_revoked=result["result_revoked_sessions"],
    )


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
