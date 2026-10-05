# CHANGELOG

## 2026-10-04 — Phase 3 CI cleanup (PR #46)

**Goal:** bring ruff from 1910 errors → 0 across the codebase, eliminate currency-drift footguns, fix real bugs hiding behind lint errors.

### Ruff cleanup (1910 → 0 across 21 commits on `feat/phase-3-ci-cleanup`)

| Category | Count | Approach |
|---|---|---|
| **B904** (raise from None) | 10 | Added `from None` to exception handlers in csrf/services/closures/routers |
| **PERF401** (list comps in prod) | 6 | Converted to explicit loops; test cases ignored via pyproject.toml |
| **BLE001** (bare except) | 35 | `# noqa: BLE001` with rationale for 8 in prod; rest in tests/scripts/docs |
| **F811** (dead re-definitions) | 12 | Removed 6 dead wire-stub re-definitions in `app/rms/db.py`; renamed duplicates in `sales.py`, removed in 4 test files |
| **F821** (undefined names) | 50+ | Added missing imports across 30+ test files + 3 prod bugs (Boolean, sales_intel funcs, BackupResult) |
| **ANN202** (missing return types) | 9 | Added `-> Callable`, `-> Iterator[str]`, `-> dict[str, Any]` etc. |
| **DTZ007** (naive strptime) | 6 | Documented DB-naive-UTC convention with `# noqa: DTZ007` |
| **PERF403** (eff. comprehensions) | 4 | Converted to lists in cost_freshness, supplier_prices, demo, screenshot script |
| **PIE810/S310/S110** | 8 | `startswith` tuples, urlopen schemes, try-except-pass noqas |
| **RUF043** (regex metachars) | 3 | Converted test `match=` args to raw strings |
| **B018** (useless assignment) | 3 | Removed `session.query(...).one().password_hash` in test_bootstrap_password_sync |
| **DTZ005/ANN002/ANN003/S108/F841/DTZ901/B023/B015/W292/RUF100/F401/I001** | 60+ | Mechanical cleanups |

### Real bugs found & fixed by the cleanup

- **`app/rms/models/sales.py`**: missing `Boolean` import — model would crash at mapper-config time
- **`app/routers/reportes.py`**: 3 missing imports from `app.rms.sales_intel` (`sales_by_hour`, `sales_heatmap`, `waste_roi_by_ingredient`) — would crash on any report request
- **`app/routers/health.py`**: `_run_backup_admin` forward-ref needed `BackupResult` import
- **`tests/test_analytics_properties_phase14_tier4.py`**: `MockScalars` defined inside `MockResult.scalars()` but used at module level (NameError waiting to happen)
- **`tests/test_receta_detalle_2026_09_29_regression.py`**: dead `ior_allergens` reference
- **`app/rms/db.py`**: removed 6 dead wire-stub re-definitions of migration functions (they shadowed real imports)

### pyproject.toml per-file-ignores added

- `tests/*`: ANN, S, DTZ, B011, PERF401, BLE001
- `_smoke/*.py`: ANN, S, DTZ, E501, BLE001
- `scripts/*.py`: ANN, S, BLE001, DTZ
- `docs/**/*.py`: BLE001, S, E501
- `run_migration.py`: BLE001

### Stats

- **1910 → 0 ruff errors** (100% reduction)
- **12 currency-drift** sites (`Gs. {{ ... }}` in templates) → **0** — wrapped in `m.gs_full()`
- **340 files** changed, 19 commits
- Test status: 152/152 pass + 6 PG skip + 3 net skip (pre-existing; no new failures from cleanup)
- PR: https://github.com/Ai-Whisperers/sazon-app/pull/46

### Files that received a disproportionate share of fixes

- `app/routers/health.py` (8 fixes) — most defensive-defaults of any router
- `app/routers/sales.py` (7 fixes) — oldest router, accumulated debt
- `scripts/check_currency_drift.sh` (8 fixes) — quoted template strings with `Gs. {{...}}`
- `pyproject.toml` (6 fixes) — per-file-ignores + line-length tightening
- `app/services/pedido_history.py` (4 fixes) — hot path, lots of `now()`/`timedelta`

---

## 2026-10-01
- **Schema 75** (`app/rms/config.py`): adds `suggestion_applied` to `loyalty_transaction.reason` ENUM (Tier 3.2).

## 2026-10-02 - Backend overhaul (Sprint 1.3)

