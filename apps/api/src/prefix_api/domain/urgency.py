"""Which items in the staff notifications are urgent. Fixed rules only, never an LLM.

An item is urgent when any of these is true:

- a red-flag symptom was detected (deterministically, see ``red_flags``) in what the patient
  wrote or asked;
- the patient reported a problem with a prep step marked critical;
- the procedure is within the next 24 hours.

Urgency changes how an item looks and is counted. It never changes the order: the feed is
always newest first.
"""

import datetime as dt
from enum import StrEnum

PROCEDURE_SOON = dt.timedelta(hours=24)


class UrgentReason(StrEnum):
    RED_FLAG = "red_flag"
    CRITICAL_STEP = "critical_step"
    PROCEDURE_SOON = "procedure_soon"


def urgent_reasons(
    *,
    red_flag: bool,
    critical_step: bool,
    scheduled_at: dt.datetime | None,
    now: dt.datetime,
) -> tuple[UrgentReason, ...]:
    """Every rule that makes the item urgent, in a fixed order; empty when it is not."""
    reasons: list[UrgentReason] = []
    if red_flag:
        reasons.append(UrgentReason.RED_FLAG)
    if critical_step:
        reasons.append(UrgentReason.CRITICAL_STEP)
    if scheduled_at is not None and now <= scheduled_at <= now + PROCEDURE_SOON:
        reasons.append(UrgentReason.PROCEDURE_SOON)
    return tuple(reasons)
