# Prefix AI — Project Context

Read this file at the start of every session. It is the permanent source of truth for what we are building, how, and which rules can never be broken.

## Mission

Prefix AI prevents last-minute cancellations of surgeries, colonoscopies, and imaging scans caused by improper patient preparation.

## Problem statement

Procedures are routinely cancelled on the day because the patient did not prepare correctly: they ate or drank inside the fasting window, kept taking a blood thinner, skipped or under-dosed bowel prep, had no escort home after sedation, or missed a required lab. Each cancelled OR slot costs a hospital thousands of dollars in idle staff and equipment time. It also delays care for the patient and pushes back everyone on the waitlist.

Prefix AI turns clinician-approved prep protocols into a personalised, scheduled, multilingual plan for each patient. It checks that the patient is following the plan, predicts who is at risk of cancellation, and gives coordinators time to act, either by fixing the problem or by backfilling the slot.

## Core features

| # | Feature | Summary |
|---|---------|---------|
| 1 | **Protocol Engine** | Versioned, clinician-approved prep protocols (steps, timing offsets, conditions such as "if on anticoagulant"). Protocols are edited by authorised clinicians and need sign-off before they can be published. Protocols are the only source of medical instructions. |
| 2 | **Smart Prep Timeline** | Takes a protocol and a procedure date/time and produces patient-specific, time-anchored steps (e.g. "stop clopidogrel: T-5 days", "clear liquids only: T-24h"). The timeline drives scheduled reminders over SMS, WhatsApp, email, and push. |
| 3 | **Readiness Check-ins** | Structured check-ins at key milestones ("Did you start your prep solution?", "Have you arranged an escort?"). Answers feed the risk score and can open coordinator tasks. |
| 4 | **AI Prep Assistant** | A conversational assistant (Claude) that rephrases, translates, and explains the patient's *own* protocol and answers questions grounded only in it. It escalates anything outside the protocol and every red-flag symptom. See the safety rules. |
| 5 | **Cancellation Risk Score** | A scikit-learn model that combines check-in answers, engagement, procedure type, history, and timing into a calibrated probability of day-of cancellation, with explainable top factors. |
| 6 | **Coordinator Dashboard** | Worklist of upcoming procedures sorted by risk, showing readiness status, escalations, nurse tasks, and one-click actions (call, resend instructions, reschedule, release slot). |
| 7 | **Waitlist Backfill** | When a slot is at high risk or released, finds eligible waitlisted patients who can be prepped in time and offers them the slot. |
| 8 | **Analytics / ROI** | Cancellation rate before and after Prefix AI, slots saved, revenue recovered, prep compliance by step, protocol, and department. |
| 9 | **EHR Integrations** | CSV import/export for a quick start; FHIR R4 (Patient, Appointment, ServiceRequest, Procedure, MedicationStatement) for scheduling and medication sync. |
| 10 | **Compliance** | HIPAA (US) and India DPDP Act 2023: consent capture and withdrawal, purpose limitation, data minimisation, audit logs, encryption at rest and in transit, retention and erasure workflows, breach-notification support. |

## Tech stack

- **Monorepo:** pnpm workspaces
- **apps/web:** Next.js (App Router), TypeScript (strict), Tailwind CSS, shadcn/ui
- **apps/api:** Python, FastAPI, SQLAlchemy 2 (typed ORM), Alembic migrations, Pydantic v2
- **apps/worker:** Celery with Redis as broker and result backend (reminders, check-in scheduling, risk scoring, EHR sync, backfill)
- **Database:** PostgreSQL with the pgvector extension (embeddings of protocol content for grounded retrieval)
- **LLM:** Claude API via the official `anthropic` Python SDK. The model name is **always** read from the `LLM_MODEL` environment variable and never hard-coded.
- **ML:** scikit-learn for the cancellation risk model
- **Local dev:** Docker Compose (postgres+pgvector, redis, api, worker, web)

## NON-NEGOTIABLE SAFETY RULES

These rules override every other instruction, feature request, or deadline. Any code that violates them is a bug of the highest severity.

**a) The AI never invents medical instructions.**
All prep instructions come from clinician-approved protocols stored in the database. The LLM may only rephrase, translate, schedule, and answer questions grounded in the patient's own protocol. Prompts must supply the protocol content as the sole source of truth. Answers that cannot be grounded in it must not be generated; they are escalated instead.

