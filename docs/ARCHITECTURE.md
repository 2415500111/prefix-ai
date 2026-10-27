# Prefix AI — Architecture

## 1. System diagram

```
                ┌────────────────────┐        ┌──────────────────────┐
                │  Patient channels  │        │  Coordinators/Nurses │
                │ SMS·WhatsApp·Email │        │     /Clinicians      │
                │   ·Patient web     │        │    (browser)         │
                └─────────┬──────────┘        └──────────┬───────────┘
                          │                              │
                          ▼                              ▼
                ┌───────────────────────────────────────────────────┐
                │                 apps/web (Next.js)                │
                │  Patient prep portal · Coordinator dashboard ·    │
                │  Protocol editor · Analytics                      │
                └─────────────────────────┬─────────────────────────┘
                                          │ HTTPS / JSON
                                          ▼
┌──────────────┐   FHIR R4 / CSV  ┌───────────────────────────────────────────────┐
│ Hospital EHR │◄────────────────►│               apps/api (FastAPI)              │
│ (Epic, etc.) │                  │  Routers  →  Services  →  Repositories        │
└──────────────┘                  │  ┌─────────────────────────────────────────┐  │
                                  │  │ Protocol · Timeline · Check-in · Risk · │  │
                                  │  │ Assistant · Escalation · Backfill ·     │  │
                                  │  │ Analytics · Integrations · Consent      │  │
                                  │  └─────────────────────────────────────────┘  │
                                  │  Cross-cutting: AuthN/Z · Audit log ·         │
                                  │  PHI redactor · Red-flag detector             │
                                  └───────┬──────────────────┬──────────────┬─────┘
                                          │                  │              │
                         SQLAlchemy 2     │      enqueue     │              │ redacted,
                                          ▼      tasks       ▼              │ grounded
                     ┌──────────────────────────┐   ┌───────────────┐       │ prompts
                     │ PostgreSQL + pgvector    │   │    Redis      │       ▼
                     │ (app data, audit log,    │   │ (broker/cache)│  ┌──────────────┐
                     │  protocol embeddings)    │   └───────┬───────┘  │  Claude API  │
                     └────────────▲─────────────┘           │          │ (anthropic   │
                                  │                         ▼          │  SDK,        │
                                  │           ┌──────────────────────┐ │  LLM_MODEL)  │
                                  └───────────┤ apps/worker (Celery) ├─►──────────────┘
                                              │ reminders · check-in │
                                              │ scheduling · risk    │──► SMS/WhatsApp/
                                              │ scoring · EHR sync · │    Email providers
                                              │ backfill offers      │
                                              └──────────────────────┘
```

All LLM calls go through one `LLMClient` wrapper in the API/worker. It applies the PHI redactor, injects the patient's approved protocol as the only grounding source, reads the model from `LLM_MODEL`, and records the interaction (without PHI) in the audit log.

## 2. Data flow: procedure scheduled → coordinator action

```
 1. PROCEDURE SCHEDULED
    EHR (FHIR Appointment/ServiceRequest) or CSV import ──► Integrations service
      • upsert Patient, Procedure; record Consent status
      • match ProcedureType ──► active, approved ProtocolVersion
      • audit: create Patient/Procedure
                │
                ▼
 2. TIMELINE GENERATED
    Timeline service (deterministic, no LLM):
      • resolve protocol steps + conditions (e.g. anticoagulant? diabetic?)
        against patient medications/flags
      • anchor each step to procedure datetime (T-7d, T-24h, T-6h …)
      • persist PrepTimeline + TimelineSteps
    Optional LLM pass: rephrase/translate step text into patient's language
      (redacted input; output reviewed against source step; original kept)
                │
                ▼
 3. REMINDERS SENT
    Worker (Celery beat + ETA tasks):
      • schedule Reminder per TimelineStep per channel
      • send at due time; store delivery status; retry on failure
      • respect quiet hours, consent, and channel opt-outs
                │
                ▼
 4. CHECK-INS
    Worker sends CheckIn prompts at milestones ──► patient replies
      • structured answers stored as CheckInResponse
      • free-text / questions ──► Assistant service:
          a) deterministic red-flag detector ── hit ──► Escalation (nurse)
                                                       + "contact care team /
                                                          emergency services"
          b) protocol-grounded LLM answer ── out of scope ──► Escalation
          c) answer returned, conversation audit-logged
                │
                ▼
 5. RISK SCORE
    Risk service (on every check-in, missed check-in, and on a schedule):
      • build features (check-in answers, missed steps, engagement,
        procedure type, lead time, prior no-shows/cancellations)
      • scikit-learn model ──► calibrated probability + top factors
      • persist RiskScore (model version recorded); threshold crossings
        create CoordinatorTask
                │
                ▼
 6. COORDINATOR ACTION
    Dashboard worklist sorted by risk / escalations:
      • call patient, resend instructions, assign nurse, reschedule
      • release slot ──► Backfill service finds eligible WaitlistEntries
        (can complete prep in time) ──► sends SlotOffer ──► accept ──►
        new Procedure ──► back to step 2
      • outcome (completed / cancelled + reason) recorded ──► feeds
        Analytics/ROI and future model training
```

