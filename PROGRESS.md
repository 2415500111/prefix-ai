# Prefix AI — Build Progress

Each phase gets a short plan before work starts. Tick a phase only when lint, type-check, all tests, and `docker compose build` pass, then record the date and a 2–3 line summary (see "Git workflow" in CLAUDE.md).

## Resume point

**Status:** Phases 0–10 merged (latest tag `v0.10.0`; 6b is `v0.6.1`, 8 is `v0.8.0`). Phase 11 (integrations, lite) complete on `phase-11-integrations`, merging to `main` as `v0.11.0`.
**Goal:** demo-ready v1.0.0 as fast as possible, without weakening the safety rules. Speed rules: related tests while developing, full suite once per plan item, Playwright once per phase, pre-commit on changed files, push after each item, wait for CI only before merging into main. About 60–90 minutes per phase. A problem that takes over 15 minutes is logged under "Known issues" and skipped.
**Next:** Phase 12 (release, lite) on `phase-12-release`, once Phase 11 is merged.

**Revised order** (decided with the owner; numbers stay the same, the sequence changes):
1. Phase 6 — AI Prep Assistant (finish)
2. Phase 6b — Guest login and demo mode (new, tag `v0.6.1`)
3. Phase 8 — Coordinator Dashboard (full, `v0.8.0`)
4. Phase 7 — Risk score, v1 transparent rules only; ML model is future work (`v0.7.0`)
5. Phase 10 — Analytics and ROI, one page with CSV export (`v0.10.0`)
6. Phase 9 — Waitlist, lite: manual backfill, single offer, DB locking (`v0.9.0`)
7. Phase 11 — Integrations, lite: CSV import with dry-run; FHIR is future work (`v0.11.0`)
8. Phase 12 — Release, lite: security headers, rate limits, COMPLIANCE.md, DEPLOYMENT.md, README walkthrough, `v1.0.0`

Tags follow CLAUDE.md's `v0.<n>.0` pattern for each phase's own number, so they may not be in ascending order in history.

**Known issues:** none open.

**Docker verification runs in CI** (`.github/workflows/ci.yml`: `docker compose build`, then `up --wait`, migrations and health checks), because the dev machine has no container runtime. If Docker is installed locally later, run `make up && make migrate && make health` locally too.

---

- [x] **Phase 0 — Foundation** · 2026-10-27 · `v0.0.0`
  CLAUDE.md (mission, features, stack, safety rules, conventions), this checklist, and docs/ARCHITECTURE.md (system diagram, end-to-end data flow, DB entities).

- [x] **Phase 1 — Scaffold** · 2026-10-27 · `v0.1.0`
  pnpm + uv monorepo with a FastAPI API (`/health`, settings, JSON logs, CORS), a Celery worker and beat (demo task), a Next.js 16 + shadcn/ui web app (landing page, `/dashboard`), Alembic (pgvector migration), Docker Compose with healthchecks, Makefile, linters, pre-commit with a secret scanner, and README.
  Verified: 17 pytest + 3 Vitest passing, ruff/mypy strict/ESLint/tsc/Prettier clean, web production build OK, API `/health` OK over HTTP.
  Docker build and compose smoke test: verified in CI.

