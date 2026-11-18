from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

CaseStatus = Literal["draft", "open", "on_hold", "closed"]


class CaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reference_no: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=300)
    case_type: str = Field(min_length=1, max_length=100)
    court: str | None = Field(default=None, max_length=200)
    court_case_no: str | None = Field(default=None, max_length=100)
    jurisdiction: str | None = Field(default=None, max_length=200)
    opposing_party: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=10000)
    internal_notes: str | None = Field(default=None, max_length=10000)
    client_objectives: str | None = Field(default=None, max_length=10000)


class CasePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reference_no: str | None = Field(default=None, min_length=1, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    case_type: str | None = Field(default=None, min_length=1, max_length=100)
    court: str | None = Field(default=None, max_length=200)
    court_case_no: str | None = Field(default=None, max_length=100)
    jurisdiction: str | None = Field(default=None, max_length=200)
    opposing_party: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=10000)
    internal_notes: str | None = Field(default=None, max_length=10000)
    client_objectives: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def validate_patch(self) -> "CasePatch":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        for field in ("reference_no", "title", "case_type"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null.")
        return self


class CaseResponse(BaseModel):
    id: UUID
    organization_id: UUID
    reference_no: str
    title: str
    case_type: str
    workflow_template_id: UUID | None
    court: str | None
    court_case_no: str | None
    jurisdiction: str | None
    opposing_party: str | None
    description: str | None
    internal_notes: str | None
    client_objectives: str | None
    status: CaseStatus
    current_stage: str | None
    key_dates: dict[str, object]
    closed_at: datetime | None
    closed_by: UUID | None
    retention_until: date | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class CaseAccess(BaseModel):
    case_id: UUID
    role: Literal["lead_lawyer", "team_lawyer", "assistant", "client"]
    permissions: dict[str, bool]


class CaseMemberCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    user_id: UUID
    role: Literal["team_lawyer", "assistant"]
    permissions: dict[str, bool] = Field(default_factory=dict)


class CaseMemberResponse(BaseModel):
    id: UUID
    case_id: UUID
    user_id: UUID
    role: Literal["lead_lawyer", "team_lawyer", "assistant", "client"]
    permissions: dict[str, bool]
    status: Literal["active", "read_only", "revoked"]
    granted_at: datetime
    revoked_at: datetime | None


class AuditLogResponse(BaseModel):
    id: int
    occurred_at: datetime
    actor_user_id: UUID | None
    actor_role: str | None
    action: str
    object_type: str | None
    object_id: UUID | None
    request_id: str | None


class InvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    client_profile_id: UUID


class InvitationResponse(BaseModel):
    id: UUID
    case_id: UUID
    client_profile_id: UUID
    email: str
    expires_at: datetime
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None
    development_token: str | None = None
