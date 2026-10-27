"""Run a local PostgreSQL + pgvector for development WITHOUT Docker.

Uses the `pgserver` package (bundled Postgres binaries). Data lives in `.devdb/` (git-ignored).
Starts the server if needed (it keeps running in the background), creates the `prefix_dev`
database, and writes its URL into the DATABASE_URL line of `.env`.

    uv run --no-project --python 3.12 --with pgserver python scripts/dev_postgres.py

Run it again after a reboot: the port can change, and .env is updated to match.
Development only. Never point production at this.
"""

import pathlib
import re
import sys

import pgserver

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / ".devdb"
ENV_FILE = ROOT / ".env"
DATABASE = "prefix_dev"


def main() -> None:
    if not ENV_FILE.exists():
        sys.exit("No .env found. First run: copy .env.example .env")

    DATA_DIR.mkdir(exist_ok=True)
    server = pgserver.get_server(DATA_DIR, cleanup_mode=None)
    exists = server.psql(f"SELECT 1 FROM pg_database WHERE datname = '{DATABASE}';")
    if "(1 row)" not in exists:
        server.psql(f"CREATE DATABASE {DATABASE};")

    base = server.get_uri().rsplit("/", 1)[0].replace("postgresql://", "postgresql+psycopg://")
    url = f"{base}/{DATABASE}"
    text = ENV_FILE.read_text(encoding="utf-8")
    new_text, count = re.subn(r"(?m)^DATABASE_URL=.*$", f"DATABASE_URL={url}", text)
    if count == 0:
        new_text = text.rstrip("\n") + f"\nDATABASE_URL={url}\n"
    ENV_FILE.write_text(new_text, encoding="utf-8")

    test_url = f"{base}/prefix_test"
    print(f"PostgreSQL is running. Wrote to .env: DATABASE_URL={url}")
    print(f"For `make test` / pytest, use: TEST_DATABASE_URL={test_url}")


if __name__ == "__main__":
    main()
