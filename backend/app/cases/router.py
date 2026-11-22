from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

from app.auth.dependencies import (
    LawyerDep,
    UserSessionDep,
    require_lawyer,
    require_same_origin,
    request_ip,
)
from app.auth.repository import write_audit_event
from app.auth.security import hash_token, new_session_token
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
    set_case_archived,
    create_case_invitation,
    revoke_case_invitation,
)
from app.cases.schemas import (
    AuditLogResponse,
    CaseCreate,
    CaseMemberCreate,
    CaseMemberResponse,
    CasePatch,
    CaseResponse,
    InvitationCreate,
    InvitationResponse,
    CaseCloseRequest,
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
    description=(
        "Lists cases with an active membership for the authenticated lawyer. "
        "Archived cases are hidden unless include_archived is true."
    ),
    response_model=list[CaseResponse],
    responses=problem_responses(401, 403, 422, 503),
)
async def list_cases_endpoint(
    user: LawyerDep,
    session: UserSessionDep,
    include_archived: Annotated[
        bool, Query(description="Also return archived cases")
    ] = False,
) -> list[CaseResponse]:
    return await list_cases(
        session, acting_user_id=user.id, include_archived=include_archived
    )


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
    description=(
        "Updates case details (title, type, court, status open/on_hold, ...) for a "
        "lawyer with case-edit permission. Closed and archived cases are read-only."
    ),
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
    existing = await get_case(
        session,
        acting_user_id=user.id,
        case_id=case_id,
    )
    if existing is None:
        raise HTTPException(status_code=404, detail="Case was not found.")
    if existing.status == "closed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Closed cases are read-only.",
        )
    if existing.archived_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Archived cases are read-only. Restore the case first.",
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
        details={
            "fields": sorted(payload.model_fields_set),
            **(
                {"status_from": existing.status, "status_to": case.status}
                if "status" in payload.model_fields_set
                else {}
            ),
        },
    )
    return case


async def _set_archived(
    request: Request,
    *,
    case_id: UUID,
    user,
    case_access,
    session,
    archived: bool,
) -> CaseResponse:
    if case_access.role != "lead_lawyer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the lead lawyer can archive or restore a case.",
        )
    case = await set_case_archived(
        session, acting_user_id=user.id, case_id=case_id, archived=archived
    )
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Case is already archived." if archived else "Case is not archived.",
        )
    await write_audit_event(
        session,
        action="case.archived" if archived else "case.restored",
        actor_user_id=user.id,
        actor_role=user.role,
        object_type="case",
        object_id=case.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
        organization_id=case.organization_id,
        case_id=case.id,
    )
    return case


@router.post(
    "/{case_id}/archive",
    summary="Archive a case",
    description=(
        "Soft delete: hides the case from lists by default. Nothing is deleted; "
        "documents, hearings, analyses and history are kept and the case can be "
        "restored. Lead lawyer only. Audit-logged."
    ),
    response_model=CaseResponse,
    responses=problem_responses(401, 403, 404, 409, 422, 503),
    dependencies=[Depends(require_same_origin)],
)
async def archive_case_endpoint(
    request: Request,
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: LawyerDep,
    case_access: CaseAccessDep,
    session: UserSessionDep,
) -> CaseResponse:
    return await _set_archived(
        request, case_id=case_id, user=user, case_access=case_access,
        session=session, archived=True,
    )


@router.post(
    "/{case_id}/restore",
    summary="Restore an archived case",
    description="Shows an archived case in lists again. Lead lawyer only. Audit-logged.",
    response_model=CaseResponse,
    responses=problem_responses(401, 403, 404, 409, 422, 503),
    dependencies=[Depends(require_same_origin)],
)
async def restore_case_endpoint(
    request: Request,
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: LawyerDep,
    case_access: CaseAccessDep,
    session: UserSessionDep,
) -> CaseResponse:
    return await _set_archived(
        request, case_id=case_id, user=user, case_access=case_access,
        session=session, archived=False,
    )


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


@router.post(
    "/{case_id}/invitations",
    summary="Create a client invitation",
    description="Revokes prior unused invitations and creates a hashed single-use token.",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
    responses=problem_responses(400, 401, 403, 404, 409, 422, 503),
    dependencies=[Depends(require_same_origin)],
)
async def create_invitation_endpoint(
    request: Request,
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: LawyerDep,
    case_access: CaseAccessDep,
    session: UserSessionDep,
    payload: Annotated[InvitationCreate, Body(description="Client invitation")],
) -> InvitationResponse:
    if request.app.state.settings.app_env == "production":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Invitation email delivery is not configured.",
        )
    if not (
        case_access.role == "lead_lawyer"
        or case_access.permissions.get("can_manage_members", False)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Case member management permission is required.",
        )
    token = new_session_token()
    expires_at = datetime.now(UTC) + timedelta(hours=48)
    invitation = await create_case_invitation(
        session,
        acting_user_id=user.id,
        case_id=case_id,
        payload=payload,
        token_hash=hash_token(token),
        expires_at=expires_at,
    )
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client profile or email is not available for this case.",
        )
    if request.app.state.settings.app_env != "production":
        invitation.development_token = token
    await write_audit_event(
        session,
        action="case.invitation_created",
        actor_user_id=user.id,
        actor_role=user.role,
        object_type="case_invitation",
        object_id=invitation.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
        case_id=case_id,
        details={"client_profile_id": str(invitation.client_profile_id)},
    )
    return invitation


