# Prefix AI — Build Progress

Each phase gets a short plan before work starts. Tick a phase only when lint, type-check, all tests, and `docker compose build` pass, then record the date and a 2–3 line summary (see "Git workflow" in CLAUDE.md).

## Resume point

**Status:** Phases 0–2 merged and pushed to https://github.com/2415500111/prefix-ai. Phase 3 in progress on `phase-3-protocol-engine` (pushed, not merged).
**Phase 3 done so far:** plan items 1 (condition evaluator), 2 (protocol service/API, 28 tests incl. DB trigger guards), 3 (migration 0003), 4 (embedding provider), 5 (SAMPLE protocols seeded as labelled drafts) and 6 (web sign-in + `/dashboard/protocols` list, step builder, approval; verified end to end against a local API).
**Next:** finish item 7 (docs, full checks), push, wait for green CI, then merge Phase 3.

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
- [ ] Phase 3 — Protocol Engine · branch `phase-3-protocol-engine`
  **Plan:**
  1. Safe JSON condition evaluator (`all`/`any`/`not`/`flag`/`missing`/`compare` over whitelisted patient fields, with depth and size limits, no `eval`), validated on save.
  2. Protocol service + API: create, edit, list, versions, approve. Editing an approved version creates a new DRAFT (one draft per family). Only CLINICIAN/ADMIN approve, a step is required, and SAMPLE protocols need explicit acknowledgement. Approving retires the previous version. `applicable_steps()` refuses non-approved protocols.
  3. Migration 0003: `prep_step.embedding vector(384)` + model name. DB triggers make approved/retired versions and their steps immutable, and reject timeline events that point at steps of an unapproved protocol.
  4. Embedding provider interface with an offline deterministic hashing embedder (default). Steps are embedded at approval.
  5. Seed SAMPLE drafts for colonoscopy, general surgery, CT with contrast and MRI, labelled "SAMPLE – must be reviewed by your clinical team before use". Instructions are generic and defer to the care team (no doses).
  6. Web: staff login via a Next.js backend-for-frontend (httpOnly cookies, server-only API client). `/dashboard/protocols` with list, editor and step builder (offset in hours/days), plus approve.
  7. Tests: versioning, approval rules, evaluator, triggers, tenant isolation, web unit tests for offset conversion and the builder.
- [ ] Phase 4 — Smart Prep Timeline + Messaging
- [ ] Phase 5 — Patient Portal (mobile-first PWA)
- [ ] Phase 6 — AI Prep Assistant
- [ ] Phase 7 — Cancellation Risk Score
- [ ] Phase 8 — Coordinator Dashboard
- [ ] Phase 9 — Waitlist Backfill
- [ ] Phase 10 — Analytics & ROI
- [ ] Phase 11 — Integrations
- [ ] Phase 12 — Hardening + Release
