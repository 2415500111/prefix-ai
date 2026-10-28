# Prefix AI — Build Progress

Each phase gets a short plan before work starts. Tick a phase only when lint, type-check, all tests, and `docker compose build` pass, then record the date and a 2–3 line summary (see "Git workflow" in CLAUDE.md).

## Resume point

**Status:** Phases 0–5 merged (latest tag `v0.5.0`).
**Next:** Phase 6 (AI Prep Assistant) on `phase-6-ai-assistant`; write its plan below first.

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
- [ ] Phase 6 — AI Prep Assistant
- [ ] Phase 7 — Cancellation Risk Score
- [ ] Phase 8 — Coordinator Dashboard
- [ ] Phase 9 — Waitlist Backfill
- [ ] Phase 10 — Analytics & ROI
- [ ] Phase 11 — Integrations
- [ ] Phase 12 — Hardening + Release
