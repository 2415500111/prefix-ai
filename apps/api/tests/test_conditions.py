from decimal import Decimal
from typing import Any

import pytest

from prefix_api.domain.conditions import (
    MAX_DEPTH,
    MAX_NODES,
    InvalidConditionError,
    evaluate,
    validate_condition,
)

BASE: dict[str, Any] = {
    "on_anticoagulant": False,
    "diabetic_on_insulin": False,
    "on_glp1_agonist": False,
    "has_contrast_allergy": False,
    "has_metal_implant": False,
    "egfr_value": None,
}


def facts(**overrides: Any) -> dict[str, Any]:
    return {**BASE, **overrides}


def test_no_condition_always_applies() -> None:
    assert evaluate(None, facts()) is True


@pytest.mark.parametrize(("value", "expected"), [(True, True), (False, False)])
def test_flag(value: bool, expected: bool) -> None:
    assert evaluate({"flag": "on_anticoagulant"}, facts(on_anticoagulant=value)) is expected


def test_all_any_not() -> None:
    insulin_and_glp1 = {"all": [{"flag": "diabetic_on_insulin"}, {"flag": "on_glp1_agonist"}]}
    either = {"any": [{"flag": "diabetic_on_insulin"}, {"flag": "on_glp1_agonist"}]}

    assert evaluate(insulin_and_glp1, facts(diabetic_on_insulin=True)) is False
    assert evaluate(either, facts(diabetic_on_insulin=True)) is True
    assert evaluate({"not": either}, facts()) is True
    assert evaluate({"all": []}, facts()) is True
    assert evaluate({"any": []}, facts()) is False


@pytest.mark.parametrize(
    ("op", "threshold", "egfr", "expected"),
    [
        ("lt", 30, Decimal("29.9"), True),
        ("lt", 30, Decimal("30"), False),
        ("lte", 30, Decimal("30"), True),
        ("gt", 60, Decimal("61"), True),
        ("gte", 60, Decimal("60"), True),
        ("eq", 45, Decimal("45.0"), True),
        ("ne", 45, Decimal("45"), False),
        ("lt", "30.5", Decimal("30.4"), True),
    ],
)
def test_numeric_comparisons(op: str, threshold: object, egfr: Decimal, expected: bool) -> None:
    rule = {"compare": {"field": "egfr_value", "op": op, "value": threshold}}

    assert evaluate(rule, facts(egfr_value=egfr)) is expected


def test_comparison_on_missing_value_is_false_and_missing_can_be_tested() -> None:
    low = {"compare": {"field": "egfr_value", "op": "lt", "value": 30}}
    unknown_or_low = {"any": [{"missing": "egfr_value"}, low]}

    assert evaluate(low, facts(egfr_value=None)) is False
    assert evaluate(unknown_or_low, facts(egfr_value=None)) is True
    assert evaluate(unknown_or_low, facts(egfr_value=Decimal("90"))) is False


def test_unknown_facts_in_input_are_ignored() -> None:
    assert evaluate({"flag": "on_anticoagulant"}, facts(name="x", on_anticoagulant=True)) is True


@pytest.mark.parametrize(
    "rule",
    [
        "on_anticoagulant",
        [],
        {},
        {"flag": "on_anticoagulant", "not": {"flag": "on_glp1_agonist"}},
        {"flag": "is_vip"},
        {"flag": "__class__"},
        {"compare": {"field": "first_name", "op": "eq", "value": 1}},
        {"compare": {"field": "egfr_value", "op": "__import__", "value": 1}},
        {"compare": {"field": "egfr_value", "op": "lt", "value": "abc"}},
        {"compare": {"field": "egfr_value", "op": "lt", "value": True}},
        {"compare": {"field": "egfr_value", "op": "lt"}},
        {"all": {"flag": "on_anticoagulant"}},
        {"missing": "on_anticoagulant"},
        {"exec": "import os"},
    ],
)
def test_malformed_conditions_are_rejected(rule: object) -> None:
    with pytest.raises(InvalidConditionError):
        validate_condition(rule)
    if isinstance(rule, dict):
        with pytest.raises(InvalidConditionError):
            evaluate(rule, facts())


def test_depth_and_size_limits() -> None:
    deep: dict[str, Any] = {"flag": "on_anticoagulant"}
    for _ in range(MAX_DEPTH + 1):
        deep = {"not": deep}
    wide = {"any": [{"flag": "on_anticoagulant"}] * MAX_NODES}

    with pytest.raises(InvalidConditionError, match="deeper"):
        validate_condition(deep)
    with pytest.raises(InvalidConditionError, match="nodes"):
        validate_condition(wide)
