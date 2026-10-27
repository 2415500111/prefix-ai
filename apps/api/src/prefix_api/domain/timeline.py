"""Pure timeline math: when each prep step is due and when its reminder is sent.

Rules
- Offsets that are whole days use wall-clock arithmetic in the facility timezone ("1 day
  before a 09:00 procedure" is 09:00 the previous day, even across a DST change). Other
  offsets use exact elapsed time ("2 hours before" is always 120 minutes), because fasting
  windows are physiological.
- Quiet hours are 22:00-07:00 in the patient's local time (the facility timezone). A
  non-critical reminder that falls inside them is moved EARLIER, to 21:30 the evening the
  quiet period starts: arriving early is safer than arriving after the step is due.
  Critical steps are always sent at their exact time.
- A step whose time has already passed when the timeline is built (late booking) is sent
  as a catch-up straight away. A non-critical catch-up cannot be moved into the past, so if
  "now" is in quiet hours it waits until 07:00, and is skipped if that is after the
  procedure starts.
"""

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

MINUTES_PER_DAY = 24 * 60
QUIET_START = dt.time(22, 0)
QUIET_END = dt.time(7, 0)
EVENING_SEND = dt.time(21, 30)


@dataclass(frozen=True, slots=True)
class StepTiming:
    due_at: dt.datetime
    send_at: dt.datetime | None
    """None means the reminder should not be sent (the moment has passed)."""


def _require_aware(value: dt.datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetimes must be timezone-aware")


def due_at(scheduled_at: dt.datetime, offset_minutes: int, timezone: str) -> dt.datetime:
    """When a step is due, in UTC."""
    _require_aware(scheduled_at)
    if offset_minutes > 0 and offset_minutes % MINUTES_PER_DAY == 0:
        local = scheduled_at.astimezone(ZoneInfo(timezone))
        # Aware datetime + timedelta is wall-clock arithmetic in Python.
        shifted = local - dt.timedelta(days=offset_minutes // MINUTES_PER_DAY)
        return shifted.astimezone(dt.UTC)
    # Subtract in UTC: on a local datetime Python would do wall-clock arithmetic.
    return scheduled_at.astimezone(dt.UTC) - dt.timedelta(minutes=offset_minutes)


def in_quiet_hours(moment: dt.datetime, timezone: str) -> bool:
    local_time = moment.astimezone(ZoneInfo(timezone)).time()
    return local_time >= QUIET_START or local_time < QUIET_END


def _evening_before_quiet(moment: dt.datetime, timezone: str) -> dt.datetime:
    """21:30 local on the evening the quiet period containing ``moment`` began."""
    local = moment.astimezone(ZoneInfo(timezone))
    day = local.date() if local.time() >= QUIET_START else local.date() - dt.timedelta(days=1)
    return dt.datetime.combine(day, EVENING_SEND, tzinfo=ZoneInfo(timezone)).astimezone(dt.UTC)


def _next_morning(moment: dt.datetime, timezone: str) -> dt.datetime:
    """07:00 local at the end of the quiet period containing ``moment``."""
    local = moment.astimezone(ZoneInfo(timezone))
    day = local.date() + dt.timedelta(days=1) if local.time() >= QUIET_START else local.date()
    return dt.datetime.combine(day, QUIET_END, tzinfo=ZoneInfo(timezone)).astimezone(dt.UTC)


def plan_step(
    *,
    scheduled_at: dt.datetime,
    offset_minutes: int,
    timezone: str,
    is_critical: bool,
    now: dt.datetime,
) -> StepTiming:
    """Work out when a step is due and when its reminder should go out."""
    _require_aware(now)
    due = due_at(scheduled_at, offset_minutes, timezone)
    if now >= scheduled_at:
        return StepTiming(due_at=due, send_at=None)

    if is_critical:
        return StepTiming(due_at=due, send_at=max(due, now))

    send = due
    if in_quiet_hours(send, timezone):
        send = _evening_before_quiet(send, timezone)
    if send < now:
        # Catch-up: send now, unless now is itself in quiet hours.
        send = _next_morning(now, timezone) if in_quiet_hours(now, timezone) else now
        if send >= scheduled_at:
            return StepTiming(due_at=due, send_at=None)
    return StepTiming(due_at=due, send_at=send)
