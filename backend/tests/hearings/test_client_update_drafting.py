"""Tests for Draft Client Update generation and Lawyer Review Gate (Rule 8 & HEAR-8)."""

from datetime import datetime, timezone
import pytest
from backend.src.hearings.schemas import (
    HearingCreateRequest,
    HearingDateStatus,
    HearingReviewStatus,
    HearingUpdateCreateRequest,
)
from backend.src.hearings.service import HearingsService


def test_draft_client_update_generation_and_approval_gate():
    service = HearingsService()
    now = datetime.now(timezone.utc)
    case_id = "case-client-draft-test"

    # 1. Schedule hearing
    hearing = service.create_hearing(
        case_id=case_id,
        request=HearingCreateRequest(
            scheduled_at=now,
            purpose="Hearing on Charge",
            court_room="Court 2",
            date_status=HearingDateStatus.CONFIRMED,
        ),
        lawyer_id="lawyer-advocate",
    )

    # 2. Submit hearing outcome
    reassessment = service.submit_hearing_update_and_reassess(
        hearing_id=str(hearing.id),
        request=HearingUpdateCreateRequest(
            happened="The court heard arguments on charge framing.",
            orders_directions="The court fixed the next date for formal indictment.",
            next_hearing_date=datetime(2025, 4, 15, 10, 30, tzinfo=timezone.utc),
            next_hearing_confirmed=False,
            follow_ups="Bring witness Haji Abdul to chambers.",
        ),
        case_title="Rahman Commercial Debt Matter",
    )

    # 3. Verify Draft Client Update properties
    client_draft = reassessment.draft_client_update
    assert client_draft.is_approved_by_lawyer is False
    assert client_draft.approved_by is None
    assert client_draft.approved_at is None
    assert reassessment.review_status == HearingReviewStatus.DRAFT

    # Verify plain-language wording without confidential internal risk rating
    assert "Rahman Commercial Debt Matter" in client_draft.title
    assert "The court directed" in client_draft.plain_language_summary
    assert "tentative" in client_draft.next_hearing_info.lower()
    assert "rubric" not in client_draft.plain_language_summary.lower()
    assert "plausibility" not in client_draft.plain_language_summary.lower()

    # 4. Lawyer Review Gate: Approve client update
    approved_payload = service.approve_client_update(
        hearing_id=str(hearing.id),
        reassessment_id=str(reassessment.id),
        lawyer_id="lawyer-advocate",
    )

    assert approved_payload.is_approved_by_lawyer is True
    assert approved_payload.approved_by == "lawyer-advocate"
    assert approved_payload.approved_at is not None

    # Check updated review status on reassessment record
    updated_reassessment = service.get_latest_reassessment(str(hearing.id))
    assert updated_reassessment.review_status == HearingReviewStatus.LAWYER_REVIEWED
