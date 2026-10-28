# Integrations

Phase 11 ships CSV import, the quick start for a hospital that has no interface to its scheduling system yet. FHIR R4 is planned future work (see the end of this file).

## CSV import

Coordinators and admins import from **Import records** in the dashboard, or with `POST /imports/patients` and `POST /imports/appointments`.

- The first line is the header. A header matches a field when its name is the field name, ignoring case, spaces and hyphens. `mapping` in the request maps other header names to fields, for example `{"DOB": "date_of_birth"}`.
- Columns that match no field are ignored and listed in the report, so a typo shows up rather than disappearing.
- A file is capped at 1 MB and 500 rows. Split a larger file.
- `dry_run` defaults to `true`. A dry run checks every row and saves nothing. A real import (`dry_run: false`) saves only when every row is valid, so a file is never half imported.

### Patients

| Column | Required | Notes |
|---|---|---|
| `first_name`, `last_name` | yes | Up to 100 characters each. |
| `date_of_birth` | yes | `YYYY-MM-DD`. |
| `phone` | no | E.164, with country code, e.g. `+919812300001`. |
| `email` | no | |
| `mrn` | no | Must be unique in the hospital. |
| `preferred_language` | no | e.g. `en`, `hi`. |
| `preferred_channel` | no | `SMS`, `WHATSAPP`, `EMAIL` or `PORTAL`. |
| `consent_to_message` | no | `yes` or `no`. Defaults to `no`, so nothing is messaged without consent. |
| `on_anticoagulant`, `diabetic_on_insulin`, `on_glp1_agonist`, `has_contrast_allergy`, `has_metal_implant` | no | `yes` or `no`. |
| `egfr_value` | no | A number from 0 to 200. |

### Appointments

| Column | Required | Notes |
|---|---|---|
| `patient_mrn` or `patient_phone` | one of them | Must match exactly one existing patient. |
| `facility` | yes | The facility name, ignoring case. |
| `procedure_code` | yes | The procedure code, ignoring case, e.g. `COLONOSCOPY`. |
| `scheduled_at` | yes | ISO 8601 with its UTC offset, e.g. `2026-11-02T09:00:00+05:30`. Must be in the future. |
| `arrival_at` | no | Same format as `scheduled_at`. |
| `duration_minutes` | no | 5 to 1440. Defaults to the procedure's duration. |

An appointment is booked by the same service as a typed booking, so the procedure's approved protocol builds the prep timeline, and the usual reminders follow.

## Safety properties

- **Same rules as a typed entry.** Every row goes through the patient and appointment services. Consent, audit, protocol and timeline rules all apply.
- **No values in error messages.** A report says `line 3, column email, is not valid`. It never repeats what was typed, so a report or a screenshot of one does not spread patient data.
- **Audited.** Each created record is audited as usual. A committed import also writes one `import` audit row with the record count. Each existing patient matched to an appointment is audited as a read.
- **Permissions.** Patient imports need the patient write permission and appointment imports need the appointment write permission. Viewers are refused.
- **Consent is recorded as given.** The consent timestamp is the time of import. The source of the consent, such as a signed form, is not stored, so check it before importing (see `docs/COMPLIANCE.md`, Phase 12).

## Future work: FHIR R4

Planned for after v1.0.0, as CLAUDE.md describes: read and write `Patient`, `Appointment`, `ServiceRequest`, `Procedure` and `MedicationStatement` resources, so that scheduling and medication sync can run without CSV. The import service's validation and per-row savepoints are the parts to reuse; a FHIR adapter would translate each resource into the same typed inputs.
