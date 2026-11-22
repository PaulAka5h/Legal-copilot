"""Case progress derived from stored data (never a hand-set or mock stage).

Stages, in order:
  opened     - the case exists (always complete)
  scheduled  - complete once a hearing is on record; current until then
  held       - complete once a hearing has been held (an update was recorded);
               current while a hearing is on record but none is held yet
  closed     - complete only when the case status is closed; otherwise upcoming.
               It is never "current": hearings, not the bar, decide when a case ends.

A closed case has every stage complete. The same function serves the lawyer
(all hearings) and the client (only client-visible signals).
"""

from typing import Literal

from pydantic import BaseModel

StageId = Literal["opened", "scheduled", "held", "closed"]
StageState = Literal["complete", "current", "upcoming"]


class CaseProgressStage(BaseModel):
    id: StageId
    state: StageState


def case_progress(*, status: str, has_hearing: bool, has_held_hearing: bool) -> list[CaseProgressStage]:
    if status == "closed":
        return [CaseProgressStage(id=stage, state="complete") for stage in ("opened", "scheduled", "held", "closed")]
    scheduled = has_hearing or has_held_hearing
    return [
        CaseProgressStage(id="opened", state="complete"),
        CaseProgressStage(id="scheduled", state="complete" if scheduled else "current"),
        CaseProgressStage(id="held", state="complete" if has_held_hearing else "current" if scheduled else "upcoming"),
        CaseProgressStage(id="closed", state="upcoming"),
    ]
