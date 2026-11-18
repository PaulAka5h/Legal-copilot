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
from app.cases.dependencies import CaseAccessDep
from app.cases.repository import (
    add_case_member,
    create_case,
    get_case,
    list_case_audit,
    list_case_members,
    list_cases,
    patch_case,
    revoke_case_member,
)
from app.cases.schemas import (
    AuditLogResponse,
    CaseCreate,
    CaseMemberCreate,
    CaseMemberResponse,
    CasePatch,
    CaseResponse,
)
from app.errors import problem_responses

router = APIRouter(
    prefix="/api/v1/cases",
    tags=["cases"],
    dependencies=[Depends(require_lawyer)],
)


@router.get(
    "",
    summary="List cases",
    description="Lists cases with an active membership for the authenticated lawyer.",
    response_model=list[CaseResponse],
    responses=problem_responses(401, 403, 503),
)
async def list_cases_endpoint(
    user: LawyerDep,
    session: UserSessionDep,
) -> list[CaseResponse]:
    return await list_cases(session, acting_user_id=user.id)


@router.post(
    "",
    summary="Create a case",
    description=(
        "Creates a case, lead-lawyer membership, and default stages atomically. "
        "The lawyer must have exactly one active organization membership."
    ),
    response_model=CaseResponse,
    status_code=status.HTTP_201_CREATED,
    responses=problem_responses(401, 403, 404, 409, 422, 503),
    dependencies=[Depends(require_same_origin)],
)
async def create_case_endpoint(
    request: Request,
    user: LawyerDep,
    session: UserSessionDep,
    payload: Annotated[CaseCreate, Body(description="Case details")],
) -> CaseResponse:
    try:
        case = await create_case(
            session,
            acting_user_id=user.id,
            payload=payload,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Case conflicts with existing data.",
        ) from exc
    await write_audit_event(
        session,
        action="case.created",
        actor_user_id=user.id,
        actor_role=user.role,
        object_type="case",
        object_id=case.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
        organization_id=case.organization_id,
        case_id=case.id,
        details={"fields": sorted(payload.model_fields_set)},
    )
    return case


@router.get(
    "/{case_id}",
    summary="Get a case",
    description="Returns a case only when the lawyer has active case membership.",
    response_model=CaseResponse,
    responses=problem_responses(401, 403, 404, 422, 503),
)
async def get_case_endpoint(
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: LawyerDep,
    session: UserSessionDep,
    case_access: CaseAccessDep,
) -> CaseResponse:
    case = await get_case(
        session,
        acting_user_id=user.id,
        case_id=case_access.case_id,
    )
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case was not found.",
        )
    return case


@router.patch(
    "/{case_id}",
    summary="Update a case",
    description="Updates case details for a lawyer with case-edit permission.",
    response_model=CaseResponse,
    responses=problem_responses(401, 403, 404, 409, 422, 503),
    dependencies=[Depends(require_same_origin)],
)
async def patch_case_endpoint(
    request: Request,
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: LawyerDep,
    session: UserSessionDep,
    case_access: CaseAccessDep,
    payload: Annotated[CasePatch, Body(description="Case fields to update")],
) -> CaseResponse:
    if not (
        case_access.role == "lead_lawyer"
        or case_access.permissions.get("can_edit_case", False)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Case edit permission is required.",
        )
    try:
        case = await patch_case(
            session,
            acting_user_id=user.id,
            case_id=case_id,
            payload=payload,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Case conflicts with existing data.",
        ) from exc
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case was not found.",
        )
    await write_audit_event(
        session,
        action="case.updated",
        actor_user_id=user.id,
        actor_role=user.role,
        object_type="case",
        object_id=case.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
        organization_id=case.organization_id,
        case_id=case.id,
        details={"fields": sorted(payload.model_fields_set)},
    )
    return case


@router.get(
    "/{case_id}/members",
    summary="List case members",
    description="Lists active and read-only members visible to this case.",
    response_model=list[CaseMemberResponse],
    responses=problem_responses(401, 403, 404, 422, 503),
)
async def list_case_members_endpoint(
    case_id: Annotated[UUID, Path(description="Case ID")],
    case_access: CaseAccessDep,
    session: UserSessionDep,
) -> list[CaseMemberResponse]:
    return await list_case_members(session, case_id=case_access.case_id)


@router.post(
    "/{case_id}/members",
    summary="Add or update a case member",
    description="Adds an organization lawyer or assistant to an active case.",
    response_model=CaseMemberResponse,
    status_code=status.HTTP_201_CREATED,
    responses=problem_responses(400, 401, 403, 404, 409, 422, 503),
    dependencies=[Depends(require_same_origin)],
)
async def add_case_member_endpoint(
    request: Request,
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: LawyerDep,
    case_access: CaseAccessDep,
    session: UserSessionDep,
    payload: Annotated[CaseMemberCreate, Body(description="Case member")],
) -> CaseMemberResponse:
    if not (
        case_access.role == "lead_lawyer"
        or case_access.permissions.get("can_manage_members", False)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Case member management permission is required.",
        )
    member = await add_case_member(
        session,
        acting_user_id=user.id,
        case_id=case_id,
        payload=payload,
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case was not found.",
        )
    await write_audit_event(
        session,
        action="case.member_added",
        actor_user_id=user.id,
        actor_role=user.role,
        object_type="case_member",
        object_id=member.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
        case_id=case_id,
        details={"member_user_id": str(member.user_id), "role": member.role},
    )
    return member


@router.delete(
    "/{case_id}/members/{member_id}",
    summary="Remove a case member",
    description="Revokes a non-lead case member; access ends on the next request.",
    response_model=CaseMemberResponse,
    responses=problem_responses(401, 403, 404, 422, 503),
    dependencies=[Depends(require_same_origin)],
)
async def revoke_case_member_endpoint(
    request: Request,
    case_id: Annotated[UUID, Path(description="Case ID")],
    member_id: Annotated[UUID, Path(description="Case member ID")],
    user: LawyerDep,
    case_access: CaseAccessDep,
    session: UserSessionDep,
) -> CaseMemberResponse:
    if not (
        case_access.role == "lead_lawyer"
        or case_access.permissions.get("can_manage_members", False)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Case member management permission is required.",
        )
    member = await revoke_case_member(
        session,
        case_id=case_id,
        member_id=member_id,
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case member was not found.",
        )
    await write_audit_event(
        session,
        action="case.member_revoked",
        actor_user_id=user.id,
        actor_role=user.role,
        object_type="case_member",
        object_id=member.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
        case_id=case_id,
        details={"member_user_id": str(member.user_id)},
    )
    return member


@router.get(
    "/{case_id}/audit",
    summary="List case audit events",
    description="Returns the most recent audit events visible to this case member.",
    response_model=list[AuditLogResponse],
    responses=problem_responses(401, 403, 404, 422, 503),
)
async def list_case_audit_endpoint(
    case_id: Annotated[UUID, Path(description="Case ID")],
    case_access: CaseAccessDep,
    session: UserSessionDep,
) -> list[AuditLogResponse]:
    return await list_case_audit(session, case_id=case_access.case_id)
