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


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: Literal["lawyer", "client", "admin"]
    full_name: str
    preferred_language: Literal["en", "bn"]


class MessageResponse(BaseModel):
    message: str


class CurrentUser(BaseModel):
    id: UUID
    email: str
    role: Literal["lawyer", "client", "admin"]
    full_name: str
    preferred_language: Literal["en", "bn"]
    session_id: UUID