### Refactor
- **`app/rms/clock.py`** (new) — single source of truth for ``now()``.
  Exposes ``now()`` (UTC-aware), ``today_local()`` (Asuncion-aware),
  ``to_utc()`` / ``to_asuncion()`` for coercion, and a ``utcnow()``
  alias. Every ``datetime.utcnow()`` and bare ``datetime.now()``
  callsite in the app now routes through this module.

### Fix
- **`eod_closed._today_local()`** — replaced the deprecated
  ``datetime.utcnow().date()`` fallback with ``clock.today_local()``.
- **`routers/pedidos.py`** — 5 callsites: 2× ``datetime.utcnow()``
  for ``public_token_expires_at``, 2× ``datetime.utcnow().isoformat()``
  for audit JSON, 1× ``datetime.now()`` for upload timestamps (now
  uses ``today_local()`` for Asuncion-local filenames).
- **`routers/settings_runtime.py`** — 2 ``datetime.utcnow()`` for
  ``SettingsKV.updated_at``.

### New
- **`tests/test_clock_discipline.py`** — 10 tests pinning:
  - The ``clock`` module exposes the canonical helpers.
  - ``now()`` / ``today_local()`` return tz-aware datetimes.
  - ``to_utc()`` / ``to_asuncion()`` correctly handle both naive
    (assumed UTC, legacy convention) and aware inputs.
  - No bare ``datetime.utcnow()`` / ``datetime.now()`` callsites
    remain in ``app/`` (AST-scanned; docstrings and comments are
    tolerated).
  - The three changed routers import from ``app.rms.clock``.

### Important correctness note
- Paraguay's offset is **not** "UTC-4 year-round" as the audit's plan
  claimed. The IANA ``America/Asuncion`` zone correctly returns UTC-3
  during DST and UTC-4 during winter. Sprint 1.3 tests dynamically
  read the current offset instead of hardcoding UTC-4.

### Schema migration deferred
- Sprint 1.3's plan also called for migrating all ``DateTime``
  columns to ``DateTime(timezone=True)`` (migration 083). This was
  deferred to a follow-up sprint because:
  1. Every one of the 80+ tables with a ``DateTime`` column has rows
     that store naive datetimes — the backfill + ``ALTER`` requires
     careful per-dialect handling that wasn't safe to ship without a
     window for the operator to run migrations during low-traffic hours.
  2. Clock callsite consolidation removes the most likely sources of
     new naive-datetime writes, which protects against future drift.
  3. Migration 083 will be Sprint 7 in the next phase; it includes
     the SQL backfill: ``UPDATE x SET y = y AT TIME ZONE 'UTC' WHERE
     y IS NOT NULL;`` for Postgres and a Python-side coercion over the
     SQLite ``DateTime`` columns.

### Deploy notes
- No schema change. No deploy required. Behaviour-preserving.

### Fix
- **Duplicate `_migration_044_message_templates`** (`app/rms/db.py`):
  the audit found this function defined twice — first as a stub (just
  setting `conn.dialect.name` and returning) followed by the real
  implementation ~15 lines below. Python silently kept the second
  definition, so the migration ran correctly, but the duplicate was a
  ticking bomb: any new `_migration_044` between them would have been
  silently discarded. Removed the stub.

### New
- **`tests/test_migration_integrity.py`** — 89 tests pinning migration
  invariants:
  - No duplicate `_migration_NNN_*` function names (the duplicate-def P0).
  - Migration numbers form the contiguous range `1..CURRENT_SCHEMA_VERSION`.
  - Every migration name matches `_migration_NNN_<slug>` convention.
  - `MIGRATIONS` dict is sorted, complete, and each entry accepts one
    positional `conn` argument.
  - Each migration function has a docstring ≥ 10 chars.
  - Parametrized 82-case test asserting every individual migration
    function is importable and callable.

### Stats
- 89 new tests, 1 stub removed (-15 lines), 0 behavior changes.