- [x] **Phase 2 — Data model + Auth/RBAC** · 2026-10-27 · `v0.2.0` · branch `phase-2-data-model-auth`
  **Plan:**
  1. Settings: PII keys (`PII_ENCRYPTION_KEYS` with key IDs for rotation, `PII_BLIND_INDEX_KEY`), JWT TTLs, magic-link and patient-session TTLs, `WEB_BASE_URL`. No default keys in code; production rejects `dev*` key IDs.
  2. Crypto: AES-256-GCM field encryption (column-bound associated data, versioned `enc:v1:<kid>:` format, rotation), HMAC blind indexes for email/phone/MRN lookup, and SQLAlchemy `EncryptedString`/`EncryptedDate` types.
  3. Models (UUIDv7 keys, tz-aware timestamps, non-native enums with CHECK constraints) for every entity in the spec, plus `RefreshToken` and `PatientMagicLink`. One Alembic migration, including a trigger that makes `audit_log` append-only.
  4. Sync SQLAlchemy sessions (shared with the Celery worker). Routers → services → repositories, with domain errors mapped to HTTP in one place. Every repository query takes `organization_id`.
  5. Staff auth: argon2 passwords, JWT access tokens + rotating refresh tokens (stored hashed, reuse detection revokes the family), `/auth/login|refresh|logout|me`, and `require_roles(...)` RBAC.
  6. Patient auth: staff create single-use magic links (hash stored, never logged). The patient redeems the token in a POST body for a short patient session; `/patient/me`.
  7. Audit: the service layer writes `AuditLog` for every patient read/write (actor, action, entity, purpose, IP, user agent, request ID). Middleware is a backstop and flags any patient route that finished without an audit entry.
  8. Admin APIs for users, facilities and procedure types; patient CRUD with blind-index search; dev seed (org, facility, admin, procedure types).
  9. Tests against real Postgres (local embedded PG16 + pgvector; PG18 service in CI): auth, refresh rotation/reuse, RBAC matrix, tenant isolation, encryption (round trip, tamper, AAD, rotation), magic links (expiry, single use), audit coverage, append-only audit log.
  All 19 entities with AES-256-GCM encrypted patient PII (key rotation, blind-index search) and an append-only audit log enforced by a DB trigger. Staff auth uses argon2, JWT and rotating refresh tokens with reuse detection, plus RBAC; patients use single-use magic links. Tenant isolation everywhere, and every patient read/write is audited, with a middleware backstop.
  Verified: 116 pytest on real Postgres (PG16 local, PG18 in CI), ruff/mypy strict clean, and CI green including Docker build, compose up, migrate, seed and an API login.
- [x] **Phase 3 — Protocol Engine** · 2026-10-27 · `v0.3.0` · branch `phase-3-protocol-engine`
  **Plan:**
  1. Safe JSON condition evaluator (`all`/`any`/`not`/`flag`/`missing`/`compare` over whitelisted patient fields, with depth and size limits, no `eval`), validated on save.
  2. Protocol service + API: create, edit, list, versions, approve. Editing an approved version creates a new DRAFT (one draft per family). Only CLINICIAN/ADMIN approve, a step is required, and SAMPLE protocols need explicit acknowledgement. Approving retires the previous version. `applicable_steps()` refuses non-approved protocols.
  3. Migration 0003: `prep_step.embedding vector(384)` + model name. DB triggers make approved/retired versions and their steps immutable, and reject timeline events that point at steps of an unapproved protocol.
  4. Embedding provider interface with an offline deterministic hashing embedder (default). Steps are embedded at approval.
  5. Seed SAMPLE drafts for colonoscopy, general surgery, CT with contrast and MRI, labelled "SAMPLE – must be reviewed by your clinical team before use". Instructions are generic and defer to the care team (no doses).
  6. Web: staff login via a Next.js backend-for-frontend (httpOnly cookies, server-only API client). `/dashboard/protocols` with list, editor and step builder (offset in hours/days), plus approve.
  7. Tests: versioning, approval rules, evaluator, triggers, tenant isolation, web unit tests for offset conversion and the builder.

  Versioned protocols, where only clinicians and admins can approve, backed by DB triggers that make approved versions immutable and keep unapproved steps out of patient timelines. There is a safe JSON condition evaluator, offline step embeddings at approval, and four SAMPLE protocols seeded as labelled drafts. The web app has staff sign-in (httpOnly cookies, refreshing proxy) and `/dashboard/protocols` with a step builder and approval.
  Verified: 178 pytest + 22 Vitest, ruff/mypy strict/ESLint/tsc/Prettier clean, Next.js build OK; local end-to-end check of sign-in, token refresh and refresh-token reuse rejection; CI green including Docker build, compose up, migrate, seed, API login and the dashboard redirect.
