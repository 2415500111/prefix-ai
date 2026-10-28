"""Mechanical checks that keep assistant answers inside the approved steps."""

import datetime as dt

import pytest

from prefix_api.domain.grounding import (
    describe_offset,
    describe_time_to,
    numbers_in,
    ungrounded_numbers,
)

NOW = dt.datetime(2026, 11, 10, 6, 0, tzinfo=dt.UTC)


@pytest.mark.parametrize(
    ("minutes", "text"),
    [
        (0, "at the time of the procedure"),
        (30, "30 minutes before the procedure"),
        (60, "1 hour before the procedure"),
        (8 * 60, "8 hours before the procedure"),
        (24 * 60, "1 day before the procedure"),
        (5 * 24 * 60, "5 days before the procedure"),
    ],
)
def test_step_timing_is_relative(minutes: int, text: str) -> None:
    assert describe_offset(minutes) == text


@pytest.mark.parametrize(
    ("delta", "text"),
    [
        (dt.timedelta(hours=-1), "today"),
        (dt.timedelta(minutes=20), "in 1 hour"),
        (dt.timedelta(hours=20), "in 20 hours"),
        (dt.timedelta(days=2, hours=3), "in 2 days"),
    ],
)
def test_time_to_procedure_never_includes_a_date(delta: dt.timedelta, text: str) -> None:
    assert describe_time_to(NOW + delta, NOW) == text


def test_numbers_are_normalised_across_scripts() -> None:
    assert numbers_in("Drink ५०० ml, stop 8 hours before, 2.50 mg, 007") == {"500", "8", "2.5", "7"}


def test_answers_may_only_use_numbers_from_their_sources() -> None:
    sources = ["1 day before the procedure Clear liquids Drink 2 litres of clear liquids."]

    assert ungrounded_numbers("Drink २ litres, starting 1 day before.", sources) == set()
    assert ungrounded_numbers("Drink 3 litres and take 5 mg.", sources) == {"3", "5"}
