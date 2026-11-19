"""FastAPI Router for Phase 7 Hearings, Continuous Reassessment, and Calendar.

Follows project conventions and FastAPI best practices:
- Rich OpenAPI descriptions and parameter schemas
- Strict multi-tenant case isolation
- Separation of draft AI analysis from confirmed lawyer actions
"""

from typing import Annotated, List, Optional
from fastapi import APIRouter, Body, HTTPException, Path, Query, status

from backend.src.hearings.schemas import (
    DraftClientUpdatePayload,
    HearingCalendarItem,
    HearingCreateRequest,
    HearingPatchRequest,
    HearingReassessmentRecord,
    HearingRecord,
    HearingUpdateCreateRequest,
    HearingUpdateRecord,
)
from backend.src.hearings.service import (
    HearingNotFoundError,
    HearingsService,
    UnauthorizedDateConfirmationError,
)

router = APIRouter(tags=["Hearings & Reassessment"])

# Singleton hearings service instance
_hearings_service = HearingsService()


def get_hearings_service() -> HearingsService:
    return _hearings_service


# ------------------------------------------------------------------------------
# Case-Scoped Hearing Endpoints
# ------------------------------------------------------------------------------

@router.post(
    "/cases/{case_id}/hearings",
    response_model=HearingRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule a New Hearing",
    description="Schedules a court hearing entry for the given case. Defaults to tentative date status unless confirmed by an authorized lawyer.",
)
def create_case_hearing(
    case_id: Annotated[str, Path(description="Target Case UUID or reference")],
    payload: Annotated[HearingCreateRequest, Body(description="Hearing schedule and purpose")],
    lawyer_id: Annotated[str, Query(description="Lawyer user ID creating the entry")] = "lawyer-1",
) -> HearingRecord:
    service = get_hearings_service()
    try:
        return service.create_hearing(case_id=case_id, request=payload, lawyer_id=lawyer_id)
    except UnauthorizedDateConfirmationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/cases/{case_id}/hearings",
    response_model=List[HearingRecord],
    status_code=status.HTTP_200_OK,
    summary="List Case Hearings",
    description="Returns all scheduled, held, and tentative hearings for the specified case in chronological order.",
)
def list_case_hearings(
    case_id: Annotated[str, Path(description="Target Case UUID or reference")],
) -> List[HearingRecord]:
    service = get_hearings_service()
    return service.list_hearings_for_case(case_id)


# ------------------------------------------------------------------------------
# Individual Hearing Endpoints
# ------------------------------------------------------------------------------

@router.get(
    "/hearings/{hearing_id}",
    response_model=HearingRecord,
    status_code=status.HTTP_200_OK,
    summary="Get Hearing Details",
    description="Retrieves single hearing scheduling, purpose, court room, and confirmation status.",
)
def get_hearing(
    hearing_id: Annotated[str, Path(description="Hearing UUID")],
) -> HearingRecord:
    service = get_hearings_service()
    try:
        return service.get_hearing(hearing_id)
    except HearingNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hearing not found")


@router.patch(
    "/hearings/{hearing_id}",
    response_model=HearingRecord,
    status_code=status.HTTP_200_OK,
    summary="Update or Confirm Hearing",
    description="Updates hearing schedule, notes, or explicitly confirms date (Legal Product Rule 5).",
)
def patch_hearing(
    hearing_id: Annotated[str, Path(description="Hearing UUID")],
    payload: Annotated[HearingPatchRequest, Body(description="Fields to update")],
    lawyer_id: Annotated[str, Query(description="Lawyer ID confirming or updating")] = "lawyer-1",
) -> HearingRecord:
    service = get_hearings_service()
    try:
        return service.patch_hearing(hearing_id=hearing_id, request=payload, lawyer_id=lawyer_id)
    except HearingNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hearing not found")
    except UnauthorizedDateConfirmationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ------------------------------------------------------------------------------
# Hearing Updates & Strategy Reassessment
# ------------------------------------------------------------------------------

@router.post(
    "/hearings/{hearing_id}/updates",
    response_model=HearingReassessmentRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Hearing Update & Run Continuous Strategy Reassessment",
    description="Stores append-only versioned hearing update (Rule 6), diffs courtroom developments against active 2-ply scenario tree, re-evaluates 5-dimension rubric, generates a new strategy revision, and drafts a client-safe update (HEAR-8).",
)
def submit_hearing_update(
    hearing_id: Annotated[str, Path(description="Hearing UUID")],
    payload: Annotated[HearingUpdateCreateRequest, Body(description="Courtroom developments, orders, arguments, and judge remarks")],
    case_title: Annotated[Optional[str], Query(description="Optional case title for client update")] = "Cheque Dispute",
) -> HearingReassessmentRecord:
    service = get_hearings_service()
    try:
        return service.submit_hearing_update_and_reassess(
            hearing_id=hearing_id,
            request=payload,
            case_title=case_title or "Cheque Dispute",
        )
    except HearingNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hearing not found")


@router.get(
    "/hearings/{hearing_id}/updates",
    response_model=List[HearingUpdateRecord],
    status_code=status.HTTP_200_OK,
    summary="Get Hearing Update Version History",
    description="Returns all version revisions (supersedes_id chain) for the hearing notes to preserve historical auditability (Rule 6).",
)
def list_hearing_updates(
    hearing_id: Annotated[str, Path(description="Hearing UUID")],
) -> List[HearingUpdateRecord]:
    service = get_hearings_service()
    try:
        return service.list_hearing_updates(hearing_id)
    except HearingNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hearing not found")


@router.get(
    "/hearings/{hearing_id}/reassessment",
    response_model=HearingReassessmentRecord,
    status_code=status.HTTP_200_OK,
    summary="Get Latest Hearing Strategy Reassessment",
    description="Retrieves the latest diff analysis, tree branch evaluations, rubric shifts, and posture recommendation ('maintain', 'review', 'change_suggested').",
)
def get_hearing_reassessment(
    hearing_id: Annotated[str, Path(description="Hearing UUID")],
) -> HearingReassessmentRecord:
    service = get_hearings_service()
    try:
        return service.get_latest_reassessment(hearing_id)
    except HearingNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reassessment not found for hearing")


@router.post(
    "/hearings/{hearing_id}/reassessment/approve-client-update",
    response_model=DraftClientUpdatePayload,
    status_code=status.HTTP_200_OK,
    summary="Approve Draft Client Update for Publication",
    description="Lawyer review gate: Approves the plain-language hearing draft so it can be published to the client portal (Rule 8 & HEAR-8).",
)
def approve_client_update(
    hearing_id: Annotated[str, Path(description="Hearing UUID")],
    reassessment_id: Annotated[str, Query(description="Reassessment UUID to approve")],
    lawyer_id: Annotated[str, Query(description="Reviewing lawyer ID")] = "lawyer-1",
) -> DraftClientUpdatePayload:
    service = get_hearings_service()
    try:
        return service.approve_client_update(
            hearing_id=hearing_id,
            reassessment_id=reassessment_id,
            lawyer_id=lawyer_id,
        )
    except (HearingNotFoundError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ------------------------------------------------------------------------------
# Calendar Endpoint
# ------------------------------------------------------------------------------

@router.get(
    "/calendar",
    response_model=List[HearingCalendarItem],
    status_code=status.HTTP_200_OK,
    summary="Get Lawyer Hearing Calendar",
    description="Aggregates upcoming and scheduled hearings across all active matters for calendar views.",
)
def get_lawyer_calendar() -> List[HearingCalendarItem]:
    service = get_hearings_service()
    return service.get_lawyer_calendar()