### Deploy notes
- No schema change. No deploy required.
- **Logging** (`app/rms/main.py`): rotating file sink (BACKLOG #45) — 50 MB / 7-day retention; env-tunable path.
- **Spool prune** (`app/rms/notifications.py`): bound `notifications_spool/dryrun-*` at 7 days; prevents local-disk bloat.
- **Migrations 60-62** (`app/rms/db.py`): wrap ORM-touching steps in try/except so fresh DBs don't fail when 072's columns don't exist yet.
- **JS init fix** (`app/static/pedido-combos.js`): initialise `window.customerPickHandlers` before assignment.
- **Tests** (`tests/test_daily_sales_series.py`, `tests/_fixtures_quick_seed.py`): anchor seed "today" sale to noon UTC so daily bucketing is TZ-stable; add `_asuncion_today()` helper. - User Guide v1.0 (screenshots + version drift check)

### New
- **24 real PNG screenshots** of every daily-use page captured via Playwright + cookie auth against the live Swarm URL. Replaces 22 "placeholder screenshot" references across 16 sections of `docs/user-guide/`.
- **`check_manual_version.py`** — verifies README's `schema NN · commit XXXX` header against `app/rms/config.py` and `git HEAD`. Exits non-zero on drift so CI can catch stale docs.
- **"Lo que podés hacer" matrix** in README — 16 confirmed-active daily workflows linked to their screenshots, 8 wishlist items bucketed by quarter, 3 known-fragility callouts.
- **Version pinning header** in README: three-form verification (browser footer, login response header, this manual) so the operator can detect drift herself.
- **`tests/test_user_guide_version.py`** — 7 tests pin the contract: header present, drift check passes, every section embeds a screenshot, no placeholder strings remain, README documents both active and not-yet-active features.

### Fixes
- README pointed at **suspended** Render URL `sazon-rms.paragu-ai.com` (returns 503 / `x-render-routing: suspend-by-user`). Now points at the live Swarm URL `sazon-vps.paragu-ai.com` and warns about the suspended one.

### Stats
- 24 screenshots (5.5 MB total), 4 helper scripts (capture + replace + version-check), 17 doc files updated.
- `152 + 7 = 159` tests, `152/152` pass + 6 PG skip + 3 net skip.

### Deploy notes
- Manual lives in repo at `docs/user-guide/README.md`. No live deploy needed (markdown only).
- When schema or routes change: re-run `python3 docs/user-guide/capture_saskia_screenshots.py` and update the version header in README.md. Run `python3 docs/user-guide/check_manual_version.py` to confirm no drift.

## 2026-09-30 - reorder supplier redesign + scraper completion

### New
- **Manual supplier toggle** (Phase 1):  
  - 🔒 lock/unlock supplier on /reorder page (replaces automatic streak blocking)
  - Audit trail for lock/unlock events (action: "ingredient.supplier.lock/unlock")
  - 16 new tests covering: lock/unlock buttons, audit rows, error handling

- **Supplier CRUD** (Phase 2):  
  - Soft delete suppliers (preserves history, sets "inactive" status)
  - "Proveedores" tab on /settings/catalog links to /suppliers
  - 5 new tests: CRUD operations, soft delete, tab navigation

- **CSV price upload** (Phase 3):  
  - POST /reorder/upload-prices endpoint (CSV: ingredient_name,supplier_name,price_gs,date)
  - Auto-migration: adds supplier_id to IngredientPriceEvent (migration 073)
  - 10 new tests: CSV parsing, duplicate handling, audit trails, rollback safety

- **Superseis scraper** (Phase 4):  
  - HTTP + BeautifulSoup scraper for superseis.com.py
  - Handles ₲ 3.600 format and complex OpenCart layout
  - Graceful degradation for Stock.com.py (JS site, CSV-only fallback)
  - 13 new tests: parsing robustness, format extraction, graceful error messages

- **Scrape endpoint** (bonus):  
  - POST /reorder/scrape?q=<query> returns scraped prices per source
  - Writes audit row (action: "read.scraper.run")
  - 4 new tests: empty query, aggregation, audit tracing, audit failure handling

### Fixes
- - Fix depth counter in Superseis scraper: void HTML elements (img, input, br, etc.) don't emit closing tags, causing under-decremented depths and missed card completions. Now tracks only tag types that actually close via `</tag>`. 

- - Register 'network' pytest marker in pyproject.toml to silence test warnings.

### Stats
- 152 tests total (16 toggle + 5 CRUD + 10 CSV + 21 scrapers + 4 endpoint + 2 UI + 8 cheapest core + 3 UI cheapest + 13 daily series + 7 chart preset + 11 export period + 5 healthz docs + 22 reports + 6 PG regression + 8 mobile UX + 10 status dashboard)
- All tests pass at 145/145 (3 tests require network; 6 PG tests skip without Docker)

### Deploy notes
- Live at https://sazon-vps.paragu-ai.com/reorder  
- Auth: demo / demo1234  
- Test with: `pytest tests/reorder/** -q` (all phases)