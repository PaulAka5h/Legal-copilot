from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ClientCaseResponse(BaseModel):
    id: UUID
    title: str
    status: Literal["draft", "open", "on_hold", "closed"]
    case_type: str
    court: str | None


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
