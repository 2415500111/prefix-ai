# Local development

This guide gets the whole app running on your own machine without Docker, and explains the few things that go wrong on Windows. The Docker route is in the README; use it if you have Docker Desktop.

## One-time setup

You need Node.js 24 LTS, [uv](https://docs.astral.sh/uv/getting-started/installation/) (it installs Python 3.14 for you) and git. Run the commands from the repository root.

**1. Enable pnpm (pinned to 12 in `package.json`).**

Corepack ships with Node. It creates the `pnpm` command, and it reads the version from `package.json`.

- macOS and Linux: `corepack enable` (use `sudo` if Node is installed system-wide).
- Windows without admin rights: `corepack enable --install-directory "$env:APPDATA\npm"`. Plain `corepack enable` fails with `EPERM` there, because it writes into `C:\Program Files\nodejs`. The npm folder is already on PATH for a standard Node install.

Check it with `pnpm --version`. It should print `12.15.0` or later in the 12 line.

**2. Install the dependencies.**

```bash
uv sync                    # Python packages (API, worker, tools), locked in uv.lock
pnpm install               # JavaScript packages (web app and shared types)
```

`make setup` does both and also installs the git pre-commit hooks (`uv run pre-commit install`).

**3. Create your settings file.**

```bash
cp .env.example .env       # Windows PowerShell: Copy-Item .env.example .env
```

The defaults are right for local development: messages are only logged, and the keys are for development only. Production refuses development keys; see [DEPLOYMENT.md](DEPLOYMENT.md).

**4. Start a local PostgreSQL with pgvector.**

```bash
uv run --no-project --python 3.12 --with pgserver python scripts/dev_postgres.py
```

This starts PostgreSQL on port 55432, keeps its data in `.devdb/`, and writes the database URL into `.env`. The script may print a timeout error from `pg_ctl` even when the server starts; wait about 30 seconds, then check it with `uv run python -c "import psycopg; psycopg.connect('host=127.0.0.1 port=55432 user=postgres dbname=prefix_dev').close()"`. Run the script again after a reboot, since the port and data directory are reused.

**5. Create the tables and the demo hospital.**

```bash
uv run alembic -c apps/api/alembic.ini upgrade head
uv run python -m prefix_api.seed_demo
```

The seed creates the **Demo Hospital (guest)** with 25 made-up patients, bookings over the next week, one cancelled slot with waiting patients, and the demo admin. The first run prints the admin's password once. Save it to sign in as the admin.

## Run the app

Two terminals, both from the repository root.

```bash
# Terminal 1: the API on http://localhost:8000
uv run uvicorn prefix_api.main:create_app --factory --reload --port 8000

# Terminal 2: the web app on http://localhost:3000
pnpm dev
```

Optional, for reminders: a third terminal with `uv run celery --app prefix_worker.celery_app worker --loglevel INFO --pool solo`, and a fourth with `... beat --loglevel INFO`. They need Redis at `REDIS_URL`. The demo runs without them, but reminders are only sent by the worker.

## Sign in

- **Guest (no password):** open http://localhost:3000/login and press **Try as Guest**. A guest can read everything and tick things off, but cannot approve protocols, manage users, import or reset the demo.
- **Demo admin:** `admin@guest-demo-hospital.demo.example.com`, with the password `seed_demo` printed the first time it ran.
- **Your own hospital:** there is no onboarding command yet. See [DEPLOYMENT.md](DEPLOYMENT.md#first-admin).

API documentation is at http://localhost:8000/docs when `APP_ENV` is not `production`.

## Tests and checks

| Command | What it runs |
|---|---|
| `uv run pytest apps/api/tests apps/worker/tests` | Python tests, against the `prefix_test` database |
| `pnpm --filter @prefix/web test` | Vitest unit tests for the web app |
| `pnpm --filter @prefix/web build` then `pnpm --filter @prefix/web exec playwright test` | End-to-end tests against the real API and database. The build is needed because the tests use `next start`. |
| `make lint` | ruff, mypy, ESLint, TypeScript and Prettier (run it from Git Bash or WSL on Windows) |

The Python tests need PostgreSQL. Point `TEST_DATABASE_URL` at a server you can use, for example `postgresql+psycopg://postgres:@127.0.0.1:55432/prefix_test` for the server above. The test database is created and migrated automatically.

To take the README screenshots again, set `SCREENSHOTS=1` and run `pnpm --filter @prefix/web exec playwright test screenshots` (PowerShell: `$env:SCREENSHOTS = "1"` first). It uses the throwaway hospital from the end-to-end fixture, never the demo data.

## Troubleshooting

- **`EPERM` from `corepack enable`.** Use the `--install-directory` form in step 1.
- **`Executable pnpm not found` when committing.** The pre-commit hooks run `pnpm`. Enable corepack (step 1) and open a new terminal, so the new PATH is picked up.
- **Port 3000 or 8000 is in use, or the page is out of date.** A web or API process from an earlier run is still listening. Find it with `Get-NetTCPConnection -LocalPort 3000,8000 -State Listen` (PowerShell) or `lsof -i :3000` (macOS/Linux), and stop it. The end-to-end runs reuse a running server, so a stale one makes tests fail for no obvious reason.
- **`connection timeout expired` or `database system is starting up`.** PostgreSQL is starting or recovering after an unclean shutdown. Wait a little, then retry. If it stays down, run `scripts/dev_postgres.py` again.
- **"Too many requests" on sign-in.** Failed password attempts are limited to 10 per account in 15 minutes, and guest sign-in to 5 per client address in 10 minutes. The limits live in the API process, so restarting the API clears them.
- **The guest demo is empty or missing.** Run `uv run python -m prefix_api.seed_demo` again. It wipes and rebuilds the demo hospital, and keeps its users and protocols.
- **Emails or messages are not sent.** That is expected locally: `MESSAGING_PROVIDER=console` only logs them, with recipients masked. Set the `live` provider and the Twilio or SMTP values only when you mean to send.
