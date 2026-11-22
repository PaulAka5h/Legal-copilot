"""Lawyer profile: account fields, professional details and client visibility.

Email is not editable here. Only an organization owner may rename the
organization. Every change is audit-logged with field names only (no values).
The photo has its own endpoints (app.lawyer.photo).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import LawyerDep, UserSessionDep, request_ip, require_same_origin
from app.auth.repository import write_audit_event
from app.errors import problem_responses
from app.lawyer.profile_schemas import DEFAULT_VISIBLE_FIELDS, LawyerProfilePatch, LawyerProfileResponse
from app.tenancy import resolve_actor_organization

router = APIRouter(prefix="/api/v1/lawyer", tags=["lawyer-profile"])

# Column names come from this fixed list only, never from the request.
PROFILE_COLUMNS = ("chamber_name", "bar_enrollment_no", "courts", "practice_areas", "years_experience",
                   "office_address", "languages", "bio", "public_phone", "public_email", "client_visible_fields")


async def _read_profile(session: AsyncSession, user_id: UUID) -> LawyerProfileResponse:
    organization_id = await resolve_actor_organization(session, user_id)
    row = (await session.execute(
        text(
            """
            SELECT u.full_name, u.email::text AS email, u.phone, u.preferred_language,
                   lp.chamber_name, o.name AS organization_name,
                   (om.org_role = 'owner') AS can_edit_organization,
                   lp.bar_enrollment_no, COALESCE(lp.courts, '{}') AS courts,
                   COALESCE(lp.practice_areas, '{}') AS practice_areas, lp.years_experience,
                   lp.office_address, COALESCE(lp.languages, '{}') AS languages, lp.bio,
                   lp.public_phone, lp.public_email, lp.client_visible_fields, lp.avatar_id AS photo_id
            FROM public.users u
            JOIN public.organization_members om
              ON om.user_id = u.id AND om.organization_id = :org AND om.status = 'active'
            JOIN public.organizations o ON o.id = om.organization_id
            LEFT JOIN public.lawyer_profiles lp ON lp.user_id = u.id
            WHERE u.id = :user_id
            """
        ),
        {"user_id": user_id, "org": organization_id},
    )).mappings().one()
    values = dict(row)
    if values["client_visible_fields"] is None:
        values["client_visible_fields"] = DEFAULT_VISIBLE_FIELDS
    return LawyerProfileResponse.model_validate(values)


@router.get(
    "/profile",
    summary="Get the lawyer profile",
    description="The signed-in lawyer's editable profile fields and organization display name.",
    response_model=LawyerProfileResponse,
    responses=problem_responses(401, 403, 404, 409, 503),
)
async def get_profile(user: LawyerDep, session: UserSessionDep) -> LawyerProfileResponse:
    return await _read_profile(session, user.id)


@router.patch(
    "/profile",
    summary="Update the lawyer profile",
    description=(
        "Updates account fields (name, phone, preferred language), professional details (Bar Council "
        "enrollment, courts, practice areas, experience, office address, languages, bio, public contact "
        "phone and email), which fields clients see on the contact card, and (owners only) the organization "
        "name. All professional fields are optional; send null to clear one. Text is NFC-normalized; the "
        "public phone must be a Bangladesh mobile (+8801XXXXXXXXX). Email cannot be changed here. "
        "Audit-logged with the changed field names only."
    ),
    response_model=LawyerProfileResponse,
    responses=problem_responses(401, 403, 404, 409, 422, 503),
    dependencies=[Depends(require_same_origin)],
)
async def patch_profile(
    request: Request,
    user: LawyerDep,
    session: UserSessionDep,
    payload: Annotated[LawyerProfilePatch, Body(description="Profile fields to change")],
) -> LawyerProfileResponse:
    current = await _read_profile(session, user.id)
    fields = payload.model_fields_set
    if "organization_name" in fields and not current.can_edit_organization:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only the organization owner can rename the organization.")
    values = payload.model_dump(include=fields)
    user_columns = [name for name in ("full_name", "phone", "preferred_language") if name in fields]
    if user_columns:
        assignments = ", ".join(f"{name} = :{name}" for name in user_columns)
        await session.execute(
            text(f"UPDATE public.users SET {assignments}, updated_at = now() WHERE id = :user_id"),
            {**{name: values[name] for name in user_columns}, "user_id": user.id},
        )
    profile_columns = [name for name in PROFILE_COLUMNS if name in fields]
    if profile_columns:
        params = {"user_id": user.id, **{name: values[name] for name in profile_columns}}
        insert_columns = ", ".join(profile_columns)
        insert_values = ", ".join(f":{name}" for name in profile_columns)
        updates = ", ".join(f"{name} = EXCLUDED.{name}" for name in profile_columns)
        await session.execute(
            text(
                f"""
                INSERT INTO public.lawyer_profiles (user_id, {insert_columns}) VALUES (:user_id, {insert_values})
                ON CONFLICT (user_id) DO UPDATE SET {updates}
                """
            ),
            params,
        )
    organization_id = await resolve_actor_organization(session, user.id)
    if "organization_name" in fields:
        await session.execute(
            text("UPDATE public.organizations SET name = :name WHERE id = :org"),
            {"name": values["organization_name"], "org": organization_id},
        )
    await write_audit_event(
        session, action="lawyer.profile_updated", actor_user_id=user.id, actor_role=user.role,
        object_type="user", object_id=user.id, organization_id=organization_id,
        ip_address=request_ip(request), user_agent=request.headers.get("user-agent", "")[:512] or None,
        request_id=getattr(request.state, "request_id", None), details={"fields": sorted(fields)},
    )
    return await _read_profile(session, user.id)
