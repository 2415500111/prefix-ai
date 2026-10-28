"""Deterministic safety layer: red-flag rules (rule b) and de-identification (rule c)."""

import pytest

from prefix_api.domain.deidentify import deidentify
from prefix_api.domain.red_flags import RedFlag, detect_red_flags


@pytest.mark.parametrize(
    ("text", "flag"),
    [
        ("I have chest pain since this morning", RedFlag.CHEST_PAIN),
        ("My chest feels tight? Chest tightness when walking", RedFlag.CHEST_PAIN),
        ("seene mein dard ho raha hai", RedFlag.CHEST_PAIN),
        ("मुझे सीने में दर्द हो रहा है", RedFlag.CHEST_PAIN),
        ("I can't breathe properly", RedFlag.BREATHING),
        ("shortness of breath after the prep drink", RedFlag.BREATHING),
        ("saans lene mein dikkat hai", RedFlag.BREATHING),
        ("मुझे साँस लेने में तकलीफ है", RedFlag.BREATHING),
        ("there is a lot of blood in my stool", RedFlag.SEVERE_BLEEDING),
        ("I am vomiting blood", RedFlag.SEVERE_BLEEDING),
        ("potty mein khoon aa raha hai", RedFlag.SEVERE_BLEEDING),
        ("मल में खून आ रहा है", RedFlag.SEVERE_BLEEDING),
        ("I fainted in the bathroom", RedFlag.FAINTING_OR_SEIZURE),
        ("my father passed out", RedFlag.FAINTING_OR_SEIZURE),
        ("main behosh ho gaya tha", RedFlag.FAINTING_OR_SEIZURE),
        ("वह बेहोश हो गई", RedFlag.FAINTING_OR_SEIZURE),
        ("severe stomach pain after the solution", RedFlag.SEVERE_ABDOMINAL_PAIN),
        ("my belly pain is really bad", RedFlag.SEVERE_ABDOMINAL_PAIN),
        ("pet mein tez dard hai", RedFlag.SEVERE_ABDOMINAL_PAIN),
        ("पेट में तेज़ दर्द है", RedFlag.SEVERE_ABDOMINAL_PAIN),
        ("पेट में तेज दर्द है", RedFlag.SEVERE_ABDOMINAL_PAIN),
        ("I think I'm having an allergic reaction", RedFlag.ALLERGIC_REACTION),
        ("my lips are swollen after the tablet", RedFlag.ALLERGIC_REACTION),
        ("चेहरा सूज गया है", RedFlag.ALLERGIC_REACTION),
        ("her face is drooping and she has slurred speech", RedFlag.STROKE_SIGNS),
        ("उसे लकवा मार गया", RedFlag.STROKE_SIGNS),
    ],
)
def test_red_flags_are_detected_in_english_and_hindi(text: str, flag: RedFlag) -> None:
    assert flag in detect_red_flags(text)


@pytest.mark.parametrize(
    "text",
    [
        "Can I drink black coffee the day before?",
        "When should I stop eating?",
        "Is apple juice a clear liquid?",
        "क्या मैं प्रक्रिया से एक दिन पहले चाय पी सकता हूँ?",
        "kya main dawai le sakta hoon",
        "I have a mild headache from not eating",
        "Who will take me home after the procedure?",
    ],
)
def test_ordinary_prep_questions_are_not_red_flags(text: str) -> None:
    assert detect_red_flags(text) == frozenset()


def test_negation_is_not_trusted() -> None:
    # Conservative by design: a nurse double-checks rather than risk a missed emergency.
    assert RedFlag.CHEST_PAIN in detect_red_flags("I don't have chest pain, just a question")


def test_several_flags_at_once() -> None:
    flags = detect_red_flags("Chest pain and I fainted")

    assert flags == {RedFlag.CHEST_PAIN, RedFlag.FAINTING_OR_SEIZURE}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Call me on +91 98111 22233 please", "Call me on [PHONE] please"),
        ("my number is 9811122233", "my number is [PHONE]"),
        ("email asha.patel@example.com", "email [EMAIL]"),
        ("see https://example.com/my-report?id=7", "see [URL]"),
        ("MRN AB123456 and aadhaar 1234 5678 9012", "MRN [ID] and aadhaar [PHONE]"),
        ("my procedure is on 12/11/2026", "my procedure is on [DATE]"),
        ("booked for 14 November 2026 at 9", "booked for [DATE] at 9"),
        ("on March 3rd", "on [DATE]"),
        ("pin code 560001", "pin code [ID]"),
        ("my name is Rahul and I take metformin", "my name is [NAME] and I take metformin"),
    ],
)
def test_identifiers_are_replaced(text: str, expected: str) -> None:
    assert deidentify(text).text == expected


def test_known_names_are_replaced_case_insensitively() -> None:
    result = deidentify(
        "Asha Patel here. asha needs to know about fasting", names=["Asha", "Patel"]
    )

    assert result.text == "[NAME] [NAME] here. [NAME] needs to know about fasting"
    assert result.counts == {"NAME": 3}


def test_prep_details_survive() -> None:
    text = "Can I take 2 tablets of metformin 8 hours before? I drank 500 ml at 10:30"

    result = deidentify(text, names=["Ravi"])

    assert result.text == text
    assert not result.redacted
