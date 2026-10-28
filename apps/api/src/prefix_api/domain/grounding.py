"""Checks that an assistant answer stays inside the approved steps (safety rule a).

Pure functions. The LLM is told to use only the steps; these checks verify the parts that
can be verified mechanically before an answer reaches the patient.
"""

import datetime as dt
import re
from collections.abc import Iterable

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def describe_offset(minutes: int) -> str:
    """Step timing for the LLM, e.g. "3 days before the procedure"."""
    if minutes == 0:
        return "at the time of the procedure"
    if minutes % (24 * 60) == 0:
        value, unit = minutes // (24 * 60), "day"
    elif minutes % 60 == 0:
        value, unit = minutes // 60, "hour"
    else:
        value, unit = minutes, "minute"
    return f"{value} {unit}{'' if value == 1 else 's'} before the procedure"


def describe_time_to(scheduled_at: dt.datetime, now: dt.datetime) -> str:
    """Relative time only, never a date (safety rule c), e.g. "in 2 days"."""
    hours = (scheduled_at - now).total_seconds() / 3600
    if hours <= 0:
        return "today"
    if hours < 36:
        value, unit = max(1, round(hours)), "hour"
    else:
        value, unit = round(hours / 24), "day"
    return f"in {value} {unit}{'' if value == 1 else 's'}"


def numbers_in(text: str) -> set[str]:
    """Numbers written in the text (ASCII or Devanagari digits), normalised."""
    found = set()
    for raw in _NUMBER.findall(text.translate(_DEVANAGARI_DIGITS)):
        value = raw.replace(",", ".")
        if "." in value:
            value = value.rstrip("0").rstrip(".")
        found.add(value.lstrip("0") or "0")
    return found


def ungrounded_numbers(answer: str, sources: Iterable[str]) -> set[str]:
    """Numbers in the answer that appear in none of the sources (empty means grounded)."""
    allowed: set[str] = set()
    for source in sources:
        allowed |= numbers_in(source)
    return numbers_in(answer) - allowed
