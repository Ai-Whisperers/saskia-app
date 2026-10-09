# Sazón RMS — Makefile
# Shortcuts for common dev tasks. Run `make help` to see all targets.

.PHONY: help install test test-verbose test-coverage test-fast lint lint-fix format check serve migrate seed seed-reset backup fixtures clean ci-smoke pre-commit stats smoke check-warnings check-secrets ci dead-code complexity duplicates duplicates-code arch security audit-cve licenses ci-extra

PYTHON ?= python3
UV ?= uv

help: ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies via uv.
	$(UV) sync --all-extras

test: ## Run the full test suite.
	unset DATABASE_URL AIW_RMS_DB_PATH; \
	uv run pytest -q --no-header

test-fast: ## Run tests without coverage (faster).
	unset DATABASE_URL AIW_RMS_DB_PATH; \
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

check: ## Run pre-commit style checks (duplicates + arch + import rules).
	@echo "=== format check (ruff, no writes) ==="
	@uv run ruff format --check . || echo "  (format drift; run: make format)"
	@echo "=== duplicates (stem collisions + forbidden legacy) ==="
	@uv run python scripts/check_duplicate_files.py
	@echo "=== imports (cycles + arch rules) ==="
	@uv run python scripts/check_imports.py
	@echo "=== done ==="

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
	unset DATABASE_URL AIW_RMS_DB_PATH; \
	$(UV) run pytest tests/e2e/ -q --no-header --no-cov

test-migration: ## Weekly: full migration replay sweep (all versions).
	unset DATABASE_URL AIW_RMS_DB_PATH; \
	$(UV) run pytest tests/e2e/test_migration_archaeology.py -q --no-header --no-cov

test-xdist: ## Parallel fast loop (-n 4 green since 2026-09-25).
	unset DATABASE_URL AIW_RMS_DB_PATH; \
	$(UV) run pytest tests/ -q --no-header --no-cov -n 4 \
	  --deselect tests/test_xlsx_fixtures.py --deselect tests/test_shopping_benchmarks.py

dead-code: ## vulture + sensez: scan for unused code + structural smells.
	$(UV) run vulture app/ scripts/ --min-confidence 80 \
	  --ignore-decorators @app.get,@app.post,@app.put,@app.delete,@router.get,@router.post,@router.put,@router.delete,@app.exception_handler,@app.middleware,@app.on_event,@staticmethod,@classmethod,@property \
	  --ignore-names 'test_*,Test*,_test_*' 2>&1 | tail -30
	@echo ""
	@echo "=== sensez (structural maintainability) ==="
	$(UV) run sensez app/ 2>&1 | head -40 || true
	@echo "Note: sensez is advisory. See docs/operations/2026-10-09-sensez-ty-evaluation.md."

complexity: ## radon: cyclomatic complexity ceiling (B = CC<=10).
	$(UV) run python scripts/check_complexity.py

cognitive: ## complexipy: cognitive complexity (>15 = FAIL; >25 = must fix).
	@echo "=== complexipy (cognitive complexity, SonarSource spec) ==="
	$(UV) run complexipy --max-complexity-allowed 15 app/rms/ 2>&1 | tail -20 || true
	@echo "(>15 = warning, >25 = must fix; threshold is per Sazon conventions)"

deptry: ## deptry: find unused/missing/transitive deps.
	@echo "=== deptry (dependency hygiene) ==="
	$(UV) run deptry . 2>&1 | tail -10 || true
	@echo "Note: many DEP003 'starlette' are false positives — starlette is a"
	@echo "FastAPI transitive, but we import symbols directly. See pyproject.toml."

interrogate: ## interrogate: docstring coverage (gate: 80%).
	@echo "=== interrogate (docstring coverage) ==="
	$(UV) run interrogate -f 80 app/rms/ app/observability/ 2>&1 | tail -3

pyright: ## pyright: static type checker (catches real bugs).
	@echo "=== pyright (Microsoft type checker) ==="
	$(UV) run pyright --pythonpath .venv/bin/python app/rms/main.py app/rms/db.py 2>&1 | tail -10 || true
	@echo "Note: pyright is advisory. Run on main.py + db.py first; full sweep later."

refurb: ## refurb: modernization hints (FURB rules; FYI only).
	@echo "=== refurb (modernization hints) ==="
	-$(UV) run refurb app/rms/ 2>&1 | tail -5
	@echo "Note: refurb is FYI. Most findings are FURB123 redundant casts."
	@echo "Pre-Pydantic code is noisy. Do not auto-fix."

duplicates: ## Detect duplicate-stem files + forbidden legacy + unused modules.
	$(UV) run python scripts/check_duplicate_files.py

