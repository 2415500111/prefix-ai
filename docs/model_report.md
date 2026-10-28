# Cancellation risk model report

**Version:** `rules-v1` (`apps/api/src/prefix_api/domain/risk.py`)
**Status:** rules written by hand and not fitted to data. Not validated. Not for clinical decisions.

## What it estimates

The risk that a scheduled procedure is cancelled because the patient did not prepare: steps not done, a reported problem, a nurse escalation, or a patient factor that makes the prep harder. It is a priority score for coordinators. It does not predict cancellation and it does not cancel anything.

## How the score is made

Each rule adds points and gives a reason in plain words. The points are added and capped at 100.

| Rule | Points | Reason shown to the coordinator |
| --- | --- | --- |
| Each prep step that needs confirming and is not done | 8 each, up to 32 | "N prep steps not yet confirmed" |
| Escort or logistics step not confirmed | 12 | "Escort or logistics not confirmed" |
| Each problem reply (NO or HELP) on a step | 15 each, up to 30 | "Reported a problem with a prep step" |
| Each open escalation | 20 each, up to 40 | "Open escalation for a nurse" |
| Urgent escalation (possible red flag) | 20 | "Urgent escalation (possible red flag)" |
| Takes an anticoagulant | 10 | "Takes a blood thinner (anticoagulant)" |
| Diabetic on insulin | 8 | "Diabetic and on insulin" |
| Takes a GLP-1 agonist | 5 | "Takes a GLP-1 agonist" |
| Contrast allergy, contrast CT scan | 15 | "Contrast allergy for a contrast scan" |
| Metal implant, MRI | 15 | "Metal implant for an MRI" |
| eGFR under 30, contrast CT scan | 10 | "Low kidney function (eGFR under 30) for contrast" |
| Within 24 hours, with steps outstanding | 10 | "Procedure within 24 hours with steps outstanding" |

Levels: **HIGH** from 50, **MEDIUM** from 25, otherwise **LOW**.

## What a score does

- The coordinator dashboard lists escalated procedures first, then by score, then by readiness.
- A HIGH score opens one task, "High cancellation risk", for the coordinator, due in an hour. It stays open until someone closes it, and no second task is opened while it is open.
- Scores are recomputed every 15 minutes by the worker. Every score is stored with its reasons and the model version, so changes can be traced.
- Nothing is cancelled automatically.

## Limits

- **The weights are judgement, not measurement.** They have not been compared with real cancellations, so they may be wrong in either direction. Treat the ordering as a starting point for a person to check.
- **No calibration.** A score of 50 does not mean a 50% chance of cancellation.
- **Not tested for fairness.** The rules use age-free condition flags and do not use demographics. Their effect across groups has not been measured.
- **Negation and context are not modelled.** The rules read stored facts, such as "on anticoagulant" or "contrast allergy", as written.
- **Readiness is also a signal.** Steps that were confirmed in error (for example by staff on the phone) raise readiness just as a patient's own confirmation would.

## Future work

A calibrated logistic regression, fitted on past procedures, with a held-out test set and a calibration curve. It would replace these weights only after it beats them on held-out data, and this report would be rewritten to match.
