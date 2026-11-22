"""Case progress derived from stored data (never a hand-set or mock stage).

Stages, in order:
  opened     - the case exists (always reached)
  scheduled  - at least one hearing is on record
  held       - at least one hearing has been held (a hearing update was recorded)
  closed     - the case is closed

The first stage that is not complete is "current"; the rest are "upcoming".
A closed case has every stage complete. The same function serves the lawyer
(all hearings) and the client (only client-visible signals), so both bars move
when hearings or the status change.
"""

from typing import Literal

from pydantic import BaseModel

StageId = Literal["opened", "scheduled", "held", "closed"]
StageState = Literal["complete", "current", "upcoming"]
STAGE_IDS: tuple[StageId, ...] = ("opened", "scheduled", "held", "closed")


class CaseProgressStage(BaseModel):
    id: StageId
    state: StageState


def case_progress(*, status: str, has_hearing: bool, has_held_hearing: bool) -> list[CaseProgressStage]:
    closed = status == "closed"
    reached = {
        "opened": True,
        "scheduled": closed or has_hearing or has_held_hearing,
        "held": closed or has_held_hearing,
        "closed": closed,
    }
    stages: list[CaseProgressStage] = []
    current_assigned = False
    for stage_id in STAGE_IDS:
        if reached[stage_id]:
            state: StageState = "complete"
        elif not current_assigned:
            state, current_assigned = "current", True
        else:
            state = "upcoming"
        stages.append(CaseProgressStage(id=stage_id, state=state))
    return stages
