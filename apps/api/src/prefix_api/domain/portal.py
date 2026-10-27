"""How a prep step looks to the patient right now. Pure functions, no I/O."""

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum

from prefix_api.domain.enums import CheckInResponse, TimelineEventStatus

# Time a patient has to confirm a step after it applies before it shows as overdue.
CONFIRMATION_GRACE = dt.timedelta(hours=4)


class StepState(StrEnum):
    # Confirmed by the patient.
    DONE = "DONE"
    # The patient should do this and confirm it now.
    DUE = "DUE"
    UPCOMING = "UPCOMING"
    # Needed confirmation and the grace period has passed without one.
    OVERDUE = "OVERDUE"
    # An instruction (nothing to confirm) that applies from now on, e.g. "stop clopidogrel".
    ACTIVE = "ACTIVE"
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
    days before it applies; a problem can be reported at any time until it is done.
    """
    if status is TimelineEventStatus.CONFIRMED:
        return StepView(StepState.DONE, can_confirm=False, can_report_problem=False)
    if last_response in (CheckInResponse.NO, CheckInResponse.HELP):
        # Confirming later (once the problem is sorted out) is still allowed.
        return StepView(
            StepState.PROBLEM, can_confirm=requires_confirmation, can_report_problem=False
        )
    if now < send_at:
        return StepView(StepState.UPCOMING, can_confirm=False, can_report_problem=True)
    if not requires_confirmation:
        return StepView(StepState.ACTIVE, can_confirm=False, can_report_problem=True)
    if now >= due_at + CONFIRMATION_GRACE:
        return StepView(StepState.OVERDUE, can_confirm=True, can_report_problem=True)
    return StepView(StepState.DUE, can_confirm=True, can_report_problem=True)
