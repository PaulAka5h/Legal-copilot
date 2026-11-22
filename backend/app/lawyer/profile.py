"""Lawyer profile: name, phone, preferred language, chamber and organization name.

Email is not editable here. Only an organization owner may rename the
organization. Every change is audit-logged with field names only (no values).
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import LawyerDep, UserSessionDep, request_ip, require_same_origin
from app.auth.repository import write_audit_event
from app.errors import problem_responses
from app.tenancy import resolve_actor_organization

router = APIRouter(prefix="/api/v1/lawyer", tags=["lawyer-profile"])


class LawyerProfileResponse(BaseModel):
    full_name: str
    email: str
    phone: str | None
    preferred_language: Literal["en", "bn"]
    chamber_name: str | None
    organization_name: str
    can_edit_organization: bool = Field(description="True for organization owners")
    show_contact_to_clients: bool = Field(
        description="The lawyer allows firm, phone and email on their clients' dashboards (name is always shown)")


class LawyerProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=30, pattern=r"^[0-9+()\- ]*$")
    preferred_language: Literal["en", "bn"] | None = None
    chamber_name: str | None = Field(default=None, max_length=200)
    organization_name: str | None = Field(default=None, min_length=1, max_length=200)
    show_contact_to_clients: bool | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> "LawyerProfilePatch":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        for field in ("full_name", "preferred_language", "organization_name", "show_contact_to_clients"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null.")
        return self


async def _read_profile(session: AsyncSession, user_id: UUID) -> LawyerProfileResponse:
    organization_id = await resolve_actor_organization(session, user_id)
    row = (await session.execute(
        text(
            """
            SELECT u.full_name, u.email::text AS email, u.phone, u.preferred_language,
                   lp.chamber_name, o.name AS organization_name,
                   COALESCE(lp.show_contact_to_clients, true) AS show_contact_to_clients,
                   (om.org_role = 'owner') AS can_edit_organization
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
    return LawyerProfileResponse.model_validate(dict(row))


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
        "Updates name, phone, preferred language, chamber name, whether clients see the contact card "
        "details, and (owners only) the organization name. Email cannot be changed here. Audit-logged "
        "with the changed field names."
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
    profile_columns = [name for name in ("chamber_name", "show_contact_to_clients") if name in fields]
    if profile_columns:
        params = {"user_id": user.id, "chamber_name": (values.get("chamber_name") or None),
                  "show_contact_to_clients": values.get("show_contact_to_clients", True)}
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
