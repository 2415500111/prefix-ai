# syntax=docker/dockerfile:1
# Build context: repository root (the uv workspace lockfile lives there).
# Used for both the Celery worker and Celery beat; docker-compose.yml picks the command.
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/worker/pyproject.toml apps/worker/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package prefix-worker --no-install-workspace

COPY apps/api apps/api
COPY apps/worker apps/worker
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package prefix-worker

RUN useradd --create-home --uid 10001 app
USER app

WORKDIR /app/apps/worker

CMD ["celery", "--app", "prefix_worker.celery_app", "worker", "--loglevel", "INFO"]
