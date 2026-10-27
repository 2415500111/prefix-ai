"""How a prep step looks to the patient right now. Pure functions, no I/O."""

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum

from prefix_api.domain.enums import CheckInResponse, TimelineEventStatus


class StepState(StrEnum):
    DONE = "DONE"
    # The reminder time has come: the patient should act (or this instruction now applies).
    DUE = "DUE"
    UPCOMING = "UPCOMING"
    # A step needing confirmation whose time has passed without one.
    OVERDUE = "OVERDUE"
    # The patient said they cannot do it; staff have been told.
    PROBLEM = "PROBLEM"


@dataclass(frozen=True, slots=True)
class StepView:
    state: StepState
    can_confirm: bool
    can_report_problem: bool


def step_view(
    *,
    status: TimelineEventStatus,
    requires_confirmation: bool,
    send_at: dt.datetime,
    due_at: dt.datetime,
    last_response: CheckInResponse | None,
    now: dt.datetime,
) -> StepView:
    """State of one non-cancelled timeline event.

    Times decide the state, not whether a reminder went out: patients who use only the
    portal (or have no messaging consent) get no reminders but still see their steps.
    Confirming is possible from the reminder time onwards, so a step cannot be ticked off
    days before it applies; a problem can be reported at any time before it is done.
    """
    if status is TimelineEventStatus.CONFIRMED:
        return StepView(StepState.DONE, can_confirm=False, can_report_problem=False)
    if last_response in (CheckInResponse.NO, CheckInResponse.HELP):
        # Confirming later (once the problem is sorted out) is still allowed.
        return StepView(
            StepState.PROBLEM, can_confirm=requires_confirmation, can_report_problem=False
        )

    if not requires_confirmation:
        if now >= due_at:
            state = StepState.DONE
        elif now >= send_at:
            state = StepState.DUE
        else:
            state = StepState.UPCOMING
        return StepView(state, can_confirm=False, can_report_problem=state is not StepState.DONE)

    if now >= due_at:
        return StepView(StepState.OVERDUE, can_confirm=True, can_report_problem=True)
    if now >= send_at:
        return StepView(StepState.DUE, can_confirm=True, can_report_problem=True)
    return StepView(StepState.UPCOMING, can_confirm=False, can_report_problem=True)