Every step that reads or writes patient data writes an `AuditLog` entry from the service layer.

## 3. Main database entities

Implemented in `apps/api/src/prefix_api/db/models/` (migration `0002`). Every tenant table carries `organization_id`, and every repository query filters on it. Primary keys are UUIDv7. Enums are stored as `VARCHAR` with `CHECK` constraints, so adding a value is a simple migration.

| Entity | Purpose / key fields |
|---|---|
| **Organization** | Tenant (hospital or group). Name, slug, country, default timezone. |
| **Facility** | Site within an org. Name, IANA timezone (timelines are computed in it), address, maps link. |
| **User** (`app_user`) | Staff account. Email (globally unique), argon2 password hash, role: ADMIN, COORDINATOR, NURSE, CLINICIAN, VIEWER. |
| **RefreshToken** | SHA-256 hash of an opaque refresh token. Rotates on each use; a `family_id` lets reuse of a rotated token revoke the whole login. |
| **Patient** | **Encrypted** first/last name, DOB, phone, email, MRN (AES-256-GCM, column-bound). HMAC blind indexes for exact lookup by phone/email/MRN. Preferred language and channel, messaging consent and its timestamp, and condition flags (anticoagulant, insulin, GLP-1, contrast allergy, eGFR, metal implant). |
| **PatientMagicLink** | Hash of a single-use patient login token, its expiry and when it was used. |
| **ProcedureType** | Code, name, default duration, OR cost per minute, sedation flag. |
| **Appointment** | Patient, facility, procedure type, clinician, approved protocol version, scheduled/arrival time, status (SCHEDULED/READY/AT_RISK/CANCELLED/COMPLETED), cancellation reason (prep-related reasons are flagged in code). |
| **PrepProtocol** | One immutable version (`family_id` + `version`). Status DRAFT/APPROVED/RETIRED. A DB CHECK requires an approver and approval time on APPROVED rows. `is_sample` marks seeded examples. |
| **PrepStep** | Offset in minutes before the procedure, title, instruction text, category (DIET/FASTING/MEDICATION/BOWEL_PREP/LAB/LOGISTICS/PAPERWORK), requires_confirmation, is_critical, `conditions` JSON. |
| **PatientTimelineEvent** | One step scheduled for one appointment (unique per appointment+step, which makes sending idempotent). Due/send times and status. |
| **CheckIn** | Milestone question, status, YES/NO/HELP/OTHER response, and encrypted free-text reply. |
| **Message** | Inbound/outbound message on SMS/WhatsApp/email/portal. Encrypted body, plus the encrypted approved original whenever the body is a translation of it. |
| **RiskScore** | 0–100 score, LOW/MEDIUM/HIGH, readable factors JSON, model version. |
| **WaitlistEntry** | Patient, procedure type, optional facility, date window, prep already done, priority, status. |
| **Escalation** | Source (red flag, out of protocol, patient-reported problem, high risk, staff), severity, status, encrypted summary and resolution note, assignee. |
| **Task** | Coordinator/nurse work item: type, status, assignee, due time, links to appointment, patient or escalation. |
| **AuditLog** | Append-only (DB trigger rejects UPDATE/DELETE/TRUNCATE). Actor type and id, action, entity, patient id, purpose, IP, user agent, request id, and PHI-free details. No foreign keys, so it outlives the records it describes. |

## 4. Security model