- [x] **Phase 4 — Smart Prep Timeline + Messaging** · 2026-10-28 · `v0.4.0` · branch `phase-4-timeline-messaging`
  **Plan:**
  1. Appointments API: create, reschedule, cancel with reason (audited). The protocol is the approved version for the procedure type (explicit choice required if several).
  2. Timeline service: on create/reschedule/cancel, generate, update in place, or cancel events from the **approved** protocol's applicable steps. Times are computed in the facility timezone (DST-safe); missed past steps are sent as catch-ups.
  3. Quiet hours 22:00–07:00 in the patient's local time (= facility timezone): non-critical reminders move earlier, to 21:30 the evening before (07:00 would always be after the step is due); critical steps keep their exact time. Day offsets keep wall-clock time across DST; hour offsets are exact durations.
  4. Messaging providers behind one interface: Console (dev default), Twilio SMS, Twilio WhatsApp, SMTP email, selected by `MESSAGING_PROVIDER`. Nothing is sent without messaging consent.
  5. Celery Beat every minute: claim due events (`FOR UPDATE SKIP LOCKED`, PENDING→SENDING), send, record the Message, and open a CheckIn for steps that need confirmation. Idempotent via the claim plus a unique outbound message per event (migration 0004).
  6. Translation: the LLM only translates approved step text (no PHI) into the patient's language. The original is stored; on any LLM failure the approved text is sent as-is.
  7. Inbound webhook (Twilio signature verified): parse YES/NO/HELP (English + Hindi), link to the patient's pending check-in, confirm the step. NO on a critical step escalates and marks the appointment AT_RISK; HELP escalates to a nurse.
  8. Tests: timeline math, timezones/DST, quiet hours, idempotent dispatch, reschedule/cancel, consent, translation fallback, inbound parsing and signatures.

  Appointments API that builds a DST-safe prep timeline from the approved protocol (quiet hours, catch-ups for late bookings, regenerated on reschedule and cancelled on cancel). A Celery Beat job claims due reminders every minute and sends each one exactly once through Console, Twilio SMS/WhatsApp or SMTP, and only with consent. Claude translates approved text only and falls back to the original on any failure. A signed Twilio webhook understands YES/NO/HELP in English and Hindi and escalates problems to staff.
  Verified: 277 pytest + 22 Vitest, ruff/mypy strict/ESLint/tsc/Prettier clean, Next.js build OK; CI green (run 40562750069) including Docker build and compose smoke test.
- [x] **Phase 5 — Patient Portal (mobile-first PWA)** · 2026-10-28 · `v0.5.0` · branch `phase-5-patient-portal`
  **Plan:**
  1. Portal read API: `GET /patient/appointments`: the patient's upcoming appointments with procedure, time, arrival, facility (address, map link, phone, timezone) and the timeline. Each step gets a state (done / due / upcoming / overdue / active / problem) computed in one pure domain function; steps needing confirmation stay due for a 4-hour grace period. Patients only ever see their own data; every read is audited as the patient.
  2. Check-in actions shared by the portal and SMS: one service applies YES / NO / HELP to an event. Portal endpoints: confirm a step, report a problem (optional note, stored encrypted), and request a reschedule (task for the coordinators). NO on a critical step opens a HIGH escalation, marks the appointment AT_RISK and creates a call task. The SMS webhook is refactored onto the same service.
  3. Calendar: `GET /patient/appointments/{id}/calendar.ics` (RFC 5545, arrival time and location, alarms a day and two hours before; no clinical details beyond the procedure name).
  4. Translations: migration 0005 adds `prep_step_translation` (step, language → translated approved text, model). Dispatch reads and writes it. A Beat job pre-translates steps of the next 14 days' appointments for non-English patients. The portal shows the cached translation, or the approved English text with a notice. The LLM is never called while a patient waits.
  5. Web portal (`/p`):
     - The magic-link token is read from the URL fragment and exchanged by a Server Action for an httpOnly patient cookie; the fragment is then removed.
     - `/p/home` shows the appointment card, a countdown timeline, the readiness checklist with Confirm and "No / I have a problem" buttons, "I need to reschedule", the `.ics` download, and an English/Hindi switch.
     - When the session expires, an expired-session page tells the patient how to get a new link.
     - Mobile-first, with large type, 48px tap targets, WCAG AA contrast, little client JS and a PWA manifest.
  6. Tests:
     - pytest: step states, actions and escalations, patient isolation, ICS, the translation cache and warm-up.
     - Vitest: i18n, formatting, components.
     - Playwright E2E (Chromium at a phone viewport, axe accessibility check): redeem link → confirm → report problem → Hindi. It runs in CI against a real API and Postgres via a fixture script.

  Patients open a single-use link and get a mobile-first portal in English or Hindi. It shows their procedure (countdown, arrival, map, call, `.ics`), a readiness checklist and a prep timeline. From there they can confirm steps, report problems (critical ones escalate and flag the appointment AT_RISK through the same service as SMS replies) and ask to reschedule. Approved step translations are cached (migration 0005) and pre-translated by a Beat job, so the portal never waits for the LLM.
  Verified: 313 pytest + 45 Vitest + 4 Playwright E2E (phone viewport, axe WCAG 2.2 AA), ruff/mypy strict/ESLint/tsc/Prettier clean, Next.js build OK; CI green (run 40625645861) including the new E2E job, Docker build and compose smoke test.
