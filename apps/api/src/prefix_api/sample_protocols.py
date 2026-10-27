"""SAMPLE prep protocols shipped for demos and as starting points.

They are seeded as DRAFTs and can only be approved with an explicit acknowledgement that a
clinical team has reviewed and adapted them. The wording is deliberately generic: medicine
steps tell patients to ask their care team and never give doses or tell them to stop a
medicine on their own.
"""

from dataclasses import dataclass, field
from typing import Any

from prefix_api.domain.enums import StepCategory

SAMPLE_LABEL = "SAMPLE – must be reviewed by your clinical team before use"  # noqa: RUF001

DAY = 24 * 60
HOUR = 60

_D = StepCategory


@dataclass(frozen=True, slots=True)
class SampleStep:
    offset_minutes: int
    title: str
    instruction_text: str
    category: StepCategory
    requires_confirmation: bool = False
    is_critical: bool = False
    conditions: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class SampleProtocol:
    procedure_code: str
    title: str
    steps: list[SampleStep] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"{self.title} ({SAMPLE_LABEL})"

    @property
    def description(self) -> str:
        return (
            f"{SAMPLE_LABEL}. This example shows the structure of a prep protocol. Every "
            "step, time and condition must be checked and adapted by your clinicians to your "
            "own local guidance before approval."
        )


_ANTICOAGULANT = SampleStep(
    7 * DAY,
    "Ask about your blood thinner",
    "You take a blood thinner. Contact your care team this week to ask whether, and when, "
    "to pause it before your procedure. Do not stop or change it unless they tell you to.",
    _D.MEDICATION,
    requires_confirmation=True,
    is_critical=True,
    conditions={"flag": "on_anticoagulant"},
)
_INSULIN = SampleStep(
    7 * DAY,
    "Ask about your insulin",
    "You use insulin. Ask your care team how to manage your insulin while you prepare. "
    "Do not change your dose unless they tell you to.",
    _D.MEDICATION,
    requires_confirmation=True,
    is_critical=True,
    conditions={"flag": "diabetic_on_insulin"},
)
_GLP1 = SampleStep(
    7 * DAY,
    "Tell us about your GLP-1 medicine",
    "You take a GLP-1 medicine (for example for diabetes or weight). Tell your care team "
    "and ask whether anything needs to change before your procedure.",
    _D.MEDICATION,
    requires_confirmation=True,
    is_critical=True,
    conditions={"flag": "on_glp1_agonist"},
)
_ESCORT = SampleStep(
    3 * DAY,
    "Arrange someone to take you home",
    "You will have sedation, so you must not drive or travel home alone afterwards. "
    "Arrange for an adult to take you home and confirm when this is done.",
    _D.LOGISTICS,
    requires_confirmation=True,
    is_critical=True,
)
_ARRIVAL = SampleStep(
    0,
    "On the day",
    "Bring your ID, a list of the medicines you take, and your escort's phone number. "
    "Arrive at the time shown in your appointment details.",
    _D.LOGISTICS,
)

