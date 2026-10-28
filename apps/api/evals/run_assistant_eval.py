"""Evaluate the AI Prep Assistant against the labelled cases in assistant_cases.toml.

Run with `make eval`. Deterministic cases (red flags, benign questions, de-identification,
and the rule part of injection cases) always run and need no network. LLM cases need
ANTHROPIC_API_KEY; without it they are reported as skipped, not passed.

Exit status is 1 when any case that ran failed, so a missed red flag stops the build.
"""

import sys
import tomllib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prefix_api.core.config import get_settings
from prefix_api.domain.deidentify import deidentify
from prefix_api.domain.red_flags import detect_red_flags
from prefix_api.services.assistant.llm import AssistantLLM, StepContext, build_assistant_llm

CASES_FILE = Path(__file__).with_name("assistant_cases.toml")
CATEGORIES = ("red_flag", "benign", "deidentify", "injection", "out_of_protocol", "in_protocol")


@dataclass(frozen=True, slots=True)
class Result:
    case_id: str
    category: str
    status: str  # "pass", "fail" or "skip"
    detail: str = ""


def check_rules(case: dict[str, Any]) -> Result | None:
    """The deterministic layer. None when the case has no rule expectation."""
    category = case["category"]
    found = {flag.value for flag in detect_red_flags(case["question"])}
    if "flags" in case:
        missing = sorted(set(case["flags"]) - found)
        if missing:
            return Result(case["id"], category, "fail", f"missed red flags: {', '.join(missing)}")
        return Result(case["id"], category, "pass")
    if category == "benign":
        if found:
            return Result(case["id"], category, "fail", f"false alarm: {', '.join(sorted(found))}")
        return Result(case["id"], category, "pass")
    if category == "deidentify":
        text = deidentify(case["question"], names=case.get("names", [])).text
        leaked = [value for value in case["absent"] if value in text]
        if leaked:
            return Result(case["id"], category, "fail", f"identifier survived: {', '.join(leaked)}")
        return Result(case["id"], category, "pass")
    return None


def check_llm(case: dict[str, Any], llm: AssistantLLM) -> Result:
    category = case["category"]
    if case["llm"] == "not_prep":
        triage = llm.triage(case["question"], names=[])
        if triage.about_prep:
            return Result(case["id"], category, "fail", "treated as a question about the prep plan")
        return Result(case["id"], category, "pass")

    steps = [
        StepContext(
            ref=step["ref"],
            title=step["title"],
            instruction=step["instruction"],
            timing=step["timing"],
        )
        for step in case["steps"]
    ]
    answer = llm.answer(
        case["question"],
        names=[],
        steps=steps,
        procedure="Colonoscopy",
        time_to_procedure="in 2 days",
        language="en",
    )
    missing = sorted(set(case["expect_refs"]) - set(answer.cited_refs))
    if not answer.covered:
        return Result(case["id"], category, "fail", "not answered from the steps")
    if missing:
        return Result(case["id"], category, "fail", f"did not cite: {', '.join(missing)}")
    return Result(case["id"], category, "pass")


def run(cases: list[dict[str, Any]], llm: AssistantLLM | None) -> list[Result]:
    results: list[Result] = []
    for case in cases:
        rule = check_rules(case)
        if rule is not None:
            results.append(rule)
        if "llm" in case:
            if llm is None:
                results.append(
                    Result(case["id"], case["category"], "skip", "needs ANTHROPIC_API_KEY")
                )
            else:
                results.append(check_llm(case, llm))
    return results


def report(results: list[Result], cases: list[dict[str, Any]]) -> None:
    counts: dict[str, Counter[str]] = {category: Counter() for category in CATEGORIES}
    for result in results:
        counts[result.category][result.status] += 1

    print(f"{'category':<16}{'pass':>6}{'fail':>6}{'skip':>6}{'rate':>8}")
    for category in CATEGORIES:
        passed, failed, skipped = (counts[category][s] for s in ("pass", "fail", "skip"))
        ran = passed + failed
        rate = f"{100 * passed / ran:.0f}%" if ran else "-"
        print(f"{category:<16}{passed:>6}{failed:>6}{skipped:>6}{rate:>8}")

    flags = [case for case in cases if "flags" in case and case["category"] == "red_flag"]
    caught = sum(1 for r in results if r.category == "red_flag" and r.status == "pass")
    print(f"\nred flags caught: {caught} of {len(flags)} labelled red-flag cases")
    false_alarms = sum(1 for r in results if r.category == "benign" and r.status == "fail")
    benign_total = sum(1 for case in cases if case["category"] == "benign")
    print(f"false alarms on ordinary questions: {false_alarms} of {benign_total}")

    for result in results:
        if result.status == "fail":
            print(f"FAIL {result.case_id}: {result.detail}")
    skipped = sum(1 for r in results if r.status == "skip")
    print(f"\n{len(cases)} cases, {len(results)} checks, {skipped} skipped")


def main() -> int:
    cases: list[dict[str, Any]] = tomllib.loads(CASES_FILE.read_text(encoding="utf-8"))["case"]
    llm = build_assistant_llm(get_settings())
    if llm is None:
        print(
            "ANTHROPIC_API_KEY is not set: LLM cases are skipped, deterministic cases still run.\n"
        )
    results = run(cases, llm)
    report(results, cases)
    return 1 if any(result.status == "fail" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
