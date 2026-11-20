from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HearingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    scheduled_at: datetime | None = Field(default=None, description="Date and time, entered by the lawyer")
    purpose: str | None = Field(default=None, max_length=300)
    court_room: str | None = Field(default=None, max_length=200)
    date_confirmed: bool = Field(default=False, description="True only when the lawyer confirms the date")


class HearingOut(BaseModel):
    id: UUID
    case_id: UUID
    scheduled_at: datetime | None
    purpose: str | None
    court_room: str | None
    date_status: Literal["tentative", "confirmed", "postponed", "held", "cancelled"]
    date_confirmed_by: UUID | None
    date_confirmed_at: datetime | None
    created_at: datetime


class HearingUpdateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    order_text: str = Field(min_length=1, max_length=8000, description="The court's order or direction, as entered")
    notes: str | None = Field(default=None, max_length=8000, description="Lawyer's notes of what happened")
    next_hearing_date: datetime | None = Field(default=None, description="Next date as entered by the lawyer")
    next_hearing_confirmed: bool = Field(default=False, description="Lawyer confirms the next date")
    incident_date: date | None = Field(default=None, description="Incident date for the re-run analysis")

    @model_validator(mode="after")
    def confirmed_needs_date(self) -> "HearingUpdateCreate":
        if self.next_hearing_confirmed and self.next_hearing_date is None:
            raise ValueError("next_hearing_confirmed requires next_hearing_date")
        return self


class TimelineEntry(BaseModel):
    hearing_update_id: UUID
    hearing_id: UUID
    version: int
    order_text: str | None
    notes: str | None
    next_hearing_date: datetime | None
    next_hearing_confirmed: bool
    source_label: str
    created_at: datetime


class FindingChange(BaseModel):
    offence_or_claim: str
    before: str | None = Field(description="Previous strength, or null if new")
    after: str | None = Field(description="New strength, or null if no longer found")


class HearingReassessment(BaseModel):
    id: UUID
    hearing_id: UUID
    hearing_update_id: UUID
    changes: list[FindingChange]
    closed_options: list[str]
    new_options: list[str]
    tree_version: int | None
    analysis_version: int
    tasks: list[str]
    suggested_next_date: date | None = Field(description="Found in the order text by code; a draft only (Rule 5)")
    suggested_next_date_status: Literal["draft"] = "draft"
    next_hearing_id: UUID | None = Field(description="Hearing created only when the lawyer confirmed the next date")
    client_update_id: UUID | None = Field(description="Draft client update; the lawyer publishes it")
    client_update_status: Literal["draft", "published", "withdrawn"] | None
    created_at: datetime
