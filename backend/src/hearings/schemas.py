"""Pydantic schemas for Phase 7 Hearings, Continuous Reassessment, and Calendar."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

from backend.src.strategy.schemas import Plausibility, RubricRating, StrategyRecord


class HearingDateStatus(str, Enum):
    TENTATIVE = "tentative"
    CONFIRMED = "confirmed"
    POSTPONED = "postponed"
    HELD = "held"
    CANCELLED = "cancelled"


class HearingSourceLabel(str, Enum):
    LAWYER_ENTERED = "lawyer_entered"
    VERIFIED_COURT_RECORD = "verified_court_record"


class HearingRecommendation(str, Enum):
    MAINTAIN = "maintain"
    REVIEW = "review"
    CHANGE_SUGGESTED = "change_suggested"


class HearingReviewStatus(str, Enum):
    DRAFT = "draft"
    LAWYER_REVIEWED = "lawyer_reviewed"
    LAWYER_REJECTED = "lawyer_rejected"


class BranchDiffItem(BaseModel):
    branch_id: str
    opponent_argument: str
    rebuttal_text: str
    previous_plausibility: Plausibility
    updated_plausibility: Plausibility
    is_pruned: bool = False
    diff_reason: str
    previous_residual_risk: str
    updated_residual_risk: str


class RubricDiffItem(BaseModel):
    dimension: str
    previous_rating: RubricRating
    updated_rating: RubricRating
    justification: str


class HearingRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    case_id: str
    organization_id: str = "default_org"
    scheduled_at: Optional[datetime] = None
    purpose: Optional[str] = None
    court_room: Optional[str] = None
    date_status: HearingDateStatus = HearingDateStatus.TENTATIVE
    date_confirmed_by: Optional[str] = None
    date_confirmed_at: Optional[datetime] = None
    client_attendance_required: bool = False
    held_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HearingCreateRequest(BaseModel):
    scheduled_at: datetime = Field(description="Scheduled hearing datetime (UTC)")
    purpose: str = Field(description="Hearing purpose (e.g. Framing of Issues, Cross-examination)")
    court_room: Optional[str] = Field(default=None, description="Court room or bench identifier")
    date_status: HearingDateStatus = Field(
        default=HearingDateStatus.TENTATIVE,
        description="Tentative or confirmed by authorized lawyer",
    )
    client_attendance_required: bool = Field(default=False)
    organization_id: str = "default_org"


class HearingPatchRequest(BaseModel):
    scheduled_at: Optional[datetime] = None
    purpose: Optional[str] = None
    court_room: Optional[str] = None
    date_status: Optional[HearingDateStatus] = None
    confirm_date: Optional[bool] = Field(
        default=None,
        description="Explicit flag to confirm date (Legal Product Rule 5 - AI cannot confirm)",
    )
    client_attendance_required: Optional[bool] = None
    held_at: Optional[datetime] = None


class HearingUpdateRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    case_id: str
    organization_id: str = "default_org"
    hearing_id: str
    author_id: str
    happened: str
    our_arguments: Optional[str] = None
    opposing_arguments: Optional[str] = None
    judge_remarks: Optional[str] = None
    new_evidence: Optional[str] = None
    objections_procedural: Optional[str] = None
    orders_directions: Optional[str] = None
    next_hearing_date: Optional[datetime] = None
    next_hearing_confirmed: bool = False
    follow_ups: Optional[str] = None
    source_label: HearingSourceLabel = HearingSourceLabel.LAWYER_ENTERED
    version: int = 1
    supersedes_id: Optional[UUID] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HearingUpdateCreateRequest(BaseModel):
    happened: str = Field(description="What transpired during the hearing")
    our_arguments: Optional[str] = Field(default=None, description="Arguments and submissions raised by our side")
    opposing_arguments: Optional[str] = Field(default=None, description="Submissions, defenses, or objections raised by opposing counsel")
    judge_remarks: Optional[str] = Field(default=None, description="Judge's questions and verbal bench remarks as recorded by lawyer")
    new_evidence: Optional[str] = Field(default=None, description="New exhibits or documents submitted into evidence")
    objections_procedural: Optional[str] = Field(default=None, description="Procedural objections raised or ruled upon")
    orders_directions: Optional[str] = Field(default=None, description="Formal orders, directions, or interim relief granted")
    next_hearing_date: Optional[datetime] = Field(default=None, description="Tentative next hearing date set by court")
    next_hearing_confirmed: bool = Field(default=False, description="Whether lawyer explicitly confirmed next date")
    follow_ups: Optional[str] = Field(default=None, description="Tasks and follow-ups required before next date")
    source_label: HearingSourceLabel = Field(default=HearingSourceLabel.LAWYER_ENTERED)
    author_id: str = "lawyer-1"


class DraftClientUpdatePayload(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    hearing_id: str
    title: str
    plain_language_summary: str
    next_hearing_info: Optional[str] = None
    client_action_required: Optional[str] = None
    is_approved_by_lawyer: bool = False
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None


class HearingReassessmentRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    case_id: str
    hearing_id: str
    hearing_update_id: str
    organization_id: str = "default_org"
    previous_strategy_id: Optional[UUID] = None
    reassessed_strategy_id: Optional[UUID] = None
    recommendation: HearingRecommendation
    recommendation_reason: str
    tree_diff: List[BranchDiffItem] = Field(default_factory=list)
    rubric_diff: List[RubricDiffItem] = Field(default_factory=list)
    new_risks: List[str] = Field(default_factory=list)
    new_evidence_needs: List[str] = Field(default_factory=list)
    reassessed_strategy: Optional[StrategyRecord] = None
    draft_client_update: DraftClientUpdatePayload
    review_status: HearingReviewStatus = HearingReviewStatus.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HearingCalendarItem(BaseModel):
    hearing_id: str
    case_id: str
    case_title: str
    court_name: str
    scheduled_at: datetime
    purpose: str
    date_status: HearingDateStatus
    client_attendance_required: bool