duplicates-code: ## Detect near-duplicate function bodies (>=80% similarity).
	$(UV) run python scripts/check_duplicate_code.py

arch: ## Architecture linter: no cycles, no rule violations.
	$(UV) run python scripts/check_imports.py

security: ## bandit security scan (medium+high severity).
	$(UV) run bandit -r app/ -ll -q --exclude app/_archive

audit-cve: ## pip-audit: scan pyproject deps for known CVEs.
	$(UV) run pip-audit -r pyproject.toml

licenses: ## reuse: SPDX license header compliance.
	$(UV) run reuse lint

workflows-lint: ## zizmor: GitHub Actions workflow lint (config in .github/zizmor.yml).
	@echo "=== zizmor (GitHub Actions security) ==="
	uvx --from zizmor zizmor \
		--config .github/zizmor.yml \
		--min-severity=high \
		.github/workflows/ 2>&1 | tail -50 || true
	@echo ""
	@echo "Note: HIGH-severity findings block PRs via .github/workflows/workflows-lint.yml."
	@echo "Run without --min-severity=high to see all 64 findings (15 high, 49 info)."

workflows-lint-all: ## zizmor: show all findings (not just high).
	@echo "=== zizmor (all severities) ==="
	uvx --from zizmor zizmor \
		--config .github/zizmor.yml \
		.github/workflows/ 2>&1 | tail -100 || true

docs-lint: ## Markdown quality check (pymarkdownlnt; see scripts/check_docs_quality.py).
	$(UV) run python scripts/check_docs_quality.py

docs-lint-strict: ## Markdown quality check, all rules (no disables).
	$(UV) run python scripts/check_docs_quality.py --strict

jscpd: ## jscpd: line-level copy-paste detector (complements duplicates-code).
	@echo "=== jscpd (line-level copy-paste) ==="
	$(UV) run jscpd app/ --reporters console --threshold 5 2>&1 | tail -30 || true
	@echo "Note: jscpd finds 5+ line exact duplicates. complements duplicates-code"
	@echo "which uses AST similarity >=80%."

deadcode-code: ## deadcode: cross-file dead-code scan (complements vulture).
	@echo "=== deadcode (cross-file dead code) ==="
	$(UV) run deadcode app/ scripts/ 2>&1 | tail -30 || true
	@echo "Note: deadcode complements vulture with cross-file analysis."

tool-matrix: ## Print the tooling coverage matrix.
	@echo "=== Tooling coverage matrix (as of 2026-10-09) ==="
	@echo ""
	@echo "| Tool          | Decl | Make | Pre-C | CI  |"
	@echo "|---------------|------|------|-------|-----|"
	@echo "| ruff          |  ✓   |  ✓   |   ✓   |  ✓  |"
	@echo "| pytest        |  ✓   |  ✓   |   ✓   |  ✓  |"
	@echo "| vulture       |  ✓   |  ✓   |   ✓   |     |"
	@echo "| deadcode      |  ✓   |  ✓   |       |     |"
	@echo "| bandit        |  ✓   |  ✓   |   ✓   |     |"
	@echo "| radon-cc      |  ✓   |  ✓   |   ✓   |     |"
	@echo "| complexipy    |  ✓   |  ✓   |       |  ✓  |"
	@echo "| pyright       |  ✓   |  ✓   |       |  ✓  |"
	@echo "| mypy          |      |      |       |  ✓ (info) |"
	@echo "| deptry        |  ✓   |  ✓   |       |     |"
	@echo "| interrogate   |  ✓   |  ✓   |       |     |"
	@echo "| refurb        |  ✓   |  ✓   |       |     |"
	@echo "| pip-audit     |  ✓   |  ✓   |       |     |"
	@echo "| reuse         |  ✓   |  ✓   |       |     |"
	@echo "| jscpd         |  ✓   |  ✓   |       |     |"
	@echo "| sensez        |  ✓   |  ✓   |       |     |"
	@echo "| pymarkdownlnt |      |  ✓   |       |     |"
	@echo "| hypothesis    |  ✓   |      |       |  ✓  |"
	@echo "| playwright    |  ✓   |  ✓   |       |  ✓  |"
	@echo "| testcontainers |  ✓   |      |       |  ✓  |"
	@echo "| sentry        |  ✓   |      |       |     |"
	@echo "| zizmor        |      |  ✓   |       |  ✓  |"
	@echo ""
	@echo "Full analysis: docs/operations/2026-10-09-tooling-research.md"

ci-extra: lint dead-code complexity cognitive deptry duplicates arch security workflows-lint ## All static analysis (slow).
	@echo ""
	@echo "ci-extra complete."

ci: lint test ## Run everything CI runs.


clean: ## Remove build artifacts.
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
