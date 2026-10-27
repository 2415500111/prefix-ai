# Prefix AI — Build Progress

Each phase gets a short plan before work starts. Tick a phase only when lint, type-check, all tests, and `docker compose build` pass, then record the date and a 2–3 line summary (see "Git workflow" in CLAUDE.md).

## Resume point

**Status:** Phase 1 committed locally on `phase-1-scaffold`. Waiting on the user for (1) the GitHub `origin` URL and (2) a way to run `docker compose build` (local Docker, or CI).
**Next:** merge `phase-1-scaffold` → `main`, tag `v0.1.0`, push, then start Phase 2 (Data model + Auth/RBAC).

---

- [x] **Phase 0 — Foundation** · 2026-10-27 · `v0.0.0`
  CLAUDE.md (mission, features, stack, safety rules, conventions), this checklist, and docs/ARCHITECTURE.md (system diagram, end-to-end data flow, DB entities).

- [x] **Phase 1 — Scaffold** · 2026-10-27 · `v0.1.0`
  pnpm + uv monorepo with a FastAPI API (`/health`, settings, JSON logs, CORS), a Celery worker and beat (demo task), a Next.js 16 + shadcn/ui web app (landing page, `/dashboard`), Alembic (pgvector migration), Docker Compose with healthchecks, Makefile, linters, pre-commit with a secret scanner, and README.
  Verified: 17 pytest + 3 Vitest passing, ruff/mypy strict/ESLint/tsc/Prettier clean, web production build OK, API `/health` OK over HTTP.
  **Open:** `docker compose up`/`build` not yet run (no container runtime on the dev machine).

- [ ] Phase 2 — Data model + Auth/RBAC
- [ ] Phase 3 — Protocol Engine
- [ ] Phase 4 — Smart Prep Timeline + Messaging
- [ ] Phase 5 — Patient Portal (mobile-first PWA)
- [ ] Phase 6 — AI Prep Assistant
- [ ] Phase 7 — Cancellation Risk Score
- [ ] Phase 8 — Coordinator Dashboard
- [ ] Phase 9 — Waitlist Backfill
- [ ] Phase 10 — Analytics & ROI
- [ ] Phase 11 — Integrations
- [ ] Phase 12 — Hardening + Release