- **Staff auth:** email + password (argon2id) → 15-minute JWT access token + rotating opaque refresh token. Every request re-checks that the user is active and that their role hasn't changed.
- **RBAC:** `domain/permissions.py` maps roles to permissions. Routers reject early with `require(Permission)`, and services check again. VIEWER has no access to patient-level data.
- **Patient auth:** staff issue a single-use magic link. The token sits in the URL **fragment**, so it never reaches server logs, and is redeemed in a POST body for a 12-hour patient session.
- **Tenant isolation:** the organization comes only from the token, never from the request body. A record in another organization returns 404.
- **Audit (safety rule d):** services write audit rows in the same transaction as the access. The DB session commits *before* the response is sent. A middleware backstop logs an error and writes a generic audit row if a patient-data route ever succeeds without one.
- **PII at rest:** see Patient above. Keys come from `PII_ENCRYPTION_KEYS` (rotation supported) and `PII_BLIND_INDEX_KEY`. Development keys are rejected in production.

## 5. Protocol Engine (safety rule a)

- **Versions.** A protocol is a family of immutable versions (`family_id` + `version`). Only a DRAFT can change. Editing an APPROVED or RETIRED version creates the next DRAFT, and a family has at most one draft at a time.
- **Approval.** Only CLINICIAN and ADMIN roles can approve. A draft needs at least one step. Approving embeds every step (`EmbeddingProvider`; default `local-hashing-v1`, offline and deterministic) and retires the family's previously approved version. SAMPLE protocols (`is_sample`) need an explicit `acknowledge_sample`.
- **Database guards (migration 0003).** Triggers reject any change to an approved or retired version other than APPROVED → RETIRED, reject deleting such versions, reject edits to their steps, and reject any `patient_timeline_event` that points at a step of a non-approved protocol. This holds even if application code is bypassed.
- **Conditions.** Each step can carry a JSON rule (`all`, `any`, `not`, `flag`, `missing`, `compare`) over whitelisted patient fields. It is validated on save and evaluated without `eval` (`domain/conditions.py`). `applicable_steps()` raises if given a non-approved protocol.
- **Web.** `/dashboard/protocols` (list), `/new`, `/[id]` (steps in time order, versions, approve) and `/[id]/edit` (step builder). Staff sessions use the backend-for-frontend pattern: tokens live in httpOnly cookies set by Server Actions, and `src/proxy.ts` refreshes them before expiry.

## 6. Smart Prep Timeline and messaging

- **Building the timeline** (`services/timeline.py`, `domain/timeline.py`). Booking picks the procedure's approved protocol; if several exist, the coordinator must choose one. Applicable steps become `patient_timeline_event` rows with a due time and a send time in the facility timezone.
  - Whole-day offsets keep wall-clock time across DST; hour and minute offsets are exact durations.
  - **Quiet hours** run 22:00–07:00. A non-critical reminder that falls inside them moves earlier, to 21:30 the evening before. Critical steps keep their exact time.
  - Steps already past at booking are sent as catch-ups.
  - Rescheduling cancels the old events and builds new ones from the newest approved version. Cancelling the appointment cancels every event and expires open check-ins.
- **Dispatch** (`services/dispatch.py`, Celery beat every 60 s). Due events are claimed with `FOR UPDATE SKIP LOCKED` (PENDING → SENDING) and sent one per transaction.
  - The Message row is written before the provider call, and a partial unique index allows only one outbound message per event. An interrupted send is marked FAILED rather than retried, so a patient is never messaged twice.
  - Sending requires messaging consent and a contact for the preferred channel. Reminder text comes only from the approved step.
- **Providers** (`services/messaging/`): Console (development), Twilio SMS and WhatsApp, SMTP email, selected by `MESSAGING_PROVIDER`.
- **Translation** (`services/translation.py`): Claude translates only approved step text (no PHI) into the patient's language. The approved original is stored next to the translation, and any error, refusal or implausible output means the original is sent instead.
- **Replies** (`POST /webhooks/twilio`, Twilio-signature verified): YES, NO and HELP in English and Hindi update the latest open check-in.
  - NO on a critical step opens a HIGH escalation and marks the appointment AT_RISK.
  - HELP escalates to a nurse.
  - Any other text is stored and queued for a person, never interpreted automatically.
