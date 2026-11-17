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
    create_case,
    get_case,
    list_cases,
    patch_case,
)
from app.cases.schemas import CaseCreate, CasePatch, CaseResponse
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
