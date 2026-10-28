"""Run a local PostgreSQL + pgvector for development WITHOUT Docker.

Uses the `pgserver` package (bundled Postgres binaries). Data lives in `.devdb/` (git-ignored).
The server always listens on FIXED_PORT, so the DATABASE_URL in `.env` never goes stale. If a
server from an earlier run is still on another port, it is stopped first.

    uv run --no-project --python 3.12 --with pgserver python scripts/dev_postgres.py

Development only. Never point production at this.
"""

import pathlib
import re
import subprocess
import sys

import pgserver
import pgserver.postgres_server as pgserver_server

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / ".devdb"
ENV_FILE = ROOT / ".env"
DATABASE = "prefix_dev"
FIXED_PORT = 55432
PG_BIN = pathlib.Path(pgserver.__file__).parent / "pginstall" / "bin"
PG_CTL = PG_BIN / ("pg_ctl.exe" if sys.platform == "win32" else "pg_ctl")


def _stop_server_on_other_port() -> None:
    """postmaster.pid line 4 is the port of the server recorded in the data directory."""
    pid_file = DATA_DIR / "postmaster.pid"
    if not pid_file.exists():
        return
    lines = pid_file.read_text(encoding="utf-8").splitlines()
    if len(lines) < 4 or lines[3].strip() == str(FIXED_PORT):
        return
    print(f"Stopping the server on port {lines[3].strip()} so it can move to {FIXED_PORT}.")
    # Fails harmlessly if the recorded server is already gone.
    # The binary is a fixed file from the pgserver package, not user input.
    subprocess.run(  # noqa: S603
        [str(PG_CTL), "-D", str(DATA_DIR), "stop", "-m", "fast", "-w", "-t", "60"], check=False
    )


def main() -> None:
    if not ENV_FILE.exists():
        sys.exit("No .env found. First run: copy .env.example .env")

    DATA_DIR.mkdir(exist_ok=True)
    _stop_server_on_other_port()
    # pgserver picks a random free port on Windows. Pin it to FIXED_PORT for this start.
    pgserver_server.find_suitable_port = lambda host: FIXED_PORT

    server = pgserver.get_server(DATA_DIR, cleanup_mode=None)
    exists = server.psql(f"SELECT 1 FROM pg_database WHERE datname = '{DATABASE}';")
    if "(1 row)" not in exists:
        server.psql(f"CREATE DATABASE {DATABASE};")

    base = server.get_uri().rsplit("/", 1)[0].replace("postgresql://", "postgresql+psycopg://")
    url = f"{base}/{DATABASE}"
    text = ENV_FILE.read_text(encoding="utf-8")
    new_text = _rewrite_database_url(text, url)
    ENV_FILE.write_text(new_text, encoding="utf-8")

    print(f"PostgreSQL is running on port {FIXED_PORT}. Wrote to .env: DATABASE_URL={url}")
    print(f"For `make test` / pytest, use: TEST_DATABASE_URL={base}/prefix_test")


def _rewrite_database_url(text: str, url: str) -> str:
    new_text, count = re.subn(r"(?m)^DATABASE_URL=.*$", f"DATABASE_URL={url}", text)
    if count == 0:
        new_text = text.rstrip("\n") + f"\nDATABASE_URL={url}\n"
    return new_text


if __name__ == "__main__":
    main()
