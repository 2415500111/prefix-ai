"""Protocol step conditions: a small, safe JSON rule language (no `eval`).

A condition decides whether a step applies to a patient, using only whitelisted patient
condition fields. Each node is a JSON object with exactly one key:

    {"all": [<cond>, ...]}     every child is true (an empty list is true)
    {"any": [<cond>, ...]}     at least one child is true (an empty list is false)
    {"not": <cond>}            negation
    {"flag": "<field>"}        a boolean field is true
    {"missing": "<field>"}     a numeric field has no value on file
    {"compare": {"field": "<numeric field>", "op": "lt|lte|gt|gte|eq|ne", "value": <number>}}

A comparison against a missing value is false. When "unknown" should count as risky,
say so explicitly, e.g. {"any": [{"missing": "egfr_value"}, {"compare": ...}]}.
"""

import operator
from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import Any

BOOLEAN_FIELDS = frozenset(
    {
        "on_anticoagulant",
        "diabetic_on_insulin",
        "on_glp1_agonist",
        "has_contrast_allergy",
        "has_metal_implant",
    }
)
NUMERIC_FIELDS = frozenset({"egfr_value"})

_OPERATORS: dict[str, Callable[[Decimal, Decimal], bool]] = {
    "lt": operator.lt,
    "lte": operator.le,
    "gt": operator.gt,
    "gte": operator.ge,
    "eq": operator.eq,
    "ne": operator.ne,
}
MAX_DEPTH = 8
MAX_NODES = 64

type Condition = Mapping[str, Any]
type PatientFacts = Mapping[str, bool | Decimal | None]


class InvalidConditionError(ValueError):
    """The condition JSON does not follow the grammar."""


def validate_condition(condition: object) -> None:
    """Raise InvalidConditionError unless ``condition`` is a well-formed rule."""
    _validate(condition, depth=0, counter=[0])


def _validate(node: object, *, depth: int, counter: list[int]) -> None:
    counter[0] += 1
    if counter[0] > MAX_NODES:
        raise InvalidConditionError(f"Condition has more than {MAX_NODES} nodes")
    if depth > MAX_DEPTH:
        raise InvalidConditionError(f"Condition is nested deeper than {MAX_DEPTH} levels")
    if not isinstance(node, Mapping) or len(node) != 1:
        raise InvalidConditionError("Each condition must be an object with exactly one key")

    [(kind, arg)] = node.items()
    match kind:
        case "all" | "any":
            if not isinstance(arg, list):
                raise InvalidConditionError(f"'{kind}' expects a list")
            for child in arg:
                _validate(child, depth=depth + 1, counter=counter)
        case "not":
            _validate(arg, depth=depth + 1, counter=counter)
        case "flag":
            if arg not in BOOLEAN_FIELDS:
                raise InvalidConditionError(f"Unknown flag '{arg}'")
        case "missing":
            if arg not in NUMERIC_FIELDS:
                raise InvalidConditionError(f"Unknown numeric field '{arg}'")
        case "compare":
            _validate_compare(arg)
        case _:
            raise InvalidConditionError(f"Unknown condition type '{kind}'")


def _validate_compare(arg: object) -> None:
    if not isinstance(arg, Mapping) or set(arg) != {"field", "op", "value"}:
        raise InvalidConditionError("'compare' needs exactly 'field', 'op' and 'value'")
    if arg["field"] not in NUMERIC_FIELDS:
        raise InvalidConditionError(f"Unknown numeric field '{arg['field']}'")
    if arg["op"] not in _OPERATORS:
        raise InvalidConditionError(f"Unknown operator '{arg['op']}'")
    value = arg["value"]
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise InvalidConditionError("'compare' value must be a number")
    try:
        Decimal(str(value))
    except ArithmeticError as exc:
        raise InvalidConditionError("'compare' value must be a number") from exc


def evaluate(condition: Condition | None, facts: PatientFacts) -> bool:
    """True if the step applies. ``None`` (no condition) always applies.

    Callers must validate conditions when they are saved; evaluation re-checks nothing
    beyond what is needed to stay safe, and treats anything unexpected as an error.
    """
    if condition is None:
        return True
    validate_condition(condition)
    return _eval(condition, facts)


def _eval(node: Condition, facts: PatientFacts) -> bool:
    [(kind, arg)] = node.items()
    match kind:
        case "all":
            return all(_eval(child, facts) for child in arg)
        case "any":
            return any(_eval(child, facts) for child in arg)
        case "not":
            return not _eval(arg, facts)
        case "flag":
            return facts.get(arg) is True
        case "missing":
            return facts.get(arg) is None
        case "compare":
            current = facts.get(arg["field"])
            if current is None or isinstance(current, bool):
                return False
            return _OPERATORS[arg["op"]](Decimal(str(current)), Decimal(str(arg["value"])))
        case _:  # pragma: no cover - rejected by validate_condition
            raise InvalidConditionError(f"Unknown condition type '{kind}'")


def patient_facts(patient: object) -> dict[str, bool | Decimal | None]:
    """Extract only the whitelisted condition fields from a Patient-like object."""
    return {field: getattr(patient, field) for field in BOOLEAN_FIELDS | NUMERIC_FIELDS}
