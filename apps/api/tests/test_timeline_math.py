import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from prefix_api.domain.timeline import due_at, in_quiet_hours, plan_step

KOLKATA = "Asia/Kolkata"
NEW_YORK = "America/New_York"
DAY = 24 * 60


def local(timezone: str, year: int, month: int, day: int, hour: int, minute: int) -> dt.datetime:
    return dt.datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(timezone))


def at(timezone: str, moment: dt.datetime) -> str:
    return moment.astimezone(ZoneInfo(timezone)).strftime("%Y-%m-%d %H:%M")


# A procedure at 09:00 local on 10 March 2027 (Kolkata has no DST).
PROCEDURE = local(KOLKATA, 2027, 3, 10, 9, 0)
LONG_AGO = PROCEDURE - dt.timedelta(days=30)


class TestDueAt:
    def test_day_offsets_keep_the_clock_time(self) -> None:
        assert at(KOLKATA, due_at(PROCEDURE, 3 * DAY, KOLKATA)) == "2027-03-07 09:00"

    def test_hour_offsets_are_exact_durations(self) -> None:
        assert at(KOLKATA, due_at(PROCEDURE, 18 * 60, KOLKATA)) == "2027-03-09 15:00"
        assert at(KOLKATA, due_at(PROCEDURE, 90, KOLKATA)) == "2027-03-10 07:30"

    def test_zero_offset_is_the_procedure_time(self) -> None:
        assert due_at(PROCEDURE, 0, KOLKATA) == PROCEDURE

    def test_result_is_utc(self) -> None:
        assert due_at(PROCEDURE, 60, KOLKATA).tzinfo == dt.UTC

    def test_day_offsets_across_dst_keep_wall_clock(self) -> None:
        # US DST starts 14 March 2027; a 09:00 procedure on the 16th.
        procedure = local(NEW_YORK, 2027, 3, 16, 9, 0)

        week_before = due_at(procedure, 7 * DAY, NEW_YORK)

        assert at(NEW_YORK, week_before) == "2027-03-09 09:00"
        # ...which is 7 days minus one hour of real time.
        assert procedure - week_before == dt.timedelta(days=7) - dt.timedelta(hours=1)

    def test_hour_offsets_across_dst_are_real_elapsed_time(self) -> None:
        # 05:00 on 14 March 2027 is just after clocks jump from 02:00 to 03:00.
        procedure = local(NEW_YORK, 2027, 3, 14, 5, 0)

        four_hours_before = due_at(procedure, 4 * 60, NEW_YORK)

        assert procedure - four_hours_before == dt.timedelta(hours=4)
        assert at(NEW_YORK, four_hours_before) == "2027-03-14 00:00"

    def test_naive_datetimes_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            due_at(dt.datetime(2027, 3, 10, 9, 0), 60, KOLKATA)  # noqa: DTZ001


@pytest.mark.parametrize(
    ("hour", "minute", "quiet"),
    [(21, 59, False), (22, 0, True), (23, 30, True), (0, 0, True), (6, 59, True), (7, 0, False)],
)
def test_quiet_hours_boundaries(hour: int, minute: int, quiet: bool) -> None:
    assert in_quiet_hours(local(KOLKATA, 2027, 3, 9, hour, minute), KOLKATA) is quiet


class TestPlanStep:
    def plan(
        self, offset: int, *, critical: bool = False, now: dt.datetime = LONG_AGO
    ) -> tuple[str, str | None]:
        timing = plan_step(
            scheduled_at=PROCEDURE,
            offset_minutes=offset,
            timezone=KOLKATA,
            is_critical=critical,
            now=now,
        )
        send = None if timing.send_at is None else at(KOLKATA, timing.send_at)
        return at(KOLKATA, timing.due_at), send

    def test_daytime_reminder_is_sent_when_due(self) -> None:
        assert self.plan(3 * DAY) == ("2027-03-07 09:00", "2027-03-07 09:00")

    def test_non_critical_reminder_in_quiet_hours_moves_to_the_evening_before(self) -> None:
        # Due 03:00 on the 10th (6 hours before) -> sent 21:30 on the 9th.
        assert self.plan(6 * 60) == ("2027-03-10 03:00", "2027-03-09 21:30")

    def test_late_evening_reminder_moves_to_2130_same_evening(self) -> None:
        # Due 22:30 on the 9th -> sent 21:30 on the 9th.
        assert self.plan(10 * 60 + 30) == ("2027-03-09 22:30", "2027-03-09 21:30")

    def test_critical_reminder_keeps_its_exact_time_in_quiet_hours(self) -> None:
        assert self.plan(6 * 60, critical=True) == ("2027-03-10 03:00", "2027-03-10 03:00")

    def test_missed_critical_step_is_sent_as_catch_up_now(self) -> None:
        now = local(KOLKATA, 2027, 3, 8, 14, 0)  # booked 2 days before
        assert self.plan(7 * DAY, critical=True, now=now) == (
            "2027-03-03 09:00",
            "2027-03-08 14:00",
        )

    def test_missed_non_critical_step_is_sent_now_in_the_daytime(self) -> None:
        now = local(KOLKATA, 2027, 3, 8, 14, 0)
        assert self.plan(3 * DAY, now=now) == ("2027-03-07 09:00", "2027-03-08 14:00")

    def test_non_critical_catch_up_at_night_waits_for_the_morning(self) -> None:
        now = local(KOLKATA, 2027, 3, 8, 23, 0)
        assert self.plan(3 * DAY, now=now) == ("2027-03-07 09:00", "2027-03-09 07:00")

    def test_non_critical_catch_up_is_skipped_if_morning_is_after_the_procedure(self) -> None:
        early_procedure_now = local(KOLKATA, 2027, 3, 10, 1, 0)  # 01:00, procedure at 09:00
        timing = plan_step(
            scheduled_at=local(KOLKATA, 2027, 3, 10, 6, 0),
            offset_minutes=3 * DAY,
            timezone=KOLKATA,
            is_critical=False,
            now=early_procedure_now,
        )
        assert timing.send_at is None

    def test_nothing_is_sent_once_the_procedure_has_started(self) -> None:
        assert self.plan(60, critical=True, now=PROCEDURE)[1] is None