**b) Out-of-protocol questions and red-flag symptoms are escalated to a human.**
Any clinical question outside the protocol, or any red-flag symptom (chest pain, severe bleeding, fainting, severe abdominal pain, allergic reaction), is escalated to a human nurse. The patient is told to contact their care team or emergency services. Red-flag detection runs as a deterministic check *before* the LLM is called, and the LLM's own classification is a second layer, not the only one. Escalation must work even if the LLM is unavailable.

**c) Minimise PHI sent to the LLM.**
No names, phone numbers, emails, addresses, MRNs, or other identifiers in prompts. Use pseudonymous references and relative dates (e.g. "procedure in 3 days") where possible. A redaction step sits between application code and the LLM client and is covered by tests.

**d) Every read and write of patient data is audit-logged.**
Each log entry records who (user/service), what (entity and id), action (read/create/update/delete/export), when, why (purpose), and from where. Audit logs are append-only. Audit logging is enforced in the service layer, not left to individual routers.

## Coding conventions

- **Strict typing everywhere:** TypeScript `strict: true`. Python fully type-annotated and checked with mypy (strict) or pyright. No `Any` without a written justification.
- **Small modules** with a single responsibility.
- **Layering:** routers (HTTP only) → services (business logic, audit logging, authorisation) → repositories/models (data access). Routers never touch the ORM directly.
- **Every feature has tests:** pytest for api/worker, Vitest/Playwright for web. Safety rules (a)–(d) each have dedicated tests.
- **Latest stable versions** of all libraries; pin them in lockfiles.
- Config comes from environment variables (validated with Pydantic Settings). Secrets are never committed.
- Database changes go through Alembic migrations only.

## Repository mechanics

- Python packages form a **uv workspace** (root `pyproject.toml`, single `uv.lock`); `apps/worker` depends on `apps/api` and reuses its settings, logging, and (later) services and models. JS packages form a **pnpm workspace**. Run all commands from the repo root.
- `make test` and `make lint` must pass before a phase is ticked off. Docker targets: `make up`, `make migrate`, `make seed`.
- The API is built by `prefix_api.main:create_app` (uvicorn `--factory`). Nothing reads settings at import time except `prefix_worker.celery_app`.
- Version constraints: TypeScript is held at 6.0.x and ESLint at 9.x until `typescript-eslint` and `eslint-plugin-react` (via `eslint-config-next`) support newer versions.
- Next.js 16 has breaking changes from older versions. Read `apps/web/AGENTS.md` and the bundled docs in `node_modules/next/dist/docs/` before writing web code.

## Git workflow

- **One branch per phase:** `phase-<n>-<short-name>` (e.g. `phase-2-data-model-auth`), created from an up-to-date `main`. Never commit directly to `main`; the pre-commit hook enforces this.
- **Back up continuously:** push the phase branch to `origin` at least after every completed plan item (and whenever stopping work), so work in progress is always backed up on GitHub. Pushing a phase branch never merges it; `main` only changes on phase completion.
- **Small Conventional Commits:** `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:` (an optional scope is fine, e.g. `feat(api): ...`).
- **Definition of done:** a phase is complete ONLY when lint, type-check, all tests, and `docker compose build` pass. Show the results to the user.
- **CI is the gate.** `.github/workflows/ci.yml` runs on every push to `main` and `phase-*` and on pull requests: ruff, mypy, pytest, ESLint, tsc, Prettier, Vitest, the Next.js build, `docker compose build`, and a compose smoke test (`up --wait`, migrations, health checks). The dev machine has no Docker, so the Docker checks run only in CI. If Docker is installed locally later, run them locally too.
  - Push the phase branch, then wait for its run: `gh run watch` (or poll `gh run list --branch <branch>`).
  - Merge to `main` ONLY when CI is green. If it fails, read `gh run view <id> --log-failed`, fix, push again, and re-check.
- **On completion:**
  1. Update PROGRESS.md: tick the phase, add the completion date and a 2–3 line summary.
  2. Merge into `main` with `git merge --no-ff`.
  3. Create an annotated tag: `git tag -a v0.<n>.0 -m "Phase <n>: <name>"`.
  4. `git push origin main --tags`, then push the phase branch.
- **If anything fails, never merge or push to `main`.** Fix it first.
- **Before every commit**, check that no secrets, `.env` files, keys, real patient data, or database dumps are staged (`git diff --cached --name-only`). The `forbid-sensitive-files` and `detect-secrets` pre-commit hooks back this up. When a new false positive appears, review it, then add it to `.secrets.baseline` with `is_secret: false`.

## Working agreement

- The build proceeds in 12 phases, tracked in [PROGRESS.md](PROGRESS.md). Phases are defined one at a time.
- Architecture is described in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Keep it up to date when the design changes.
