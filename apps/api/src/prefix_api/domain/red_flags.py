"""Deterministic red-flag detection (safety rule b). Runs before any LLM call.

Deliberately conservative: there is no negation handling ("no chest pain" still matches),
because a false alarm costs a nurse a minute while a missed emergency can cost a life. The
LLM triage is a second layer on top of these rules, never a replacement for them.

English and romanised Hindi use word-boundary regexes. Devanagari uses plain substring
matching: Python's ``\\b`` treats Devanagari vowel signs as non-word characters, which
would split words in the middle.
"""

import re
import unicodedata
from enum import StrEnum


class RedFlag(StrEnum):
    CHEST_PAIN = "CHEST_PAIN"
    BREATHING = "BREATHING"
    SEVERE_BLEEDING = "SEVERE_BLEEDING"
    FAINTING_OR_SEIZURE = "FAINTING_OR_SEIZURE"
    SEVERE_ABDOMINAL_PAIN = "SEVERE_ABDOMINAL_PAIN"
    ALLERGIC_REACTION = "ALLERGIC_REACTION"
    STROKE_SIGNS = "STROKE_SIGNS"


_SEVERE = (
    r"(severe|terrible|unbearable|excruciating|intense|extreme|very bad|really bad|worst|sharp)"
)
_BELLY = r"(stomach|abdominal|abdomen|belly|tummy)"

_LATIN: dict[RedFlag, list[str]] = {
    RedFlag.CHEST_PAIN: [
        r"chest (pain|pains|pressure|tightness|ache|hurts?|is hurting)",
        r"pain in (my |the )?chest",
        r"heart attack",
        r"(seene|sine|chhati|chati) (mein|me|mai) dard",
    ],
    RedFlag.BREATHING: [
        r"(can ?not|can't|cant|unable to|hard to|struggling to) breathe",
        r"(trouble|difficulty|problem) breathing",
        r"short(ness)? of breath",
        r"breathless",
        r"gasping",
        r"(saans|sans|saas) (lene )?(mein|me|mai) (dikkat|taklif|pareshani|problem)",
        r"(saans|sans|saas) (nahi|nahin) (aa|le)",
        r"(saans|sans|saas) phool",
    ],
    RedFlag.SEVERE_BLEEDING: [
        r"(heavy|severe|a lot of|lots of|so much) (bleeding|blood)",
        r"bleeding (a lot|heavily|badly|won't stop|will not stop|wont stop|non ?stop)",
        r"blood in (my |the )?(stool|stools|poo|poop|motion|vomit|urine)",
        r"(vomiting|throwing up|coughing up) blood",
        r"(black|tarry) (stool|stools|poo|poop)",
        r"(bahut|zyada|jyada) khoon",
        r"khoon (aa raha|aa rahi|beh|bah|ki ulti)",
        r"(potty|latrine|mal) (mein|me) khoon",
    ],
    RedFlag.FAINTING_OR_SEIZURE: [
        r"faint(ed|ing)?",
        r"pass(ed)? out",
        r"black(ed)? out",
        r"unconscious",
        r"collapsed?",
        r"lost consciousness",
        r"seizures?",
        r"convulsions?",
        r"behosh",
        r"(mirgi|fit) (aa|pad)",
    ],
    RedFlag.SEVERE_ABDOMINAL_PAIN: [
        rf"{_SEVERE} {_BELLY} (pain|ache|cramps?)",
        rf"{_SEVERE} pain in (my |the )?{_BELLY}",
        rf"{_BELLY} (pain|ache|cramps?) (is |are )?(so |very |really )?{_SEVERE}",
        r"pet (mein|me|mai) (tez|bahut|zyada|jyada) dard",
    ],
    RedFlag.ALLERGIC_REACTION: [
        r"allergic reaction",
        r"anaphyla(xis|ctic)",
        r"(swollen|swelling|swelling up) (of )?(my )?(face|lips?|tongue|throat|eyes)",
        r"(face|lips?|tongue|throat) (is |are )?(swollen|swelling)",
        r"throat (is )?(closing|tight)",
        r"hives",
        r"rash all over",
        r"allergy ho (gayi|gai|gaya)",
        r"(chehra|honth|hoth|gala) (suj|sooj)",
    ],
    RedFlag.STROKE_SIGNS: [
        r"face (is )?droop(ing|y)?",
        r"slurred speech",
        r"(can't|cannot|unable to) (speak|talk) (properly|clearly)",
        r"(numb|numbness|weakness|weak) (on|in) (one|my|the) ?(left|right)? (side|arm|leg)",
        r"sudden (confusion|weakness|numbness)",
        r"(lakwa|laqwa)",
    ],
}

_DEVANAGARI: dict[RedFlag, list[str]] = {
    RedFlag.CHEST_PAIN: ["सीने में दर्द", "सीने मे दर्द", "छाती में दर्द", "छाती मे दर्द", "दिल का दौरा"],
    RedFlag.BREATHING: [
        "सांस लेने में",
        "साँस लेने में",
        "सांस लेने मे",
        "साँस लेने मे",
        "सांस नहीं",
        "साँस नहीं",
        "सांस फूल",
        "साँस फूल",
    ],
    RedFlag.SEVERE_BLEEDING: [
        "बहुत खून",
        "ज़्यादा खून",
        "ज्यादा खून",
        "खून आ रहा",
        "खून की उल्टी",
        "मल में खून",
        "खून बह",
    ],
    RedFlag.FAINTING_OR_SEIZURE: ["बेहोश", "मिर्गी", "दौरा पड़"],
    RedFlag.SEVERE_ABDOMINAL_PAIN: [
        "पेट में तेज़ दर्द",
        "पेट में तेज दर्द",
        "पेट में बहुत दर्द",
        "पेट मे बहुत दर्द",
        "पेट में ज़्यादा दर्द",
    ],
    RedFlag.ALLERGIC_REACTION: ["एलर्जी हो", "चेहरा सूज", "चेहरे पर सूजन", "होंठ सूज", "गला सूज", "पित्ती"],
    RedFlag.STROKE_SIGNS: ["लकवा", "बोलने में दिक्कत", "मुँह टेढ़ा", "मुंह टेढ़ा"],
}

_LATIN_PATTERNS = {
    flag: re.compile(r"\b(" + "|".join(patterns) + r")\b") for flag, patterns in _LATIN.items()
}


def _normalise(text: str) -> str:
    """NFC, casefold, punctuation and symbols to spaces, collapsed whitespace.

    Nukta forms are kept and also matched without the nukta (ज़्यादा and ज्यादा)."""
    text = unicodedata.normalize("NFC", text).casefold().replace("\u2019", "'")
    kept = "".join(" " if unicodedata.category(ch)[0] in "PS" and ch != "'" else ch for ch in text)
    return " ".join(kept.split())


def _without_nukta(text: str) -> str:
    return unicodedata.normalize("NFC", unicodedata.normalize("NFD", text).replace("\u093c", ""))


def detect_red_flags(text: str) -> frozenset[RedFlag]:
    """Every red-flag category the text mentions (empty when none)."""
    normalised = _normalise(text)
    plain = _without_nukta(normalised)
    found = {flag for flag, pattern in _LATIN_PATTERNS.items() if pattern.search(normalised)}
    for flag, phrases in _DEVANAGARI.items():
        if any(_without_nukta(phrase) in plain for phrase in phrases):
            found.add(flag)
    return frozenset(found)
