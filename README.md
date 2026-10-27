# Prefix AI

Prefix AI prevents last-minute cancellations of surgeries, colonoscopies, and imaging scans caused by improper patient preparation. See [CLAUDE.md](CLAUDE.md) for the mission, features, and safety rules, and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the system design.

## Repository layout

```
apps/
  api/        FastAPI service (Python, SQLAlchemy 2, Alembic, Pydantic v2)
  worker/     Celery worker + beat (Python, Redis broker); reuses prefix_api code
  web/        Next.js App Router frontend (TypeScript, Tailwind CSS, shadcn/ui)
packages/
  shared/     TypeScript types shared with the web app (to be generated from the API's OpenAPI schema)
docs/         Architecture notes
```

Two package managers share the repo:

- **pnpm workspace** (`pnpm-workspace.yaml`) for the JavaScript packages: `apps/web` and `packages/*`.
- **uv workspace** (root `pyproject.toml`) for the Python packages: `apps/api` and `apps/worker`, with one lockfile (`uv.lock`).

Run every command from the repository root.

## Prerequisites

| Tool | Version | Used for |
|---|---|---|
| [Docker Desktop](https://docs.docker.com/get-docker/) (Compose v2) | latest | Running the full stack |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | 0.13+ | Python 3.14 and Python dependencies |
| [Node.js](https://nodejs.org/) | 24 LTS | Web app |
| pnpm | 12 (pinned in `package.json`) | Enable with `corepack enable` |
| make | any | Shortcuts below (on Windows, run them from Git Bash or WSL) |

## Quick start (Docker)

```bash
cp .env.example .env    # then review it; `make up` does this for you if .env is missing
make up                 # builds images and starts postgres, redis, api, worker, celery-beat, web
make migrate            # applies database migrations (enables pgvector)
make health             # checks both health endpoints
```

| Service | URL |
|---|---|
| API health | http://localhost:8000/health |
| API docs (non-production only) | http://localhost:8000/docs |
| Web app | http://localhost:3000 |
| Coordinator dashboard | http://localhost:3000/dashboard |
| Postgres | `localhost:5432` (user, password, and database from `.env`) |
| Redis | `localhost:6379` |

`make up` waits until every container's healthcheck passes. `make ps` shows their status, and `make logs` follows the logs. The API, worker, and web containers mount the source code, so edits reload automatically.

## Run without Docker (e.g. Windows without WSL2)

Needs Python 3.12+ (for `pip`), Node.js 24 and git. Run these from the repo root in PowerShell.

```powershell
py -m pip install uv                       # once: Python package/project manager
Copy-Item .env.example .env                # once (skip if .env exists)

# Local PostgreSQL + pgvector (no Docker). Data in .devdb/; writes DATABASE_URL into .env.
# Re-run after a reboot (the port can change).
uv run --no-project --python 3.12 --with pgserver python scripts/dev_postgres.py

uv sync                                     # Python dependencies
uv run alembic -c apps/api/alembic.ini upgrade head
$env:SEED_ADMIN_PASSWORD = "Demo-Prefix-2026!"   # pick any password
uv run python -m prefix_api.seed           # demo org, admin, SAMPLE protocols

# Terminal 1: API on http://localhost:8000
uv run uvicorn prefix_api.main:create_app --factory --reload --port 8000

# Terminal 2: web app on http://localhost:3000
corepack pnpm install
corepack pnpm dev
```

Open http://localhost:3000/login and sign in as `admin@demo-hospital.example.com` with the password you chose. Then open **Protocols**. The seed only sets the password when it first creates the admin.

## Native development (without Docker for the apps)

```bash
make setup                  # uv sync, pnpm install, and git pre-commit hooks
docker compose up -d postgres redis

uv run uvicorn prefix_api.main:create_app --factory --reload --port 8000
uv run celery --app prefix_worker.celery_app worker --loglevel INFO --pool solo   # --pool solo on Windows
uv run celery --app prefix_worker.celery_app beat --loglevel INFO
pnpm dev                    # web app on http://localhost:3000
```

The Python apps read `.env` from the current directory. That is why commands run from the repository root.

## Make targets

| Command | What it does |
|---|---|
| `make up` / `make down` | Start / stop the Docker stack (`make clean` also deletes data volumes) |
| `make migrate` | Apply Alembic migrations inside the API container |
| `make migration m="..."` | Autogenerate a new migration (needs the stack up) |
| `make seed` | Load development seed data (refuses to run when `APP_ENV=production`) |
| `make test` | pytest for api + worker, Vitest for web |
| `make lint` | ruff, ruff format check, mypy (strict), ESLint, TypeScript, Prettier check |
| `make format` | Auto-fix with ruff and Prettier |
| `make help` | List every target |

## Logging in (development)

`make seed` creates **Demo Hospital** with one facility, four procedure types, and an admin `admin@demo-hospital.example.com`. The admin's password is printed once; set `SEED_ADMIN_PASSWORD` to choose it. Then:

```bash
curl -X POST localhost:8000/auth/login -H 'Content-Type: application/json'   -d '{"email":"admin@demo-hospital.example.com","password":"<printed password>"}'
```

Or sign in at http://localhost:3000/login and open **Protocols**. `make seed` adds four **SAMPLE** protocols (colonoscopy, general surgery, CT with contrast, MRI) as drafts. They are examples only and must be reviewed and adapted by your clinical team before anyone approves them; the approve screen asks for that confirmation.

The full API is browsable at http://localhost:8000/docs. The security model (roles, patient magic links, audit logging, PII encryption) is described in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#4-security-model).

## Tests

Python tests run against a real PostgreSQL with pgvector. Start one with `docker compose up -d postgres`; the `prefix_test` database is created and migrated automatically. To use another server, set `TEST_DATABASE_URL`. CI runs the same tests against Postgres 18.

## Reminders and messaging

Booking an appointment (`POST /appointments`) builds the patient's prep timeline from the approved protocol. The `celery-beat` service runs the reminder dispatcher every minute. With `MESSAGING_PROVIDER=console` (the default), reminders are only logged, with the recipient masked. Set `MESSAGING_PROVIDER=live` plus the Twilio and SMTP values in `.env` to really send. Point your Twilio number's incoming-message webhook to `<PUBLIC_API_BASE_URL>/webhooks/twilio`. Patients must have messaging consent recorded before anything is sent.

Without Docker, run the worker and scheduler in two more terminals:

```powershell
uv run celery --app prefix_worker.celery_app worker --loglevel INFO --pool solo
uv run celery --app prefix_worker.celery_app beat --loglevel INFO
```

These need Redis at `REDIS_URL`.

## Configuration

All settings come from environment variables. Each one is documented in [.env.example](.env.example). The API validates them on startup with pydantic-settings and refuses to start if a required value is missing or invalid. For example, `LLM_MODEL` must be set, `JWT_SECRET` must be at least 32 characters, and the placeholder secret is rejected in production.

## Code quality

- **Python:** ruff (lint + format) and mypy in strict mode, configured in the root `pyproject.toml`.
- **TypeScript:** ESLint (Next.js config + Prettier) and Prettier with the Tailwind plugin.
- **Pre-commit:** `.pre-commit-config.yaml` runs the same tools from the project's lockfiles. It also blocks private keys and direct commits to `main`.

## Troubleshooting

- **`WSL 2 is not supported with your current machine configuration` (Windows):** Docker Desktop needs virtualization. Enable *Virtual Machine Platform* (`wsl --install --no-distribution` in an admin terminal), turn on virtualization (VT-x/AMD-V) in the BIOS if it is off, then reboot.
- **Hot reload doesn't pick up changes on Windows:** file-change events don't always cross from the Windows filesystem into containers. Clone the repo inside WSL for the best experience.
- **`make: command not found` on Windows:** install it with `winget install GnuWin32.Make` or `choco install make`, or run the commands from the Makefile directly.
