"""Unit tests for hearing scheduling, CRUD operations, and Rule 5 date confirmation guards."""

from datetime import datetime, timezone
import pytest
from backend.src.hearings.schemas import (
    HearingCreateRequest,
    HearingDateStatus,
    HearingPatchRequest,
)
from backend.src.hearings.service import (
    HearingNotFoundError,
    HearingsService,
    UnauthorizedDateConfirmationError,
)


def test_hearing_creation_defaults_to_tentative():
    service = HearingsService()
    now = datetime.now(timezone.utc)
    req = HearingCreateRequest(
        scheduled_at=now,
        purpose="Framing of Issues",
        court_room="Room 4, Dhaka District Court",
        date_status=HearingDateStatus.TENTATIVE,
    )
    hearing = service.create_hearing("case-test-101", req, lawyer_id="lawyer-lead")

    assert hearing.case_id == "case-test-101"
    assert hearing.purpose == "Framing of Issues"
    assert hearing.date_status == HearingDateStatus.TENTATIVE
    assert hearing.date_confirmed_by is None
    assert hearing.date_confirmed_at is None


def test_hearing_creation_confirmed_requires_lawyer_attribution():
    service = HearingsService()
    now = datetime.now(timezone.utc)
    req = HearingCreateRequest(
        scheduled_at=now,
        purpose="Peremptory Trial",
        date_status=HearingDateStatus.CONFIRMED,
    )

    # Valid lawyer confirmation
    hearing = service.create_hearing("case-test-102", req, lawyer_id="lawyer-advocate-4")
    assert hearing.date_status == HearingDateStatus.CONFIRMED
    assert hearing.date_confirmed_by == "lawyer-advocate-4"
    assert hearing.date_confirmed_at is not None

    # Empty lawyer identity fails
    with pytest.raises(UnauthorizedDateConfirmationError):
        service.create_hearing("case-test-102", req, lawyer_id="")


def test_hearing_patch_and_date_confirmation():
    service = HearingsService()
    now = datetime.now(timezone.utc)
    create_req = HearingCreateRequest(
        scheduled_at=now,
        purpose="Initial Return",
        date_status=HearingDateStatus.TENTATIVE,
    )
    hearing = service.create_hearing("case-test-103", create_req, lawyer_id="lawyer-1")

    # Patch purpose and explicitly confirm date
    patch_req = HearingPatchRequest(
        purpose="Submissions on Preliminary Objection",
        confirm_date=True,
    )
    patched = service.patch_hearing(str(hearing.id), patch_req, lawyer_id="lawyer-lead-2")

    assert patched.purpose == "Submissions on Preliminary Objection"
    assert patched.date_status == HearingDateStatus.CONFIRMED
    assert patched.date_confirmed_by == "lawyer-lead-2"
    assert patched.date_confirmed_at is not None


def test_list_case_hearings_chronological():
    service = HearingsService()
    case_id = "case-multi-hearings"
    t1 = datetime(2025, 3, 10, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc)

    service.create_hearing(case_id, HearingCreateRequest(scheduled_at=t1, purpose="Hearing 2"))
    service.create_hearing(case_id, HearingCreateRequest(scheduled_at=t2, purpose="Hearing 1"))

    hearings = service.list_hearings_for_case(case_id)
    assert len(hearings) == 2
    assert hearings[0].scheduled_at == t2
    assert hearings[1].scheduled_at == t1