SAMPLE_PROTOCOLS: list[SampleProtocol] = [
    SampleProtocol(
        "COLONOSCOPY",
        "Colonoscopy preparation",
        [
            _ANTICOAGULANT,
            _INSULIN,
            _GLP1,
            SampleStep(
                3 * DAY,
                "Start a low-fibre diet",
                "Start the low-fibre diet described in your preparation instructions. "
                "Avoid seeds, nuts, whole grains, and raw fruit and vegetables unless your "
                "care team says otherwise.",
                _D.DIET,
            ),
            _ESCORT,
            SampleStep(
                2 * DAY,
                "Collect your bowel preparation",
                "Make sure you have your bowel preparation kit and have read its instructions.",
                _D.BOWEL_PREP,
                requires_confirmation=True,
            ),
            SampleStep(
                1 * DAY,
                "Clear liquids only",
                "From today, have clear liquids only, as described in your instructions "
                "(for example water, clear broth, apple juice). No solid food, milk, or red "
                "or purple drinks.",
                _D.DIET,
                requires_confirmation=True,
                is_critical=True,
            ),
            SampleStep(
                18 * HOUR,
                "First part of your bowel preparation",
                "Take the first part of your bowel preparation at the time shown in your "
                "instructions, and drink the extra clear liquids they describe.",
                _D.BOWEL_PREP,
                requires_confirmation=True,
                is_critical=True,
            ),
            SampleStep(
                5 * HOUR,
                "Second part of your bowel preparation",
                "Take the second part of your bowel preparation at the time shown in your "
                "instructions.",
                _D.BOWEL_PREP,
                requires_confirmation=True,
                is_critical=True,
            ),
            SampleStep(
                2 * HOUR,
                "Stop drinking",
                "Stop drinking all liquids now, unless your care team told you otherwise.",
                _D.FASTING,
                requires_confirmation=True,
                is_critical=True,
            ),
            _ARRIVAL,
        ],
    ),
    SampleProtocol(
        "GENERAL_SURGERY",
        "General surgery under anesthesia preparation",
        [
            SampleStep(
                14 * DAY,
                "Pre-operative tests",
                "Complete the blood tests and checks your care team has requested before "
                "your surgery.",
                _D.LAB,
                requires_confirmation=True,
                is_critical=True,
            ),
            _ANTICOAGULANT,
            _INSULIN,
            _GLP1,
            SampleStep(
                7 * DAY,
                "Complete your forms",
                "Complete and sign your consent and pre-admission forms.",
                _D.PAPERWORK,
                requires_confirmation=True,
            ),
            _ESCORT,
            SampleStep(
                1 * DAY,
                "Get ready the evening before",
                "Shower as your instructions describe. Remove jewellery, nail polish and "
                "make-up before you come in.",
                _D.LOGISTICS,
            ),
            SampleStep(
                8 * HOUR,
                "Stop eating",
                "Stop eating now, including chewing gum and sweets, unless your care team "
                "told you otherwise.",
                _D.FASTING,
                requires_confirmation=True,
                is_critical=True,
            ),
            SampleStep(
                2 * HOUR,
                "Stop drinking",
                "Stop drinking clear liquids now, unless your care team told you otherwise.",
                _D.FASTING,
                requires_confirmation=True,
                is_critical=True,
            ),
            _ARRIVAL,
        ],
    ),
    SampleProtocol(
        "CT_CONTRAST",
        "CT scan with contrast preparation",
        [
            SampleStep(
                3 * DAY,
                "Kidney blood test",
                "Your care team may need a recent kidney blood test before you receive "
                "contrast. If you have not had one recently, contact them to arrange it.",
                _D.LAB,
                requires_confirmation=True,
                is_critical=True,
                conditions={
                    "any": [
                        {"missing": "egfr_value"},
                        {"compare": {"field": "egfr_value", "op": "lt", "value": 45}},
                    ]
                },
            ),
            SampleStep(
                3 * DAY,
                "Contrast allergy",
                "You have reported a contrast allergy. Contact your care team before your "
                "scan; they will decide whether you need special preparation. Do not take "
                "any new medicine unless they tell you to.",
                _D.MEDICATION,
                requires_confirmation=True,
                is_critical=True,
                conditions={"flag": "has_contrast_allergy"},
            ),
            SampleStep(
                3 * DAY,
                "Ask about your diabetes medicines",
                "You use insulin. Ask your care team whether any of your diabetes medicines "
                "need to change around your contrast scan.",
                _D.MEDICATION,
                requires_confirmation=True,
                conditions={"flag": "diabetic_on_insulin"},
            ),
            SampleStep(
                4 * HOUR,
                "Stop eating",
                "Stop eating now unless your instructions say otherwise. You can keep "
                "drinking water.",
                _D.FASTING,
                requires_confirmation=True,
                is_critical=True,
            ),
            SampleStep(
                1 * HOUR,
                "Before you leave home",
                "Wear comfortable clothes without metal fastenings, and bring a list of the "
                "medicines you take.",
                _D.LOGISTICS,
            ),
        ],
    ),
    SampleProtocol(
        "MRI",
        "MRI scan preparation",
        [
            SampleStep(
                3 * DAY,
                "Tell us about your implant",
                "You have a metal implant or medical device. Contact your care team with its "
                "details (for example your implant card) so they can confirm the scan is safe "
                "for you.",
                _D.LOGISTICS,
                requires_confirmation=True,
                is_critical=True,
                conditions={"flag": "has_metal_implant"},
            ),
            SampleStep(
                1 * DAY,
                "Eating and drinking",
                "Follow any eating and drinking instructions in your appointment letter. If "
                "there are none, you can eat and drink as usual.",
                _D.DIET,
            ),
            SampleStep(
                1 * HOUR,
                "Before you leave home",
                "Leave jewellery and other metal items at home. Tell the staff about any "
                "implants, tattoos or medicine patches.",
                _D.LOGISTICS,
            ),
        ],
    ),
]
