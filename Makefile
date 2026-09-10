# Saskia RMS — Makefile
# Shortcuts for common dev tasks. Run `make help` to see all targets.

.PHONY: help install test test-fast lint format serve migrate seed smoke check-warnings check-secrets clean ci

PYTHON ?= python3
UV ?= uv

help: ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies via uv.
	$(UV) sync --all-extras

test: ## Run the full test suite.
	unset DATABASE_URL AIW_SASKIA_DB_PATH; \
	$(UV) run pytest -q --no-header

test-fast: ## Run tests without coverage (faster).
	unset DATABASE_URL AIW_SASKIA_DB_PATH; \
	$(UV) run pytest -q --no-header --no-cov

lint: ## Run ruff linter.
	$(UV) run ruff check .

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

ci: lint test ## Run everything CI runs.

clean: ## Remove build artifacts.
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
