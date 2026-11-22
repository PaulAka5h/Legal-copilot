"""Lawyer profile request/response models and validation.

All text is NFC-normalized before its length is checked (Bangla input often
arrives decomposed). Phones are Bangladesh mobiles stored as +8801XXXXXXXXX.
"""

import re
import unicodedata
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

PracticeArea = Literal["criminal", "civil", "family", "land", "labour", "commercial", "cheque_ni_act", "other"]
SpokenLanguage = Literal["bn", "en", "other"]
# Fields a lawyer can show on their clients' contact card. The name is always shown.
VisibleField = Literal["photo", "firm", "phone", "email", "bar_enrollment_no", "courts", "practice_areas",
                       "years_experience", "office_address", "languages", "bio"]
DEFAULT_VISIBLE_FIELDS: list[VisibleField] = ["photo", "firm", "phone"]

_BD_MOBILE = re.compile(r"^(?:\+?880|0)?(1[3-9]\d{8})$")


def nfc_value(value: object) -> object:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value).strip()
    if isinstance(value, list):
        return [nfc_value(item) for item in value]
    return value


def normalize_bd_phone(value: str) -> str:
    """'+8801712345678', '8801712345678', '01712345678' (spaces/dashes allowed) -> '+8801712345678'."""
    digits = re.sub(r"[\s\-()]", "", value)
    match = _BD_MOBILE.match(digits)
    if not match:
        raise ValueError("Phone must be a Bangladesh mobile number: +8801XXXXXXXXX.")
    return f"+880{match.group(1)}"


class LawyerProfileResponse(BaseModel):
    full_name: str
    email: str = Field(description="Login email (not editable here, never shown to clients)")
    phone: str | None = Field(description="Account phone")
    preferred_language: Literal["en", "bn"]
    chamber_name: str | None
    organization_name: str
    can_edit_organization: bool = Field(description="True for organization owners")
    bar_enrollment_no: str | None
    courts: list[str]
    practice_areas: list[PracticeArea]
    years_experience: int | None
    office_address: str | None
    languages: list[SpokenLanguage]
    bio: str | None
    public_phone: str | None = Field(description="Public contact phone, +8801XXXXXXXXX")
    public_email: str | None = Field(description="Public contact email, separate from the login email")
    client_visible_fields: list[VisibleField] = Field(
        description="Fields shown on clients' contact card (the name is always shown)")
    photo_id: UUID | None = Field(description="Current photo version; null when there is no photo")


class LawyerProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=30, pattern=r"^[0-9+()\- ]*$")
    preferred_language: Literal["en", "bn"] | None = None
    chamber_name: str | None = Field(default=None, max_length=200)
    organization_name: str | None = Field(default=None, min_length=1, max_length=200)
    bar_enrollment_no: str | None = Field(default=None, max_length=50)
    courts: list[str] | None = Field(default=None, max_length=10,
                                     description="Courts of practice, at most 10, 150 characters each")
    practice_areas: list[PracticeArea] | None = Field(default=None, max_length=8)
    years_experience: int | None = Field(default=None, ge=0, le=80)
    office_address: str | None = Field(default=None, max_length=300)
    languages: list[SpokenLanguage] | None = Field(default=None, max_length=3)
    bio: str | None = Field(default=None, max_length=500)
    public_phone: str | None = Field(default=None, description="Bangladesh mobile; stored as +8801XXXXXXXXX")
    public_email: EmailStr | None = Field(default=None, max_length=254)
    client_visible_fields: list[VisibleField] | None = Field(default=None, max_length=11)

    @field_validator("*", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        value = nfc_value(value)
        return None if value == "" else value

    @field_validator("courts")
    @classmethod
    def check_courts(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        courts = [court for court in value if court]
        if any(len(court) > 150 for court in courts):
            raise ValueError("Each court may be at most 150 characters.")
        return list(dict.fromkeys(courts))

    @field_validator("practice_areas", "languages", "client_visible_fields")
    @classmethod
    def unique(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else list(dict.fromkeys(value))

    @field_validator("public_phone")
    @classmethod
    def check_phone(cls, value: str | None) -> str | None:
        return None if value is None else normalize_bd_phone(value)

    @model_validator(mode="after")
    def validate_patch(self) -> "LawyerProfilePatch":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        for field in ("full_name", "preferred_language", "organization_name", "client_visible_fields"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null.")
        return self


class LawyerContact(BaseModel):
    """A client's view of their lead lawyer: only the fields the lawyer allows; the rest are null."""

    full_name: str
    photo_id: UUID | None = Field(
        description="Set when the photo is shown and exists; fetch it from .../lawyer/photo (version for caching)")
    firm: str | None
    phone: str | None
    email: str | None
    bar_enrollment_no: str | None
    courts: list[str] | None
    practice_areas: list[PracticeArea] | None
    years_experience: int | None
    office_address: str | None
    languages: list[SpokenLanguage] | None
    bio: str | None
