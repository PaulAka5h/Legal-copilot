from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

# Passwords are never trimmed: surrounding spaces are part of the secret.
Password = Annotated[
    str,
    StringConstraints(strip_whitespace=False, min_length=12, max_length=256),
]


class ClientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = Field(
        default=None,
        description="Sign-in email. When given, a client login is created.",
    )
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=1000)
    password: Password | None = Field(
        default=None,
        description=(
            "Optional temporary password (12+ characters). Empty means the server "
            "generates one. The client must change it at first sign-in."
        ),
    )
    case_id: UUID | None = Field(
        default=None,
        description="Optional case to link the client to (lead lawyer only).",
    )

    @field_validator("password", mode="before")
    @classmethod
    def empty_password_means_generate(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def login_needs_email(self) -> "ClientCreate":
        if self.email is None and (self.password is not None or self.case_id is not None):
            raise ValueError("email is required to create a client login.")
        return self


class ClientPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_patch(self) -> "ClientPatch":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        if "display_name" in self.model_fields_set and self.display_name is None:
            raise ValueError("display_name cannot be null.")
        return self


class ClientResponse(BaseModel):
    id: UUID
    organization_id: UUID
    display_name: str
    email: EmailStr | None
    phone: str | None
    address: str | None
    created_at: datetime
    has_account: bool = Field(description="True when the client has a portal login.")


class ClientCreatedResponse(ClientResponse):
    temporary_password: str | None = Field(
        description=(
            "Shown once. Present when a login was created; never stored or "
            "retrievable again."
        ),
    )
    linked_case_id: UUID | None = Field(
        description="The case the client was linked to, if one was chosen.",
    )


class ClientCaseLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: UUID = Field(description="Open case, led by the acting lawyer, to link the client to.")


class ClientCaseLinkResponse(BaseModel):
    client_id: UUID
    case_id: UUID
    case_member_id: UUID = Field(description="The client's case membership (role `client`).")


class ClientPasswordResetResponse(BaseModel):
    client_id: UUID
    email: EmailStr
    temporary_password: str = Field(description="Shown once; never stored.")
    created_account: bool = Field(
        description="True when this call created the client's first login.",
    )
    sessions_revoked: int = Field(description="Client sessions that were signed out.")
