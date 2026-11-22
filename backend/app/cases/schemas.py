from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.cases.progress import CaseProgressStage, case_progress

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
    status: Literal["open", "on_hold"] | None = Field(
        default=None,
        description="Active or on hold. Closing and reopening use /close and /reopen.",
    )

    @model_validator(mode="after")
    def validate_patch(self) -> "CasePatch":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        for field in ("reference_no", "title", "case_type", "status"):
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
    archived_at: datetime | None = None
    archived_by: UUID | None = None
    hearing_count: int = Field(default=0, description="Hearings on record")
    hearings_held: int = Field(default=0, description="Hearings with a recorded outcome")

    @computed_field(description="Progress derived from hearings and status")  # type: ignore[prop-decorator]
    @property
    def progress(self) -> list[CaseProgressStage]:
        return case_progress(
            status=self.status,
            has_hearing=self.hearing_count > 0,
            has_held_hearing=self.hearings_held > 0,
        )


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


class ClientUpdateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=10000)
    language: Literal["en", "bn"] = "en"


class ClientUpdateResponse(BaseModel):
    id: UUID
    case_id: UUID
    version: int
    title: str
    body: str
    language: Literal["en", "bn"]
    status: Literal["draft", "published", "withdrawn"]


class CaseCloseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str | None = Field(default=None, max_length=2000)


class SharedDocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    document_id: UUID
    display_name: str = Field(min_length=1, max_length=300)


class ClientTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=10000)
    due_date: date | None = None


class VisibilityPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status_label: str | None = Field(default=None, max_length=200)
    stage_label: str | None = Field(default=None, max_length=200)
    plain_explanation: str | None = Field(default=None, max_length=10000)


class ClientTaskPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: Literal["open", "done", "cancelled"]