- [x] **Phase 6 — AI Prep Assistant** · 2026-10-28 · `v0.6.0` · branch `phase-6-ai-assistant`
  **Plan:**
  1. Deterministic safety layer (`domain/red_flags.py`, `domain/deidentify.py`):
     - Red-flag rules in English, Hindi and romanised Hindi: chest pain, trouble breathing, severe bleeding, fainting, severe abdominal pain, allergic reaction, stroke signs. Deliberately conservative: no negation handling, so a false positive goes to a nurse rather than a missed emergency.
     - De-identification of patient text before any LLM call: known patient names, phone numbers, emails, URLs, ID-like numbers (MRN, Aadhaar), PIN codes and dates become placeholders.
  2. LLM layer (`services/assistant/llm.py`): the only place the assistant calls Claude, with the model from `LLM_MODEL` and structured JSON outputs. Every text passes through the de-identifier here, so no caller can skip it.
     - Triage classifier: red flag yes/no, plus whether the question is about this patient's prep.
     - Grounded answer: answer text plus cited step ids, and a flag saying whether the steps cover the question.
     - Versioned prompt files (`prompts/assistant_triage_v1.md`, `prompts/assistant_answer_v1.md`); the version is stored with every exchange.
  3. Assistant pipeline (`services/assistant/service.py`, migration 0006 `assistant_exchange`):
     - Order: rules → LLM triage → retrieval over only this patient's applicable steps (pgvector over the appointment's active timeline steps) → grounded answer → output checks.
     - Output checks: citations must be a subset of the steps provided, and every number in the answer must appear in the cited steps.
     - Red flags (from the rules or the LLM) give a fixed, human-written emergency message plus an URGENT escalation and call task. Out-of-protocol questions, failed checks, refusals and an unavailable LLM give a fixed "passed to your care team" message plus an escalation and a nurse task. Escalation never depends on the LLM.
     - The question and answer are stored encrypted; everything is audited.
  4. API: `POST /patient/assistant/questions` and `GET /patient/assistant/questions` (the patient's own history). Nurse inbox: `GET /escalations` (open first, by severity), `POST /escalations/{id}/acknowledge`, `POST /escalations/{id}/resolve` (with a note), all needing `escalation:handle`.
  5. Web:
     - Portal: an "Ask about your prep" panel showing the answer with cited steps (links into the timeline), or the escalation message, plus history. English and Hindi.
     - Dashboard: `/dashboard/inbox` (nurse inbox) with severity, patient, the question, and acknowledge/resolve actions.
  6. Evaluation: `make eval` runs 30+ cases from `apps/api/evals/assistant_cases.toml` (red flags in three languages, in-protocol questions with the expected cited step, out-of-protocol questions, prompt injection, PHI in the question).
     - The rules layer always runs. The full pipeline runs against the real model when `ANTHROPIC_API_KEY` is set.
     - The report shows a pass rate per category, and the run exits non-zero on any missed red flag.
  7. Tests: rules, de-identification (the LLM client receives only redacted text), each pipeline outcome with a fake LLM (red flag, out of protocol, unavailable, ungrounded number, bad citation, refusal), patient isolation, the inbox API and permissions, Vitest for the panels, and Playwright for asking a question and seeing an escalation in the inbox.
  Red flags (chest pain, breathing, severe bleeding, fainting, severe abdominal pain, allergy, stroke signs) are caught by rules in English, Hindi and romanised Hindi before any LLM call. The LLM classifies triage and answers only from the patient's own approved steps, citing them. Output checks reject citations to steps that were not provided and numbers that do not appear in the cited steps. Anything else goes to the nurse inbox at `/dashboard/inbox` with a fixed reply, and emergencies get an urgent escalation and an AT_RISK appointment.
  Verified: 406 pytest + 53 Vitest + 5 Playwright (phone viewport, including the red-flag question reaching the inbox), ruff, mypy strict, ESLint, tsc and Prettier clean. `make eval` (41 cases): 17/17 red flags caught, 0 false alarms on 10 ordinary questions. The LLM cases were skipped because no API key is set on this machine.
  **Known issues:**
  - The 8 LLM eval cases and the live LLM answer path have not been run against the real model (no `ANTHROPIC_API_KEY` on the dev machine). Their logic is covered by tests with a fake client only.
  - `make` is not installed on the Windows dev machine, so the eval was run with `uv run python apps/api/evals/run_assistant_eval.py`. The Makefile target works where `make` exists.
  - Assistant requests are not rate-limited yet (the portal already handles HTTP 429). The limiter comes in Phase 6b.

- [x] **Phase 6b — Guest login and demo mode** · 2026-10-28 · `v0.6.1` · branch `phase-6b-guest-demo`
  A guest signs in with "Try as Guest" (`ENABLE_GUEST_LOGIN`, on by default) and gets a 2-hour `DEMO_VIEWER` session in the synthetic "Demo Hospital (guest)". The role can view everything in the demo and complete tasks, confirm steps and resolve escalations, but cannot approve protocols, manage users, reset the demo or reach other organisations. Demo reminders go to the console only. `make seed-demo` builds the hospital (2 facilities, 4 approved SAMPLE protocols, 25 synthetic patients, bookings over 7 days, reminders, answers and escalations). The demo resets nightly from the worker and from the demo admin's button. "View patient demo" opens a fresh single-use link in English or Hindi. Guest sign-in and assistant questions are rate-limited.
  Verified: 427 pytest (13 new guest tests, plus worker tests), 56 Vitest, 6 Playwright (guest sign-in, banner, inbox, demo patient), ruff, mypy, ESLint, tsc and Prettier clean. CI result is recorded at merge.
  **Known issues:**
  - On Windows, a Playwright-started `next start` failed the portal's server actions in two runs right after a fresh `next build`. The same six tests pass when the server is started separately, or when there is no build immediately before the run. Cause not found. CI runs build and then E2E, so watch the E2E job; if it fails the same way, start the server before Playwright.
  - Rate limits live in process memory. Repeated local E2E runs can hit the guest sign-in limit (5 per 10 minutes per address); restart the API to clear it.
  - The nightly reset runs in the worker, so it needs a running worker and beat. Locally they are not started by default.
  - A staff member's "View patient demo" link is issued as the demo guest, so the audit trail names the demo account, not the staff member.

- [x] **Phase 8 — Coordinator Dashboard** · 2026-10-28 · `v0.8.0` · branch `phase-8-coordinator-dashboard`
  The dashboard lists the next 72 hours, with a "Needs attention" filter. Each row shows readiness (the share of steps that need confirming that are done), open escalations and open tasks. Escalated patients come first, then the least ready. A patient drawer shows the prep steps, escalations, recent messages and tasks, with actions: mark a step done for the patient, log a task done, resend failed reminders, reschedule (India time), and release the slot with a reason. The task queue at `/dashboard/tasks` shows each task's SLA in words (overdue, due within an hour, on time). Every patient read is audited.
  Verified: 436 pytest (9 new dashboard tests), 63 Vitest, Playwright on the desktop project for the coordinator flow, ruff, mypy, ESLint, tsc and Prettier clean. CI result is recorded at merge.
  **Known issues and scope notes:**
  - Scope: real-time updates (server-sent events) and a generated OpenAPI client are not built. The web types are written by hand in `packages/shared`. Both are future work.
  - Readiness stands in for the risk score until Phase 7 lands.
  - Times are shown in Asia/Kolkata, and the reschedule form takes India time. Facilities in other timezones need their own offset (future work).
  - Staff screens are tested on the desktop project only. The table scrolls sideways on phones, but that layout is not tested yet.

- [x] **Phase 7 — Cancellation Risk Score (rules v1)** · 2026-10-28 · `v0.7.0` · branch `phase-7-risk-score`
  Transparent rules with written weights, each with a plain-words reason: steps not yet confirmed, escort or logistics outstanding, problem replies, open and urgent escalations, anticoagulant, insulin, GLP-1, contrast allergy and metal implant (for the matching scan), low eGFR for contrast, and the last 24 hours with steps outstanding. Levels: HIGH from 50, MEDIUM from 25. The worker refreshes scores every 15 minutes, stores each one with its reasons and model version, and opens one "High cancellation risk" coordinator task per HIGH procedure (never a second while one is open). The dashboard sorts escalations first, then by risk, and shows the reasons. `docs/model_report.md` lists the weights and their limits.
  Verified: 445 pytest (new risk rules, refresh and dashboard tests), 63 Vitest, 7 Playwright (desktop project for staff screens), ruff, mypy, ESLint, tsc and Prettier clean. CI result is recorded at merge.
  **Known issues and scope notes:**
  - The learned model (calibrated logistic regression) is future work. The weights are judgement calls, not fitted to data, and are not calibrated (see `docs/model_report.md`).
  - The dashboard works out each row's score on request, which costs about eight queries per procedure. Fine for the demo; cache it when the list grows.
  - Scores are stored every 15 minutes per procedure with no retention policy yet (Phase 12).
  - Scores need the worker and beat running. Locally they are not started by default.
- [x] **Phase 10 — Analytics & ROI (lite)** · 2026-10-28 · `v0.10.0` · branch `phase-10-analytics`
  One analytics page for a date range: cancellation rate, prep-related cancellations (the six reasons a patient could have prevented), check-in response rate, theatre minutes and OR cost at risk, and an optional estimate of avoided cancellations against a cancellation rate the hospital enters from before Prefix AI. A CSV export lists each procedure by id, time, status and reason, with no names; only coordinators and admins may download it, and each download is audited. Slots backfilled is shown as not tracked until the waitlist exists.
  Verified: 452 pytest (7 new analytics tests), 68 Vitest, 8 Playwright (desktop project for staff screens), ruff, mypy, ESLint, tsc and Prettier clean. CI result is recorded at merge.
  **Known issues and scope notes:**
  - Charts (Recharts), the nightly aggregation job, and a printed PDF are not built. The page prints through the browser.
  - "OR cost" uses the seeded per-minute OR cost, not billed revenue. The page calls the at-risk figure exposure, not savings, and only estimates savings when a baseline is given.
  - Dates are UTC. Facility timezones are not applied to range boundaries.
- [x] **Phase 9 — Waitlist Backfill (lite)** · 2026-10-28 · `v0.9.0` · branch `phase-9-waitlist`
  Coordinators see each released slot (cancelled, still ahead, within seven days) and offer it to one waitlisted patient at a time, the best fit first. A patient fits when they wait for the same procedure, the slot's local date is inside their window, they have enough notice for the prep (the protocol's longest offset), and they have not declined the slot or already booked that procedure. Accepting books the patient into the slot. Viewers can read the page but cannot act.
  The slot is locked before any offer or booking, and the database allows one OPEN and one ACCEPTED offer per slot, so two staff members cannot double-book. Each night the demo hospital gets a released slot with three patients waiting for it.
  Verified: 460 pytest (14 new waitlist tests and one demo test), 73 Vitest (5 new), 9 Playwright (1 new, desktop), ruff, mypy, ESLint, tsc and Prettier clean. CI result is recorded at merge.
  **Known issues and scope notes:**
  - Offers never expire. An OPEN offer stays until someone accepts or declines it, so a silent patient holds the slot. Timed expiry belongs with notifications (Phase 12 or later).
  - No message goes to the patient about an offer; the coordinator phones them. Released slots appear only within seven days.
  - The prep check uses the protocol's longest offset and ignores step conditions. That is conservative: it can skip a patient who would have been fine.
  - Analytics still shows backfilled slots as "not tracked", although the waitlist now exists.
  - Fixed in this phase: the analytics page logged a Next.js "unstable Date.now()" error during prerender. It now renders per request.
