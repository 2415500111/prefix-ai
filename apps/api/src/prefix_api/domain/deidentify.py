"""Removing identifiers from patient text before it reaches an LLM (safety rule c).

Pattern-based and deliberately aggressive: replacing a harmless number with a placeholder
costs little, leaking an identifier does not. Known names (the patient's own) are passed in
and replaced wherever they appear. Small numbers ("8 hours", "2 tablets") are kept because
prep questions depend on them.
"""

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

_MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|november|december|"
    "jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
)

# Applied in order: earlier patterns win, so e-mails go before IDs and dates before phones.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")),
    ("URL", re.compile(r"\b(https?://|www\.)\S+", re.IGNORECASE)),
    (
        "DATE",
        re.compile(
            r"\b(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}"
            rf"|\d{{1,2}}(st|nd|rd|th)? ({_MONTHS})\.?( \d{{4}})?"
            rf"|({_MONTHS})\.? \d{{1,2}}(st|nd|rd|th)?(,? \d{{4}})?)\b",
            re.IGNORECASE,
        ),
    ),
    # Medical record numbers and similar: letters followed by four or more digits.
    ("ID", re.compile(r"\b[A-Z]{1,5}[-/]?\d{4,}\b", re.IGNORECASE)),
    # Phone numbers: eight or more digits, possibly with spaces, dashes, dots or brackets.
    ("PHONE", re.compile(r"(?<![\w])\+?\d[\d ().-]{6,}\d(?![\w])")),
    # Any remaining long digit run (Aadhaar, PIN code, account numbers).
    ("ID", re.compile(r"\b\d{6,}\b")),
]
_SELF_INTRODUCTION = re.compile(r"\b(my name is|mera naam)\s+([A-Za-z][\w'-]*)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Redaction:
    text: str
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def redacted(self) -> bool:
        return bool(self.counts)


def deidentify(text: str, *, names: Iterable[str] = ()) -> Redaction:
    counts: Counter[str] = Counter()

    def sub(label: str, pattern: re.Pattern[str], value: str) -> str:
        def replace(match: re.Match[str]) -> str:
            if label == "PHONE" and sum(ch.isdigit() for ch in match.group(0)) < 8:
                return match.group(0)
            counts[label] += 1
            return f"[{label}]"

        return pattern.sub(replace, value)

    result = text
    for name in sorted({n.strip() for n in names if len(n.strip()) >= 2}, key=len, reverse=True):
        result = sub("NAME", re.compile(rf"(?<!\w){re.escape(name)}(?!\w)", re.IGNORECASE), result)

    def introduction(match: re.Match[str]) -> str:
        counts["NAME"] += 1
        return f"{match.group(1)} [NAME]"

    result = _SELF_INTRODUCTION.sub(introduction, result)
    for label, pattern in _PATTERNS:
        result = sub(label, pattern, result)
    return Redaction(text=result, counts=dict(counts))
