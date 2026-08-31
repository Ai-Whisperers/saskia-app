# App CHANGELOG — Saskia RMS

> **For Kiki, Saskia, and any agent.** App-level changelog separate from the
> repo-level changelog. Tracks changes to the `app/` source code, not the docs.

## [Unreleased] — pre-signoff skeleton

**Status:** Skeleton landed in pre-signoff commit `f82dfb3` of the engagement repo,
which migrated to `saskia-app` repo. **Not yet on her PC.**

### Added

- `pyproject.toml` with Python 3.13, FastAPI 0.115, uvicorn[standard], SQLAlchemy 2.0,
  openpyxl 3.1, Jinja2, pydantic 2.9, loguru. Dev: pytest, pytest-cov, hypothesis, ruff.
- `LICENSE` (MIT).
- `.gitignore` blocking `__pycache__/`, `.venv/`, `*.sqlite`, `*.log`, `.env`.
- `.pre-commit-config.yaml` (ruff + smoke tests + secret detection).
- `.github/workflows/ci.yml` (ruff + pytest + 80% coverage gate).
- `app/rms/__init__.py` (package marker).
- `app/rms/money.py` (Decimal helpers, Gs. formatting, strict parsing).
- `app/rms/units.py` (Unit enum with alias coercion, intra-family conversion).
- `app/routers/__init__.py`, `app/services/__init__.py`.
- `app/routers/health.py` (`/healthz`, `/healthz/db`).
- `app/services/auto_backup.py` (backup helper functions).
- `app/docs/copy-vos.md` (UI copy bank template).
- `app/docs/threat-model.md` (single-user, single-PC, single trust boundary).
- `app/docs/architecture.md` (data flow, sources of truth, timezone).
- `app/docs/upgrade-tiers.md` (Tier matrix for future upgrades).
- `app/rms/AGENTS.md` (engineering conventions for `app/rms/`).
- `tests/conftest.py`, `tests/test_money.py` (43 tests), `tests/test_units.py` (45 tests).
- `installer/README.md` (install-session checklist).
- `installer/run.bat` (Windows launcher using `uv`).
- `docs/sessions/round-2-feedback.md` (review template).

### Test results

- 88 tests pass (43 money + 45 units).
- ruff clean (lint + format).

### Known gaps (for next sprint)

- `app/rms/db.py` (SQLite engine + WAL + versioned migrations) — Task 1 of dev plan.
- `app/rms/models.py` (7 tables + polymorphic recipe_line) — Task 1.
- `app/rms/costing.py` (recipe_batch_cost, product_unit_cost, margin) — Task 2.
- `app/rms/main.py` (FastAPI app with lifespan) — Task 1.
- `app/routers/dashboard.py`, `products.py`, `recipes.py`, `inventory.py`, `sales.py`,
  `excel_io.py` — Tasks 3-7.
- `app/services/import_xlsx.py`, `export_xlsx.py`, `reports.py`, `r2_backup.py`
  — Tasks 6, 9, 12.
- `app/templates/base.html`, `inicio.html`, etc. — Tasks 3-7.
- `installer/run.sh` (Mac) — Task 9.
- `installer/r2-setup.md` — Task 9.
- `tests/test_costing.py`, `test_stock_drop.py`, `test_void_sale.py`,
  `test_import_roundtrip.py`, `test_healthz.py`, `test_r2_backup.py`,
  `test_recipe_polymorphic.py` — Tasks 1, 2, 6, 9.
- `tests/fixtures/stress.xlsx` (real-scale synthetic) — Task 6.

## Versioning

- We use CalVer: `YYYY.MM.patch` (e.g., `2026.09.0`).
- Major = 0 until fase 1 ships.
- After fase 1: `1.0.0`, then `1.1.0` for Fase 1.5, `2.0.0` for Fase 2.
