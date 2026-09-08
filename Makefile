# Saskia RMS — Makefile
# Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E24.S1.
#
# Wraps the uv + pytest + ruff workflow into single-letter commands.
# Use `make help` for the full list.

PROJECT_NAME := saskia-rms
PYTHON := uv run python
PYTEST := uv run pytest
RUFF := uv run ruff
ENTRY := app/rms/main.py
ENV := AIW_SASKIA_DB_URL ?= sqlite:///./saskia.db

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Install dev dependencies via uv.
	uv sync --dev

.PHONY: test
test: ## Run the test suite (pytest).
	$(PYTEST) -q

.PHONY: test-verbose
test-verbose: ## Run the test suite with -v.
	$(PYTEST) -v --no-header

.PHONY: test-coverage
test-coverage: ## Run tests with coverage report.
	$(PYTEST) --cov=app --cov-report=term-missing --cov-report=html

.PHONY: lint
lint: ## Run ruff lint.
	$(RUFF) check .

.PHONY: lint-fix
lint-fix: ## Run ruff lint with auto-fix.
	$(RUFF) check . --fix

.PHONY: format
format: ## Run ruff format.
	$(RUFF) format .

.PHONY: check
check: lint test ## Run lint + tests.

.PHONY: serve
serve: ## Run the local server on 127.0.0.1:8765.
	$(PYTHON) $(ENTRY) serve --host 127.0.0.1 --port 8765

.PHONY: migrate
migrate: ## Apply pending schema migrations.
	$(PYTHON) $(ENTRY) migrate

.PHONY: seed
seed: ## Populate demo data (idempotent).
	$(PYTHON) $(ENTRY) seed

.PHONY: seed-reset
seed-reset: ## Drop + re-create + reseed demo data.
	$(PYTHON) $(ENTRY) seed --reset

.PHONY: backup
backup: ## Run a backup to local + R2.
	$(PYTHON) scripts/backup.py

.PHONY: fixtures
fixtures: ## Rebuild Drive-shape xlsx fixtures.
	$(PYTHON) tests/fixtures/build_herbus_fixture.py

.PHONY: clean
clean: ## Remove generated artifacts (DBs, caches, .pyc).
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache htmlcov
	rm -f saskia.db saskia.db-journal

.PHONY: ci-smoke
ci-smoke: ## CI smoke: migrate + seed + 1 dashboard test.
	$(PYTHON) $(ENTRY) migrate
	$(PYTEST) tests/test_smoke.py -v --no-header

.PHONY: pre-commit
pre-commit: lint-fix format test ## Pre-commit hook equivalent.

.PHONY: stats
stats: ## Project LOC stats.
	@echo "--- Python LOC ---"
	@find app -name "*.py" | xargs wc -l | tail -1
	@echo "--- Test LOC ---"
	@find tests -name "*.py" | xargs wc -l | tail -1
	@echo "--- Test count ---"
	@$(PYTEST) --collect-only -q 2>/dev/null | tail -1
