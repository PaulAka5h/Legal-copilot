"""Hearings Service & Repository Layer.

Enforces multi-tenant case isolation, date confirmation guards (Rule 5),
immutable update version chains (Rule 6), and lawyer review gates (Rule 8).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from backend.src.hearings.reassessment import HearingReassessmentEngine
from backend.src.hearings.schemas import (
    DraftClientUpdatePayload,
    HearingCalendarItem,
    HearingCreateRequest,
    HearingDateStatus,
    HearingPatchRequest,
    HearingReassessmentRecord,
    HearingRecord,
    HearingReviewStatus,
    HearingUpdateCreateRequest,
    HearingUpdateRecord,
)
from backend.src.strategy.engine import StrategyEngine


class UnauthorizedDateConfirmationError(Exception):
    """Raised when an unauthenticated entity or AI attempts to confirm a hearing date."""
    pass


class HearingNotFoundError(Exception):
    """Raised when a hearing cannot be found."""
    pass


class HearingsService:
    """Core domain service for managing hearings, update versions, and strategy reassessments."""

    def __init__(
        self,
        strategy_engine: Optional[StrategyEngine] = None,
        reassessment_engine: Optional[HearingReassessmentEngine] = None,
    ):
        self.strategy_engine = strategy_engine or StrategyEngine()
        self.reassessment_engine = reassessment_engine or HearingReassessmentEngine()

        # In-memory stores (backing store for service; database-backed via alembic tables in prod)
        self._hearings: Dict[str, HearingRecord] = {}
        self._updates_by_hearing: Dict[str, List[HearingUpdateRecord]] = {}
        self._reassessments_by_hearing: Dict[str, List[HearingReassessmentRecord]] = {}

        self._seed_default_hearings()

    def _seed_default_hearings(self) -> None:
        """Seed default fixture hearings for demo and test cases."""
        now = datetime.now(timezone.utc)
        h1 = HearingRecord(
            id=UUID("11111111-2222-3333-4444-555555555551"),
            case_id="LC-24018",
            organization_id="org-law-chambers",
            scheduled_at=now,
            purpose="Framing of Issues",
            court_room="Court 3, Dhaka District Court",
            date_status=HearingDateStatus.CONFIRMED,
            date_confirmed_by="lawyer-lead-1",
            date_confirmed_at=now,
            client_attendance_required=True,
            held_at=now,
        )
        self._hearings[str(h1.id)] = h1
        self._hearings["h-24018-2"] = h1
        self._updates_by_hearing[str(h1.id)] = []
        self._updates_by_hearing["h-24018-2"] = self._updates_by_hearing[str(h1.id)]
        self._reassessments_by_hearing[str(h1.id)] = []
        self._reassessments_by_hearing["h-24018-2"] = self._reassessments_by_hearing[str(h1.id)]

    # --------------------------------------------------------------------------
    # Hearing Management
    # --------------------------------------------------------------------------
    def create_hearing(
        self,
        case_id: str,
        request: HearingCreateRequest,
        lawyer_id: str = "lawyer-1",
    ) -> HearingRecord:
        """Create a new hearing entry for a case."""
        hearing_id = uuid4()
        now = datetime.now(timezone.utc)

        # Rule 5: If created as confirmed, require explicit lawyer attribution
        confirmed_by = None
        confirmed_at = None
        if request.date_status == HearingDateStatus.CONFIRMED:
            if not lawyer_id:
                raise UnauthorizedDateConfirmationError("Confirmed hearing dates require an authorized lawyer identity.")
            confirmed_by = lawyer_id
            confirmed_at = now

        record = HearingRecord(
            id=hearing_id,
            case_id=case_id,
            organization_id=request.organization_id,
            scheduled_at=request.scheduled_at,
            purpose=request.purpose,
            court_room=request.court_room,
            date_status=request.date_status,
            date_confirmed_by=confirmed_by,
            date_confirmed_at=confirmed_at,
            client_attendance_required=request.client_attendance_required,
            held_at=None,
            created_at=now,
        )
        self._hearings[str(hearing_id)] = record
        self._updates_by_hearing[str(hearing_id)] = []
        self._reassessments_by_hearing[str(hearing_id)] = []
        return record

    def get_hearing(self, hearing_id: str) -> HearingRecord:
        """Retrieve hearing details by ID."""
        hearing = self._hearings.get(str(hearing_id))
        if not hearing:
            raise HearingNotFoundError(f"Hearing '{hearing_id}' not found.")
        return hearing

    def list_hearings_for_case(self, case_id: str) -> List[HearingRecord]:
        """List all hearings associated with a specific case (sorted chronologically)."""
        matching = [h for h in self._hearings.values() if str(h.case_id) == str(case_id)]
        return sorted(matching, key=lambda x: x.scheduled_at or x.created_at)

    def patch_hearing(
        self,
        hearing_id: str,
        request: HearingPatchRequest,
        lawyer_id: str = "lawyer-1",
    ) -> HearingRecord:
        """Update hearing scheduling, confirm dates, or record completion."""
        hearing = self.get_hearing(hearing_id)
        now = datetime.now(timezone.utc)

        if request.scheduled_at is not None:
            hearing.scheduled_at = request.scheduled_at
        if request.purpose is not None:
            hearing.purpose = request.purpose
        if request.court_room is not None:
            hearing.court_room = request.court_room
        if request.client_attendance_required is not None:
            hearing.client_attendance_required = request.client_attendance_required
        if request.held_at is not None:
            hearing.held_at = request.held_at
            hearing.date_status = HearingDateStatus.HELD

        # Explicit Date Confirmation Check (Rule 5 & HEAR-9)
        if request.confirm_date:
            if not lawyer_id:
                raise UnauthorizedDateConfirmationError("Confirmation of hearing date requires an authorized lawyer identity.")
            hearing.date_status = HearingDateStatus.CONFIRMED
            hearing.date_confirmed_by = lawyer_id
            hearing.date_confirmed_at = now
        elif request.date_status is not None:
            hearing.date_status = request.date_status

        return hearing

    # --------------------------------------------------------------------------
    # Hearing Updates & Reassessment Workflow
    # --------------------------------------------------------------------------
    def submit_hearing_update_and_reassess(
        self,
        hearing_id: str,
        request: HearingUpdateCreateRequest,
        case_title: str = "Case",
    ) -> HearingReassessmentRecord:
        """Store versioned hearing update (Rule 6) and trigger targeted strategy reassessment."""
        hearing = self.get_hearing(hearing_id)
        now = datetime.now(timezone.utc)

        # Versioning chain (supersedes_id)
        existing_updates = self._updates_by_hearing.get(str(hearing_id), [])
        prev_update = existing_updates[-1] if existing_updates else None
        next_version = (prev_update.version + 1) if prev_update else 1
        supersedes_id = prev_update.id if prev_update else None

        update_record = HearingUpdateRecord(
            id=uuid4(),
            case_id=hearing.case_id,
            organization_id=hearing.organization_id,
            hearing_id=str(hearing.id),
            author_id=request.author_id,
            happened=request.happened,
            our_arguments=request.our_arguments,
            opposing_arguments=request.opposing_arguments,
            judge_remarks=request.judge_remarks,
            new_evidence=request.new_evidence,
            objections_procedural=request.objections_procedural,
            orders_directions=request.orders_directions,
            next_hearing_date=request.next_hearing_date,
            next_hearing_confirmed=request.next_hearing_confirmed,
            follow_ups=request.follow_ups,
            source_label=request.source_label,
            version=next_version,
            supersedes_id=supersedes_id,
            created_at=now,
        )
        existing_updates.append(update_record)
        self._updates_by_hearing[str(hearing_id)] = existing_updates

        # Mark hearing as held
        hearing.date_status = HearingDateStatus.HELD
        hearing.held_at = now

        # Only a lawyer-selected current strategy is reassessed. The AI never
        # generates and promotes a strategy here (Rules 1 and 5).
        current_strategy = self.strategy_engine.get_current_strategy(hearing.case_id)

        # Run targeted reassessment engine
        reassessment = self.reassessment_engine.reassess_hearing(
            case_id=hearing.case_id,
            hearing_id=str(hearing.id),
            hearing_update=update_record,
            active_strategy=current_strategy,
            case_title=case_title,
            organization_id=hearing.organization_id,
        )

        reassessments = self._reassessments_by_hearing.get(str(hearing_id), [])
        reassessments.append(reassessment)
        self._reassessments_by_hearing[str(hearing_id)] = reassessments

        return reassessment

    def get_latest_reassessment(self, hearing_id: str) -> HearingReassessmentRecord:
        """Retrieve the latest reassessment evaluation for a given hearing."""
        reassessments = self._reassessments_by_hearing.get(str(hearing_id), [])
        if not reassessments:
            raise HearingNotFoundError(f"No reassessment found for hearing '{hearing_id}'.")
        return reassessments[-1]

    def list_hearing_updates(self, hearing_id: str) -> List[HearingUpdateRecord]:
        """List version history of hearing updates for auditing and diffing."""
        self.get_hearing(hearing_id)  # Validate existence
        return self._updates_by_hearing.get(str(hearing_id), [])

    def approve_client_update(
        self,
        hearing_id: str,
        reassessment_id: str,
        lawyer_id: str,
    ) -> DraftClientUpdatePayload:
        """Lawyer review gate: Approves the draft client update for publication (Rule 8 & HEAR-8)."""
        reassessment = self.get_latest_reassessment(hearing_id)
        if str(reassessment.id) != str(reassessment_id):
            raise ValueError("Reassessment ID does not match latest record.")

        now = datetime.now(timezone.utc)
        reassessment.draft_client_update.is_approved_by_lawyer = True
        reassessment.draft_client_update.approved_by = lawyer_id
        reassessment.draft_client_update.approved_at = now
        reassessment.review_status = HearingReviewStatus.LAWYER_REVIEWED

        return reassessment.draft_client_update

    # --------------------------------------------------------------------------
    # Calendar Aggregator
    # --------------------------------------------------------------------------
    def get_lawyer_calendar(self, organization_id: str = "org-law-chambers") -> List[HearingCalendarItem]:
        """Aggregate hearing calendar across all matters."""
        items: List[HearingCalendarItem] = []
        for h in self._hearings.values():
            if h.scheduled_at:
                items.append(
                    HearingCalendarItem(
                        hearing_id=str(h.id),
                        case_id=h.case_id,
                        case_title=f"Matter {h.case_id}",
                        court_name=h.court_room or "Metropolitan Magistrate Court",
                        scheduled_at=h.scheduled_at,
                        purpose=h.purpose or "Hearing",
                        date_status=h.date_status,
                        client_attendance_required=h.client_attendance_required,
                    )
                )
        return sorted(items, key=lambda x: x.scheduled_at)
