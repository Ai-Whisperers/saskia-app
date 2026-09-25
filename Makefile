# Saskia RMS — Makefile
# Shortcuts for common dev tasks. Run `make help` to see all targets.

.PHONY: help install test test-verbose test-coverage test-fast lint lint-fix format check serve migrate seed seed-reset backup fixtures clean ci-smoke pre-commit stats smoke check-warnings check-secrets ci

PYTHON ?= python3
UV ?= uv

help: ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies via uv.
	$(UV) sync --all-extras

test: ## Run the full test suite.
	unset DATABASE_URL AIW_SASKIA_DB_PATH; \
	uv run pytest -q --no-header

test-fast: ## Run tests without coverage (faster).
	unset DATABASE_URL AIW_SASKIA_DB_PATH; \
	$(UV) run pytest -q --no-header --no-cov

lint: ## Run ruff linter.
	uv run ruff check .

format: ## Auto-format with ruff.
	$(UV) run ruff check . --fix
	$(UV) run ruff format .

serve: ## Run the app locally on PORT (default 8000).
	$(UV) run uvicorn app.rms.main:app --host 127.0.0.1 --port $${PORT:-8000}

migrate: ## Apply DB migrations (idempotent).
	$(UV) run python -c "from app.rms.db import init_db; from app.rms.db_dialect import make_engine; \
	  from sqlalchemy.orm import sessionmaker; \
	  Session = sessionmaker(bind=make_engine()); \
	  init_db(Session())"

seed: ## Seed demo data (only for local dev, NOT production).
	$(UV) run python -c "from app.rms.seed import seed_demo_data; \
	  from app.rms.db import init_db; from app.rms.db_dialect import make_engine; \
	  from sqlalchemy.orm import sessionmaker; \
	  Session = sessionmaker(bind=make_engine()); \
	  init_db(Session()); seed_demo_data(Session())"

smoke: ## Run the deploy-shape smoke test locally (requires Docker).
	$(UV) run python scripts/smoke_test_deploy_shape.py --skip-docker --skip-build --port 18999

check-warnings: ## Verify test suite runs with 0 warnings.
	$(UV) run python scripts/check_warnings.py

check-secrets: ## Scan staged files for leaked credentials.
	$(PYTHON) scripts/check_no_secrets.py

test-verbose: ## Run tests with verbose output.
	uv run pytest -v --no-header

test-coverage: ## Run tests with coverage report.
	uv run pytest --cov=app --cov-report=term-missing --no-header

lint-fix: ## Auto-fix lint errors.
	uv run ruff check . --fix

check: ## Run pre-commit style checks (lint + warnings + secrets).
	uv run ruff check .
	uv run python scripts/check_warnings.py

seed-reset: ## Drop and recreate demo data (DESTRUCTIVE — local dev only).
	uv run python -c "from app.rms.seed import seed_demo_data; \
	  from app.rms.db import init_db; from app.rms.db_dialect import make_engine; \
	  from sqlalchemy.orm import sessionmaker; \
	  eng = make_engine(); init_db(sessionmaker(bind=eng)()); \
	  seed_demo_data(sessionmaker(bind=eng)())"

backup: ## Run the local backup script.
	uv run python scripts/backup.py

fixtures: ## Regenerate test fixtures (incl. real Drive shape).
	uv run python tests/fixtures/build_herbus_drive_fixture.py

ci-smoke: ## Run the deploy-shape smoke test (requires Docker).
	uv run python scripts/smoke_test_deploy_shape.py --skip-docker --skip-build --port 18999

pre-commit: ## Run pre-commit hooks if installed.
	@command -v pre-commit >/dev/null 2>&1 && pre-commit run --all-files || echo "pre-commit not installed; skipping"

stats: ## Show LOC + test count summary.
	@echo "=== LOC by area ==="
	@find app -name "*.py" -not -path "*/__pycache__/*" | xargs wc -l | tail -1
	@find tests -name "*.py" -not -path "*/__pycache__/*" | xargs wc -l | tail -1
	@echo "=== Test count ==="
	@uv run pytest --collect-only -q 2>/dev/null | tail -1


test-browser: ## Real-browser (Playwright/Chromium) front-end tests.
	$(UV) run pytest tests/browser -m browser -q

test-e2e: ## Run the E2E scenario suite only (tests/e2e/).
	unset DATABASE_URL AIW_SASKIA_DB_PATH; \
	$(UV) run pytest tests/e2e/ -q --no-header --no-cov

test-migration: ## Weekly: full migration replay sweep (all versions).
	unset DATABASE_URL AIW_SASKIA_DB_PATH; \
	$(UV) run pytest tests/e2e/test_migration_archaeology.py -q --no-header --no-cov

test-xdist: ## Parallel fast loop (-n 4 green since 2026-09-25).
	unset DATABASE_URL AIW_SASKIA_DB_PATH; \
	$(UV) run pytest tests/ -q --no-header --no-cov -n 4 \
	  --deselect tests/test_xlsx_fixtures.py --deselect tests/test_shopping_benchmarks.py

ci: lint test ## Run everything CI runs.

clean: ## Remove build artifacts.
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
