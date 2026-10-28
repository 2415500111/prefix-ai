"""Cancellation risk, version 1: transparent rules with written weights. Pure functions, no I/O.

Each rule adds points and says why, so a coordinator sees the reasons, not a bare number. The
weights are judgement calls, not fitted to data; docs/model_report.md says so and lists the
limits. A learned model (logistic regression, calibrated) is future work.
"""

from dataclasses import dataclass

from prefix_api.domain.enums import RiskLevel

MODEL_VERSION = "rules-v1"
HIGH_FROM = 50
MEDIUM_FROM = 25
SOON = 24  # hours before the procedure


@dataclass(frozen=True, slots=True)
class RiskInputs:
    unconfirmed_steps: int
    logistics_unconfirmed: bool
    problem_replies: int
    open_escalations: int
    urgent_escalation: bool
    on_anticoagulant: bool
    diabetic_on_insulin: bool
    on_glp1_agonist: bool
    contrast_allergy: bool
    metal_implant: bool
    egfr: float | None
    procedure_code: str
    hours_to_procedure: float


@dataclass(frozen=True, slots=True)
class Factor:
    feature: str
    points: int
    label: str


@dataclass(frozen=True, slots=True)
class RiskResult:
    score: int
    level: RiskLevel
    factors: tuple[Factor, ...]


def _factors(inputs: RiskInputs) -> list[Factor]:
    found: list[Factor] = []
    if inputs.unconfirmed_steps:
        points = min(32, 8 * inputs.unconfirmed_steps)
        found.append(
            Factor(
                "unconfirmed_steps",
                points,
                f"{inputs.unconfirmed_steps} prep step"
                f"{'s' if inputs.unconfirmed_steps != 1 else ''} not yet confirmed",
            )
        )
    if inputs.logistics_unconfirmed:
        found.append(Factor("logistics", 12, "Escort or logistics not confirmed"))
    if inputs.problem_replies:
        found.append(
            Factor(
                "problem_replies",
                min(30, 15 * inputs.problem_replies),
                "Reported a problem with a prep step",
            )
        )
    if inputs.open_escalations:
        found.append(
            Factor(
                "open_escalations",
                min(40, 20 * inputs.open_escalations),
                "Open escalation for a nurse",
            )
        )
    if inputs.urgent_escalation:
        found.append(Factor("urgent_escalation", 20, "Urgent escalation (possible red flag)"))
    if inputs.on_anticoagulant:
        found.append(Factor("anticoagulant", 10, "Takes a blood thinner (anticoagulant)"))
    if inputs.diabetic_on_insulin:
        found.append(Factor("insulin", 8, "Diabetic and on insulin"))
    if inputs.on_glp1_agonist:
        found.append(Factor("glp1", 5, "Takes a GLP-1 agonist"))
    if inputs.contrast_allergy and inputs.procedure_code == "CT_CONTRAST":
        found.append(Factor("contrast_allergy", 15, "Contrast allergy for a contrast scan"))
    if inputs.metal_implant and inputs.procedure_code == "MRI":
        found.append(Factor("metal_implant", 15, "Metal implant for an MRI"))
    if inputs.egfr is not None and inputs.egfr < 30 and inputs.procedure_code == "CT_CONTRAST":
        found.append(Factor("low_egfr", 10, "Low kidney function (eGFR under 30) for contrast"))
    if (inputs.unconfirmed_steps or inputs.logistics_unconfirmed) and (
        0 <= inputs.hours_to_procedure <= SOON
    ):
        found.append(Factor("soon", 10, "Procedure within 24 hours with steps outstanding"))
    return found


def score(inputs: RiskInputs) -> RiskResult:
    factors = sorted(_factors(inputs), key=lambda f: (-f.points, f.feature))
    total = min(100, sum(f.points for f in factors))
    if total >= HIGH_FROM:
        level = RiskLevel.HIGH
    elif total >= MEDIUM_FROM:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW
    return RiskResult(score=total, level=level, factors=tuple(factors))
