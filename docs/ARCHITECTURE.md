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

| Entity | Purpose / key fields |
|---|---|
| **Organization** | Hospital/tenant. Name, region (US/IN), compliance settings, timezone. |
| **Site / Department** | Location and department within an organisation. |
| **User** | Staff account. Role (admin, coordinator, nurse, clinician), org. |
| **Patient** | Demographics (PHI, encrypted), preferred language, contact channels, external EHR ids. |
| **Consent** | Patient, purpose, channel, granted/withdrawn timestamps, legal basis (HIPAA/DPDP). |
| **ProcedureType** | e.g. colonoscopy, CT with contrast, lap chole. Default protocol mapping. |
| **Protocol** | Logical protocol (per org + procedure type). |
| **ProtocolVersion** | Immutable versioned content, status (draft/approved/retired), approved_by, approved_at. |
| **ProtocolStep** | Instruction text, offset from procedure time, conditions, category (diet, medication, logistics), check-in required flag. |
| **ProtocolChunk** | Text chunk + pgvector embedding for grounded retrieval by the assistant. |
| **Procedure** | Patient, procedure type, scheduled datetime, site, clinician, status, external appointment id. |
| **PrepTimeline** | Procedure + the ProtocolVersion it was generated from. |
| **TimelineStep** | Resolved step with due datetime, localised text, completion status. |
| **Reminder** | Timeline step, channel, scheduled/sent/delivered/failed status. |
| **CheckIn / CheckInResponse** | Milestone question, sent time, patient answer, answered time. |
| **Conversation / Message** | Assistant chat history (stored encrypted; redacted copy is what the LLM sees). |
| **Escalation** | Source (red-flag, out-of-scope, risk), severity, assigned nurse, status, resolution notes. |
| **RiskScore** | Procedure, probability, top factors, model version, computed_at. |
| **CoordinatorTask** | Procedure, type, assignee, due, status. |
| **WaitlistEntry** | Patient, procedure type, earliest date, readiness constraints, priority. |
| **SlotOffer** | Released slot, waitlist entry, offered/accepted/expired status. |
| **ProcedureOutcome** | Completed / cancelled, cancellation reason, prep-related flag. Ground truth for analytics and model training. |
| **IntegrationJob** | FHIR/CSV sync run, status, counts, errors. |
| **AuditLog** | Append-only: actor, action, entity type/id, purpose, timestamp, IP/user agent, request id. |

Key relationships: `Organization 1─* Patient 1─* Procedure 1─1 PrepTimeline 1─* TimelineStep 1─* Reminder`; `Protocol 1─* ProtocolVersion 1─* ProtocolStep`; `Procedure 1─* RiskScore`, `Procedure 1─* Escalation`, `Procedure 1─0..1 ProcedureOutcome`.
