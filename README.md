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
