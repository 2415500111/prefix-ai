# Compliance

This is an engineering summary of how Prefix AI meets the HIPAA (US) and India DPDP Act 2023 duties it is built for, with the gaps stated. It is not legal advice. A hospital deploying Prefix AI still needs its own privacy officer, its own agreements with its vendors, and a review of this file against its own obligations.

## Where personal data lives

| Data | Where | Protected by |
|---|---|---|
| Names, date of birth, phone, email, MRN | `patient` table | AES-256-GCM per field, with a key ID so keys can rotate. Lookups use HMAC blind indexes, so phone, email and MRN can be matched without storing them in clear. |
| Free text from patients (check-in replies, escalation summaries, messages) | `check_in`, `escalation`, `message` tables | The same field encryption. |
| Prep plans and approved protocols | `prep_protocol`, `prep_step` | Not personal data. They are clinician content, so they are stored in clear. |
| Who did what, when | `audit_log` | Append-only: a database trigger rejects `UPDATE`, `DELETE` and `TRUNCATE`. |

## Requirements

| Requirement | How it is met | Status |
|---|---|---|
| **Consent capture** | `consent_to_message` is required at registration, CSV import and update. The consent timestamp is recorded. Nothing is messaged without consent. | Met. The source of consent (a signed form, a phone call) is not stored. Keep that record in the hospital system. |
| **Consent withdrawal** | Setting `consent_to_message` to false is audited, and the timestamp is updated. Dispatch checks consent again before every send, so pending reminders are skipped. | Met. |
| **Purpose limitation** | Every audit row records a purpose (for example `prep_reminder`, `waitlist_backfill`, `bulk_import`). The AI assistant sees only the patient's own approved protocol. | Met. |
| **Data minimisation** | Prompts to the AI assistant carry no names, phone numbers, e-mails or record numbers. Console and log output masks recipients. Logs record request method, path, status and timing, never bodies or query strings. A test checks that a personal e-mail never reaches the logs. | Met. Request paths contain record IDs (UUIDs), which are not names or contact details but are still identifiers. |
| **Audit logs** | Every read and write of patient data is audited in the service layer, not in the routers. A backstop middleware flags a patient-data route that writes no audit row. | Met. Audit rows from a request that fails are rolled back with it, the same as the data change they describe. |
| **Access control** | Role-based permissions checked in the router and again in the service. Every query filters on the tenant. Tests cover cross-tenant access. Login attempts are limited per account (10 failed attempts in 15 minutes) and per client address. | Met. The limits are per process; see `docs/DEPLOYMENT.md`. |
| **Encryption in transit** | The API and web app expect TLS at the edge. Production responses send `Strict-Transport-Security`. | Met when deployed behind TLS. TLS is the operator's to set up. |
| **Encryption at rest** | Personal fields are encrypted in the application. Database volumes should be encrypted by the operator's platform. | Field encryption met. Volume encryption is an operator requirement. |
| **Retention and erasure** | Nothing automated. Records stay until someone deletes them in the database. | **Gap.** A retention schedule and an erasure workflow (including audit-safe deletion) are not built. |
| **Breach notification support** | The audit log, the export of procedure lists and the escalation inbox make it possible to see what was accessed. There is no breach workflow, no notification template and no timer. | **Gap.** Plan this with the hospital's incident process before go-live. |
| **Subject access** | A patient can see their own prep plan and calendar in the portal. There is no export of all of a patient's data. | **Gap.** A subject-access export is not built. |
| **Security headers** | The API and web app send `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, a content security policy and, in production, HSTS. | Met. The web policy allows inline scripts, which Next.js needs for its page data; nonces would remove that. |

## Vendors

Prefix AI sends personal data to a messaging provider (Twilio for SMS and WhatsApp, SMTP for e-mail) only when a reminder is due and the patient has consented. It sends the AI assistant's prompt to the Claude API with names, phone numbers, e-mail addresses and record numbers removed. A patient's own question is passed on as written, so the assistant's answers must still be reviewed and red flags are escalated before the model is called. Each vendor relationship needs its own agreement, including a business associate agreement with a HIPAA covered entity. The hospital signs those, not Prefix AI.

## Before go-live

1. Decide the retention period for each record type and build the deletion job, or accept the gap in writing.
2. Write the breach procedure and name the person who runs it.
3. Record how consent was obtained for every patient imported from a file.
4. Sign the vendor agreements listed above.
5. Turn off guest login (`ENABLE_GUEST_LOGIN=false`) and check the production settings in `docs/DEPLOYMENT.md`.