- [x] **Phase 11 — Integrations (lite)** · 2026-10-28 · `v0.11.0` · branch `phase-11-integrations`
  CSV import of patients and appointments. A coordinator picks a file, sees every row problem by line and column, and imports only when every row is valid. Each row goes through the same services as a typed entry, so consent, audit, protocol and timeline rules apply. Error messages never repeat cell values. Columns can be mapped, unknown ones are reported, and files are capped at 1 MB and 500 rows. The formats and safety properties are in `docs/INTEGRATIONS.md`.
  Verified: 472 pytest (12 new import tests), 84 Vitest (11 new), 10 Playwright (1 new, desktop), ruff, mypy, ESLint, tsc and Prettier clean. CI result is recorded at merge.
  **Known issues and scope notes:**
  - FHIR R4 is not built. It is planned after v1.0.0, and `docs/INTEGRATIONS.md` says what it will cover.
  - Import only creates records. There is no update or merge: a repeated MRN is refused, and existing patients are edited in the app.
  - Consent from a file is recorded with the import time as its timestamp, and the source of the consent is not stored. Check it before importing; Phase 12's COMPLIANCE.md repeats this.
  - Each file is processed synchronously in one request, so the 500-row cap stays. A larger hospital would need a background job.
  - Found and fixed while testing: browsers send form text with CRLF line endings, so the import button never appeared. Both sides now normalise line endings.
- [ ] Phase 12 — Hardening + Release (lite) · branch `phase-12-release`
