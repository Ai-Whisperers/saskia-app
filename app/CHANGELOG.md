# App CHANGELOG — Saskia RMS

> **For Kiki, Saskia, and any agent.** App-level changelog separate from the
> repo-level changelog. Tracks changes to the `app/` source code, not the docs.

## [Unreleased]

### Added

- `.github/ISSUE_TEMPLATE/{bug,feature,epic}.md` for guided issue filing.
- AGENTS.md gains "Issue templates", "Locked hotfixes", and refreshed CI
  list sections.
- **Audit log (E3.S1)**: `audit_log` table + `app/rms/audit.py` record()
  helper. Captures `login.success`, `login.failure`, `logout` from the
  auth router with X-Forwarded-For IP + truncated User-Agent. Append-only
  by convention; surfaced later via /audit admin view.
- Schema migration `_migration_002_audit_log` (CURRENT_SCHEMA_VERSION
  bumped 1 -> 2). Idempotent. `aiw-saskia migrate` applies it on first
  run against existing DBs.
- **Tag system + filters (E9)** — schema v4; 31 starter tags;
  polymorphic M:N (product/ingredient/recipe); filter dataclasses for
  Ventas/Inventario/Recetas/Productos.
- **Drive-shape xlsx fixtures (E7)** — 4 fixtures under tests/fixtures/
  (minimal, realistic, edge cases, herbus-compat) + 10 round-trip tests.
  Rebuild with `uv run python tests/fixtures/build_herbus_fixture.py`.

- **Operational analytics dashboard (E8)** — `app/rms/analytics.py` adds
  stock turnover, dead-stock detection, margin-erosion alerts, day-of-week
  heatmap, top-margin ranking, ingredient concentration, recipe complexity.
  Schema v3 adds 4 nullable columns: ingredient.purchase_price_updated_at,
  last_consumed_at (indexed), shelf_life_days (E22 prep), recipe.prep_minutes.

- **Realistic demo data seed (E6)** — `app/rms/seed.py` +
  `aiw-saskia seed [--reset]`. 30 ingredients, 12 recipes, 80
  recipe_lines, 20 products, ~200 synthetic sales over 90 days with
  weekday/weekend skew + payday spikes, demo user, voided + encargo
  examples, import_batch + audit_log seed rows. Idempotent.

- **Dashboard TZ fix** — period_window now converts to UTC-naive
  before DB compare (was treating Asunción-local as naive-UTC which
  broke `today` filter outside UTC midnight).

- **Complete epic plan v3 (`docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md`)** —
  25 epics across 6 phases, ~268h, no cap (gem project). Each epic has
  Why / Stories / Tasks / Effort / Depends on / Acceptance / Refs.
  Ticket convention `SASKIA-NNN` defined in `AGENTS.md`.

- **Security headers (E3.S3)**: `app/rms/security_headers.py` adds
  X-Frame-Options, X-Content-Type-Options, Referrer-Policy, restrictive
  CSP, and Permissions-Policy on every response (including /healthz
  and 3xx redirects). HSTS conditional on HTTPS_ONLY (off for local-dev
  over http). 9 tests lock the behavior in.
- **Login rate-limit (E3.S2)**: 5 failures / 5 min per IP → 429 with
  Retry-After. Backed by audit log (login.rate_limited rows for forensics).
  /healthz is exempt. AIW_SASKIA_AUTH_DISABLED=1 bypasses for tests.
- **CF tunnel rotation runbook (E1.S3)**:
  `docs/operations/cf-tunnel-rotation.md`. 7-step procedure with
  90-day cadence (next: 2026-12-04) and rollback. Operator-only;
  assistant cannot perform the rotation itself (CF dashboard access).

## [Unreleased-pre-templates] — pre-signoff skeleton

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

## [2026.09.0] — 2026-09-04 / 2026-09-07 — Fase 1.5 hardening

**Status:** Closed Fase 1 production hotfixes + hardened deploy CI. **On her PC** once operator syncs `main` branch.

### Added

- **`docs/wishlist/`** (append-only bucket for future ideas; 21 seeds from
  critical-path analysis). Includes `README.md` format spec and `raw/` /
  `triaged/` / `rejected/` subdirs.
- **`tests/test_hotfix_regressions.py`** — 15 fail-closed tests for the 5
  production hotfixes landed on 2026-09-04 (HEAD /healthz, SUPABASE_SECRET_KEY
  alias, supabase in Dockerfile pip list, /healthz/deps fingerprint,
  row_counts_json JSONB match). Proven fail-closed by reverting the HEAD route
  and confirming 2 tests fail with the original 405.
- **`tests/test_migrate_cli.py`** — 5 tests covering the new `aiw-saskia
  migrate` CLI (idempotent first/second run, schema detection across SQLite
  and Postgres dialects, argv dispatch).
- **CLI dispatch in `app/rms/main.py`**: `run()` now dispatches on sys.argv —
  `aiw-saskia migrate` invokes `migrate()` (idempotent schema apply);
  `aiw-saskia serve` and bare `aiw-saskia` start uvicorn (backward compatible).
- **`migrate()` entry point** in `app/rms/main.py`: idempotent (checks
  schema_version; no-op if already at target); supports both `DATABASE_URL`
  (Postgres) and `AIW_SASKIA_DB_PATH` (SQLite) so it works for hosted and
  local dev.
- **CI: migrate smoke test** in `.github/workflows/ci.yml` — runs
  `aiw-saskia migrate` against a fresh SQLite on every PR to catch migrate()
  regressions.
- **CI: CHANGELOG discipline check** — every PR touching `app/`, `scripts/`,
  `tests/`, or `.github/` must also touch `app/CHANGELOG.md` or CI fails.

### Changed

- **`scripts/apply_neon_schema.py`** — now a thin wrapper around `migrate()`
  with dialect-aware schema introspection (works on both PG and SQLite).
- **`docs/operations/dashboard/refresh.sh`** — autodetects when `$PWD` is a
  saskia-app git repo, falling back to the legacy scratch path only when
  both are absent. Previously the hard-coded path didn't exist.
- **`installer/README.md`** — clone URL corrected from `saskia.git` to
  `saskia-app.git` (commit `6fef4a2`).

### Test results

- 354 tests pass (was 334; +20 from `test_hotfix_regressions` and
  `test_migrate_cli`).
- Coverage: 82% (was 81%; held at >= 80% gate).

### Hotfixes locked in by the regression suite (commits on `main`)

- `f1af406` — HEAD /healthz for UptimeRobot
- `c093a75` — SUPABASE_SECRET_KEY / SUPABASE_PUBLISHABLE_KEY aliases
- `99b37c6` — supabase SDK in Dockerfile pip list
- `bb21eff` — /healthz/deps env fingerprint
- `501bcff` — `row_counts_json` ORM type matches Postgres JSONB column

## Versioning

- We use CalVer: `YYYY.MM.patch` (e.g., `2026.09.0`).
- Major = 0 until fase 1 ships.
- After fase 1: `1.0.0`, then `1.1.0` for Fase 1.5, `2.0.0` for Fase 2.
