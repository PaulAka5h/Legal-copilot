from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    full_name: str = Field(min_length=1, max_length=200)
    preferred_language: Literal["en", "bn"] = "en"


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    mfa_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    mfa_recovery_code: str | None = Field(default=None, min_length=8, max_length=256)
    expected_role: Literal["lawyer", "client"] | None = Field(
        default=None,
        description=(
            "The portal the user signs in from. An account of another role gets the same generic "
            "invalid-credentials error as a wrong password, and no session is created."
        ),
    )


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: Literal["lawyer", "client", "admin"]
    full_name: str
    preferred_language: Literal["en", "bn"]
    must_change_password: bool = Field(
        default=False,
        description="True until the user replaces a password a lawyer set for them.",
    )


class MessageResponse(BaseModel):
    message: str


class CurrentUser(BaseModel):
    id: UUID
    email: str
    role: Literal["lawyer", "client", "admin"]
    full_name: str
    preferred_language: Literal["en", "bn"]
    session_id: UUID
    must_change_password: bool = False


class PasswordForgotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: EmailStr


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    token: str = Field(min_length=32, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class MfaSetupResponse(BaseModel):
    otpauth_uri: str


class MfaVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    code: str = Field(pattern=r"^\d{6}$")


class MfaVerifyResponse(BaseModel):
    enabled: bool
    recovery_codes: list[str]


class InvitationAcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=12, max_length=256)
