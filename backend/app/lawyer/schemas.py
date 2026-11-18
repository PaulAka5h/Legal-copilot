from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class LawyerOverviewResponse(BaseModel):
    active_cases: int
    total_matters: int
    total_clients: int
    next_hearing: None


class LawyerActivityResponse(BaseModel):
    id: str
    action: str
    object_type: str | None
    object_id: UUID | None
    occurred_at: datetime


class LawyerTeamMemberResponse(BaseModel):
    user_id: UUID
    full_name: str
    email: str
    org_role: str
