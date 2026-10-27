# Prefix AI developer commands. Run `make help` for the list.
# Docker targets need Docker Compose v2; test/lint/format run natively and need uv + pnpm.

COMPOSE := docker compose
# Tests need Postgres: `docker compose up -d postgres` (the test database is created automatically).
export TEST_DATABASE_URL ?= postgresql+psycopg://prefix:prefix@localhost:5432/prefix_test
API_RUN := $(COMPOSE) run --rm api

.DEFAULT_GOAL := help

.PHONY: help setup up down restart logs ps health migrate migration seed test lint format clean

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

.env:
	cp .env.example .env
	@echo "Created .env from .env.example. Review it before going further."

setup: .env ## Install Python + JS dependencies and git hooks for native development
	uv sync
	pnpm install
	uv run pre-commit install

up: .env ## Build and start the full stack in the background
	$(COMPOSE) up --build --detach --wait
	@echo "API: http://localhost:8000/health   Web: http://localhost:3000"

down: ## Stop the stack (data volumes are kept)
	$(COMPOSE) down

restart: down up ## Restart the stack

logs: ## Follow logs from all services
	$(COMPOSE) logs --follow --tail=100

ps: ## Show service status and health
	$(COMPOSE) ps

health: ## Call the API and web health endpoints
	curl --fail --silent --show-error http://localhost:8000/health && echo
	curl --fail --silent --show-error http://localhost:3000/api/health && echo

migrate: .env ## Apply database migrations
	$(API_RUN) alembic upgrade head

migration: .env ## Create a migration (stack must be up): make migration m="add patients table"
	@test -n "$(m)" || (echo 'Usage: make migration m="description"' && exit 1)
	uv run alembic -c apps/api/alembic.ini revision --autogenerate -m "$(m)"

seed: .env ## Load development seed data
	$(API_RUN) python -m prefix_api.seed

test: ## Run all tests (Python + web)
	uv run pytest
	pnpm -r test

lint: ## Run all linters and type checkers
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	pnpm -r lint
	pnpm -r typecheck
	pnpm format:check

format: ## Auto-format and auto-fix code
	uv run ruff check --fix .
	uv run ruff format .
	pnpm format

clean: ## Stop the stack AND delete its data volumes
	$(COMPOSE) down --volumes --remove-orphans