@router.post(
    "/{case_id}/close",
    summary="Close a case",
    description="Marks a case closed and removes client-visible access.",
    response_model=CaseResponse,
    responses=problem_responses(401, 403, 404, 409, 422, 503),
    dependencies=[Depends(require_same_origin)],
)
async def close_case_endpoint(
    request: Request,
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: LawyerDep,
    case_access: CaseAccessDep,
    session: UserSessionDep,
    payload: Annotated[CaseCloseRequest, Body(description="Closure reason")],
) -> CaseResponse:
    if not (
        case_access.role == "lead_lawyer"
        or case_access.permissions.get("can_close_case", False)
    ):
        raise HTTPException(
            status_code=403,
            detail="Case close permission is required.",
        )
    row = (
        await session.execute(
            text(
                """
                UPDATE public.cases
                SET status = 'closed',
                    closed_at = now(),
                    closed_by = :user_id,
                    updated_at = now()
                WHERE id = :case_id
                  AND status != 'closed'
                RETURNING id
                """
            ),
            {"case_id": case_id, "user_id": user.id},
        )
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Case was not found or already closed.")
    case = await get_case(session, acting_user_id=user.id, case_id=case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case was not found.")
    await write_audit_event(
        session,
        action="case.closed",
        actor_user_id=user.id,
        actor_role=user.role,
        object_type="case",
        object_id=case.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
        organization_id=case.organization_id,
        case_id=case.id,
        details={"reason": payload.reason} if payload.reason else {},
    )
    return case


@router.post(
    "/{case_id}/reopen",
    summary="Reopen a case",
    description="Restores lawyer access and published client-visible data.",
    response_model=CaseResponse,
    responses=problem_responses(401, 403, 404, 409, 422, 503),
    dependencies=[Depends(require_same_origin)],
)
async def reopen_case_endpoint(
    request: Request,
    case_id: Annotated[UUID, Path(description="Case ID")],
    user: LawyerDep,
    case_access: CaseAccessDep,
    session: UserSessionDep,
) -> CaseResponse:
    if not (
        case_access.role == "lead_lawyer"
        or case_access.permissions.get("can_close_case", False)
    ):
        raise HTTPException(status_code=403, detail="Case reopen permission is required.")
    row = (
        await session.execute(
            text(
                """
                UPDATE public.cases
                SET status = 'open',
                    closed_at = NULL,
                    closed_by = NULL,
                    updated_at = now()
                WHERE id = :case_id
                  AND status = 'closed'
                RETURNING id
                """
            ),
            {"case_id": case_id},
        )
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Case was not found or already open.")
    case = await get_case(session, acting_user_id=user.id, case_id=case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case was not found.")
    await write_audit_event(
        session,
        action="case.reopened",
        actor_user_id=user.id,
        actor_role=user.role,
        object_type="case",
        object_id=case.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
        organization_id=case.organization_id,
        case_id=case.id,
    )
    return case


@router.delete(
    "/{case_id}/invitations/{invitation_id}",
    summary="Revoke a client invitation",
    description="Revokes an unused client invitation immediately.",
    response_model=InvitationResponse,
    responses=problem_responses(401, 403, 404, 422, 503),
    dependencies=[Depends(require_same_origin)],
)
async def revoke_invitation_endpoint(
    request: Request,
    case_id: Annotated[UUID, Path(description="Case ID")],
    invitation_id: Annotated[UUID, Path(description="Invitation ID")],
    user: LawyerDep,
    case_access: CaseAccessDep,
    session: UserSessionDep,
) -> InvitationResponse:
    if not (
        case_access.role == "lead_lawyer"
        or case_access.permissions.get("can_manage_members", False)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Case member management permission is required.",
        )
    invitation = await revoke_case_invitation(
        session,
        case_id=case_id,
        invitation_id=invitation_id,
    )
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation was not found.",
        )
    await write_audit_event(
        session,
        action="case.invitation_revoked",
        actor_user_id=user.id,
        actor_role=user.role,
        object_type="case_invitation",
        object_id=invitation.id,
        ip_address=request_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
        case_id=case_id,
        details={"client_profile_id": str(invitation.client_profile_id)},
    )
    return invitation
