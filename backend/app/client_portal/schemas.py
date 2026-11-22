from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, computed_field

from app.cases.progress import CaseProgressStage, case_progress


class ClientCaseResponse(BaseModel):
    id: UUID
    title: str
    status: Literal["draft", "open", "on_hold", "closed"]
    case_type: str
    court: str | None
    has_confirmed_hearing: bool = Field(default=False, description="A confirmed hearing is on record")
    published_updates: int = Field(default=0, description="Hearing updates the lawyer published")

    @computed_field(description="Progress from client-visible data only")  # type: ignore[prop-decorator]
    @property
    def progress(self) -> list[CaseProgressStage]:
        return case_progress(
            status=self.status,
            has_hearing=self.has_confirmed_hearing,
            has_held_hearing=self.published_updates > 0,
        )


class ClientUpdateResponse(BaseModel):
    id: UUID
    version: int
    title: str
    body: str
    language: Literal["en", "bn"]
    published_at: datetime | None


class ClientTaskResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    due_date: str | None
    status: Literal["open", "done", "cancelled"]


class ClientDocumentResponse(BaseModel):
    id: UUID
    document_id: UUID
    display_name: str
    shared_at: datetime


class ClientNotificationResponse(BaseModel):
    id: UUID
    kind: str
    title: str
    body: str | None
    read_at: datetime | None
    created_at: datetime


class ClientHearingResponse(BaseModel):
    id: UUID
    scheduled_at: datetime
    purpose: str | None
    court_room: str | None


class DownloadUrlResponse(BaseModel):
    status: Literal["NOT_CONFIGURED"]
