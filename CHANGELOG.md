## 2026-10-07f — Sprint 2.1 COMPLETE: settings consolidation (AppMeta → settings_kv)

**The dual-persistence trap is closed.** One settings store: `settings_kv` (JSON, via settings_runtime).

- **`app/rms/settings_registry.py` (new)**: the 42-key Setting/SettingGroup/VALIDATORS registry moved verbatim from the deleted `app/rms/settings.py`, API re-backed onto SettingsKV with the old call signatures preserved (`get_setting_value`, `set_setting`, `list_settings`, `settings_by_group`, `reset_setting_to_default`).
- **Deleted**: `app/rms/settings.py` (538 lines) + `app/rms/settings_original.py` (411 lines). `settings.py` had exactly ONE production importer (production_demand.py lazy import) — re-pointed.
- **Migration 114** (`_114_settings_kv_consolidation.py`): copies operator-customized values from AppMeta (42 registry keys + legacy /settings router keys: business_*, theme, timbrado, punto_expedicion, invoice_sequence) into settings_kv, then deletes the copied rows. KV-wins on conflict (idempotent), empty values skipped, non-settings AppMeta rows (eod markers, backup stamps, seed flags) untouched. SCHEMA_VERSION → 114.
- **Tests**: 4 new migration tests (fresh-init to 114, copy+delete, idempotent+KV-wins, empty-skip); test_settings.py re-seeded via SettingsKV; the 2 Sprint 2.1 strict-xfails in test_settings_kv_canonical flipped to plain green (the invariant tests now pass for real). File-scan made worktree-relative (hardcoded /opt/data/work path would have scanned the wrong tree) with self-exclusion.
- **Sibling coordination**: rebased onto 387d11ca + 51a880d2 (SASKIA-301..308 + ruff waves); sibling's new test_SASKIA-308_settings_eod_auditoria.py passes against the consolidation. My worktree's .venv symlink was transitively broken by a self-referencing loop in the shared checkout's .venv — rebuilt locally with uv sync --frozen.

**Sweep**: 77 passed across settings + migration-safety + SASKIA-308 locks.

## 2026-10-07e — SASKIA-301: copy/UX hardening Phase 0 (globals)

**Goal:** fix the 8 categories of copy/UX drift identified in
`docs/ux/copy-fix-list.md` (the audit of 110 templates + the
reuse-abstraction audit) that apply globally across the app.

**Shipped in this commit:**

- **Currency symbol drift (G.1)** — `₲` and bare `Gs` → canonical `Gs. 729.167`
  per `app/docs/copy-vos.md`. 4 templates: `eod_print.html` (2 spots),
  `ops_status.html`, `reportes_mermas_cost.html`, `suppliers_volatility.html`.
- **English band label (G.2)** — `>Loyalty<` → `>Fidelización<` in
  `inicio.html` line 87.
- **English loan words (G.3)** — 18 replacements across 15 templates:
  `COGS` → `Costo de Mercadería Vendida`, `Revenue` → `Ingresos`,
  `Batches` → `Tandas`, `Forecast` → `Pronóstico`, `Endpoint` → `Ruta`,
  `Counterparty` → `Contraparte`, `Reorder rate` → `Tasa de reposición`,
  `Lead time` → `Tiempo de reposición`, `Login OK/FAIL` → `Login exitoso/fallido`,
  `Δ Margen/Δ Gs./Δ Precio` → `Cambio (...)`, `KPIs en vivo` → `Indicadores en vivo`,
  `Owner` → `Responsable`, `Status` → `Estado`, `Prob.` → `Probabilidad`,
  `Unit Gs.` → `Unitario (Gs.)`, `Qty` → `Cant.`, `Severidad (Gs.)` instead of
  `Sev Gs.`. English tooltip `Set every row...` → `Marcá todas...` in produccion.html.
- **Register consistency (G.4)** — `Guardá` → `Guardar` in 11 button locations
  across 9 templates (form submit buttons + aria-labels). `Decí por qué`
  → `Indicá por qué` in produccion.html.
- **Severity pill (G.7)** — `sev-pill saludable` → `sev-pill ok` in inicio.html
  (canonical set: OK / Aviso / Crítico).
- **Column header / placeholder (G.6+G.8)** — `(Gs)` → `(Gs.)` in
  menu_import_ocr.html; placeholder `25000` → `25.000` in menus.html.
- **Tooltip rationale (G.5)** — no change (locked): all 8 `aria-label="Cerrar"`
  buttons have SVG X icon as visible content; the aria-label is the correct
  accessible name.

**Tests:** 6 new test files, 33 tests, all pass in 20s:
- `tests/test_SASKIA-301_currency_gs.py` (5)
- `tests/test_SASKIA-301_loan_words.py` (15+)
- `tests/test_SASKIA-301_register.py` (3)
- `tests/test_SASKIA-301_severity.py` (2)
- `tests/test_SASKIA-301_columns.py` (2)
- `tests/test_SASKIA-301_tooltips.py` (2)

All marked `pytest.mark.smoke` so they run on every commit via pre-commit.

**Decisions (D1-D8)** documented in `docs/ux/copy-ux-decisions.md`:
- D1: `copy-vos.md` is wrong (`Guardá` is Argentine, not Paraguayan for buttons);
  canonical is infinitive for buttons, vose-conjugated for prose. The style
  guide fix happens in SASKIA-310 (Phase 9).
- D2: actual scope larger than original estimate (11 Guardá buttons, not 2-3;
  3 Loyalty templates, not 1; 4 ₲ templates, confirmed).
- D3: Phase 8 shrinks (500.html is already safe; the security check becomes
  a regression test rather than a fix).
- D4-D5: worktree + sibling recovery (SASKIA-207 was uncommitted on main;
  this commit includes the recovery merge via the chain SASKIA-207 → SASKIA-301).
- D6-D8: test naming, no Phase 0 migrations, glossary in Phase 9.

**Regression:** SASKIA-205/206/207 (62 tests) still pass; ruff clean on the
new test files.

Refs: `docs/ux/copy-fix-list.md`, `docs/ux/copy-ux-decisions.md`,
`.hermes/plans/2026-10-07_202522-copy-ux-hardening.md`.
## 2026-10-07e — SASKIA-208: Poisson weekday restocking forecast (BACKLOG #5)

**Model** (`app/rms/restock_forecast.py`, zero new deps per AGENTS.md rule 26):
- Per-weekday Poisson rates, closed-form MLE λ̂_w = Σcount/Σexposure over a 56-day window (Sat/Sun bakery peaks a flat 30-day average misses — the exact gap that made "12 days of stock" actually 8).
- Two stockout paths: P50 (expected) and P95 (conservative, λ+1.645σ accumulated) — operators plan against P95.
- Confidence labels key on OBSERVED movement days (28+/10+ cutoffs), not window exposure.
- recommended qty covers 14 days on the P95 path with the 2×-min floor kept from forecast.py.

**Bugs caught by tests during build**: SQLite %w (0=Sunday) vs date.weekday() (0=Monday) key mismatch silently misassigned every weekday; exact-now cutoff dropped the window's first day by seconds (biased one weekday 1/N low); the P50 walk mutated the reported stock.

**Wired**: /reorder gains `restock_map` (P95 date, days-to-P95, weekend uplift, confidence); template shows a `P95 Nd` badge only when the conservative path lands ≥2 days before the flat estimate (that gap IS the weekend risk).

**Tests**: 13 new (10 model math + 3 batch/integration); reorder regression 31 passed.
## 2026-10-07d — SASKIA-207: stock_ledger helper + reuse/abstraction audit

**Audit:** docs/operations/2026-10-07-saskia-reuse-abstraction-audit.md (8 findings, measured).

**Shipped:**
- `app/rms/stock_ledger.py`: `apply_stock_delta()` (bump + StockMovement row, caller commits) + `qty_to_stock_unit()` (explicit on_mismatch policy: 'raw' lands unconverted, 'raise' errors). Replaces 3 divergent copy-paste blocks: shopping mark-purchased (raw), wishlist mark-purchased, waste.py record_waste + record_recipe_waste (raise→400). Sale path stays in costing.apply_sale per AGENTS.md rule 8.
- 12 contract tests in tests/test_SASKIA-207_stock_ledger.py (incl. DB floor surfacing IntegrityError, no-hidden-commit).
- Clock discipline: pedidos.py 5 today sites → clock.today_local(); generated seed files (packs.py) exempted in test_clock_discipline with generator-fix rationale. 10/10 (2 were failing on main).
- Deprecation headers on models/procurement.py, models/herbus_drive.py, models/catalogs_restored.py (0 importers, runtime classes live in models_legacy.py — the SASKIA-206 trap).

**Regression:** 62 passed across SASKIA-205/206/207, waste, herbus, P20, clock. 5 remaining failures verified pre-existing on main (stash baseline) — settings_kv_canonical x3 noted in audit.

## 2026-10-07c — SASKIA-205 + SASKIA-206: purchase→inventory + price snapshots

**Goal:** close two shopping-flow gaps — purchases that never landed in inventory, and list rows that showed today's price instead of the quoted one.

- **SASKIA-205** (`741a149a`): `POST /shopping-list/{id}/mark-purchased` now converts `qty_to_buy` to the ingredient's stock unit (`app.rms.units.convert_qty`), bumps `stock_qty`, and writes `StockMovement(movement_type='reorder')`. `POST /wishlist/{id}/mark-purchased` creates/updates the `[EQUIPMENT]` pseudo-ingredient the same way. Idempotent (False→True only); `/unmark` doesn't subtract stock.
- **SASKIA-206** (this commit): migration 113 adds `shopping_list_item.unit_price_snapshot_gs`. All 4 row-creation paths (from-plan, sync-low-stock, manual add, save-plan) freeze `purchase_price_gs` at creation via `_price_snapshot()`. Template + totals prefer the snapshot; pre-113 rows (NULL) fall back to live price.
- Migration 113 bump is INSIDE the function (each migration owns its bump — see pitfalls skill).
- Tests: 3 snapshot tests (freeze-despite-price-change, no-price→NULL, helper contract); 34+ passed across shopping/wishlist/herbus suites; fresh-DB init reaches v113.

## 2026-10-07 — SASKIA-204: Sale channel mismatch cleanup

**Goal:** fix the silent skew where 9 of 346 sales were being collapsed to `mostrador` by the import fallback at `scripts/import_herebus_data.py:622`, surface the 4 HEREBUS channels (retail/wholesale/distributor/eventual) in revenue reports, and add a channel filter to /ventas/historial.

- `app/rms/migrations/_112_extended_channel_check.py` (NEW): SQLite DROP TRIGGER + CREATE TRIGGER pattern extending the CHECK constraint on `sale.channel` from 6 to 10 values. Mirrors `Channel.allowed_values()` — the test `test_channel_enum_and_migration_have_same_allowed_set` enforces this alignment.
- `app/rms/models/channels.py`: extended `Channel` enum with `RETAIL/WHOLESALE/DISTRIBUTOR/EVENTUAL`; updated `display_order()` to keep front-of-house first.
- `app/rms/models_legacy.py`: extended Postgres `CheckConstraint` on `sale.channel` and `pedido.channel` to match.
- `app/rms/db.py:_migration_041_channel_catalog`: seed the 4 new channels in the `channel` table.
- `app/rms/config.py`: `SCHEMA_VERSION` bumped to 112.
- `app/routers/sales.py`: `sales_history` and `sales_export_csv` accept `channel` query param; the same channel filter is applied to `sales_q`, `count_q`, and `totals_q` (must match all three or pagination is wrong). `_build_filtered_sales_query` extended for the export path. Channel values not in `Channel.allowed_values()` fall back to `None` so typos don't 500 the page.
- `app/templates/ventas_historial.html`: channel combo_field in the filter form, auto-submitting on change. Pagination links preserve the channel param.
- `scripts/reclassify_sale_channels.py` (NEW): idempotent backfill that reads the VENTAS export CSV and `UPDATE`s `sale.channel` where the canonical value differs. Idempotency key is `(sold_at ± 1s, qty)` (the 1s window handles the SQLAlchemy/Python microsecond format mismatch with SQLite's text storage of datetimes). Always dry-run first (`--apply` to actually run).
- `scripts/import_herebus_data.py`: now uses the same `_normalize_channel()` helper so future imports don't reintroduce the silent-skew bug.
- `tests/test_reclassify_sale_channels.py` (NEW): 28 tests covering both `_normalize_channel` and `reclassify()` end-to-end (parametrized over 24 raw→canonical mappings + dry-run + actual-update paths).
- `tests/test_sales_history_filter.py`: `test_channel_filter` rewritten to count `<td>` cells instead of substring match (since the page now contains channel labels in the filter UI).
- `tests/test_P42_channel_enum_integration.py`: `test_channel_enum_and_migration_have_same_allowed_set` now checks against the LATEST migration's `_ALLOWED_CHANNELS` (not hardcoded to migration 111).
- `tests/test_sale_channel.py`: `test_all_five_channels_accepted_by_apply_sale` extended from 5 to 10 channels (SASKIA-204 name change).
- `pyproject.toml`-side: `uv sync` was run to remove a stale `_editable_impl_aiw_saskia_rms.pth` pointing at `/tmp/baseline-6ffe16d3` (an Oct 5 snapshot) that was shadowing the real `app/` package — every Python invocation under the project's `uv run` had been importing the OLD baseline's `app.rms.config` (where `CURRENT_SCHEMA_VERSION` was still 102), so migration 112 appeared to be missing from the runtime `MIGRATIONS` dict. The 43 channel tests + 28 reclassify tests + 13 sales-history tests now pass against the real package.
- Total: 84 channel/reclassify tests + 13 sales-history tests = 84+13 = 97 passing tests across the SASKIA-204 ticket.

# CHANGELOG

## 2026-10-06b — Demos vivos por industria + onboarding 1 comando + importador carta

**Goal:** pasar de "te mando un PDF" a "entrá y mirá": 3 demos VPS (Pizzería/Café/Panadería) con vida demo pack-native, `onboard_tenant()` para altas en 1 llamada, e importador de carta real para el primer día de un cliente.

- `app/rms/seed/pack_demo.py`: `reseed_pack()` wipe via sqlite_master (todas las tablas, FK-safe sobre DB sucia) en conexión AUTOCOMMIT dedicada; CLI `--pack` acepta ASCII (`pizzeria`/`cafe`); env `AIW_DEMO_PACK` para stack auto-seed path.
- `app/rms/seed/onboard.py` (NEW): `onboard_tenant(session, name, pack=...)` — tenant + admin + pack + 90 días demo; idempotente (mismo nombre → mismo tenant).
- `app/rms/seed/menu_import.py` (NEW): importador carta-real CSV → match difuso (≥0.82, sin acentos) contra pack; matched → precio real del cliente; faltantes → producto nuevo tag `importado (pendiente recosteo)` (no inventa recetas); `dry_run=True` por defecto.
- Tests: `tests/test_pack_demo.py` + `tests/test_onboard.py` + `tests/test_menu_import.py` = 14 nuevos, 14/14.
- Deploy demos VPS: `scratch/deploy_demos_v5.sh` — 3 stacks swarm (`sazon-demo-{pizzeria,cafe,panaderia}`), imagen tagueada por timestamp (rollout garantizado), volumen + DB por demo, `HTTPS_ONLY=false` (solo demos; prod intacto), reseed FK-safe post-boot. Puertos 8081/8082/8083; login admin/cambiar1234.

## 2026-10-06 — Seed packs per market segment (pre-carga onboarding)

**Goal:** every prospect segment seeds in one call with La-Vaquita-grade data (products → recipes → ingredients with ref costs). Staged from market research; nothing loads automatically.

- `app/rms/seed/packs.py` (GENERATED — do not hand-edit): 10 packs — Panadería 22 · Pastelería/Confitería 16 · Pizzería 18 · Hamburguesería/Rápida 15 · Parrilla/Restaurante 23 · Comedor/Kilo 14 · Heladería 15 · Café/Cafetería 15 · Empanadas/Criolla 10 · Oriental 13 = 161 productos / 161 recetas / 779 recipe lines / 257 ingredientes únicos con costo ref Gs + variantes + price events, 4 suppliers, payment methods, channels, 2 delivery zones, weekly production templates, tags. Uso: `seed_pack(session, "Pizzería")` — idempotente, mismos patrones que `seed/sazon.py`.
- `scripts/seed_packs_gen.py`: regenera packs.py desde los CSV de investigación stageados (scratch/sazon_pack_*.csv + sazon_ingredientes_maestro.csv); auto-ruff-fix al generar.
- `tests/test_packs_seed.py`: 7 tests — integridad (producto→receta, qty>0), seed completo, idempotencia, barrido 10 packs en DB fresca, pack desconocido raise, reuso de ingredientes entre packs.
- `pyproject.toml`: per-file-ignore DTZ para el generado (contrato naive-UTC heredado de sazon.py).
- `app/rms/seed/pack_demo.py` + `tests/test_pack_demo.py` (5 tests): vida demo nativa del pack —
  clientes + pedidos con token público + 90 días de ventas con skew fin de semana/quincena + stock
  moves. CLI: `python -m app.rms.seed.pack_demo --pack "Pizzería"` re-seedea el demo en segundos
  (`reseed_pack`, wipe de data only). Tests: 5 passed; ruff clean.


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
## 2026-10-07f — SASKIA-302: login + inicio + prod-manana (Phase 1)

**Goal:** fix the 7 P0/P1 copy/UX bugs on login and home, plus the
duplicate H2 in produccion_manana.html (a 1-line P0 bug promoted from
Phase 4 because it's a screen-reader / nav ordering issue).

**Shipped:**

- **LOGIN.1 (P0)** — removed duplicate `stay_logged_in` checkbox from
  `app/templates/login.html`. The remaining `Recordar este dispositivo`
  is the one to keep (works with FastAPI's standard remember-me).
- **LOGIN.2** — translated a11y statement "Sazón strives to conform to
  WCAG 2.1 Level AA." → "Sazón apunta a cumplir con WCAG 2.1 Nivel AA."
- **INICIO.1** — KPI card label `Operaciones` → `Ventas` (the card counts
  sales, not ops).
- **INICIO.5** — split the `Acciones del día` card into 2:
  `Acciones del día` (actionable) and `Hecho hoy` (informational,
  contains the `Merma del día` row). The "Todo en orden" empty-state
  stays in the actions card.
- **INICIO.6** — forecast empty state already has `Sin plan todavía`
  with a `/produccion` hint; locked with a regression test.
- **INICIO.17** — loyalty sub-text format `5 de 12 ventas` →
  `12 ventas · 5 con cliente` (more scannable).
- **PROD.11 (P0, promoted)** — removed duplicate `<h2>🧾 Pedidos para mañana</h2>`
  in `app/templates/produccion_manana.html`. The `<summary>` inside the
  `<details>` is now the canonical heading (the H2 was redundant and
  also broke the `<details>` semantics).

**Tests:** 2 new test files, 7 tests, all pass in 7s:
- `tests/test_SASKIA-302_login.py` (2)
- `tests/test_SASKIA-302_inicio.py` (5, includes the prod-manana regression)

**Regression:** SASKIA-301 (33) + inicio frequent-customer card all pass;
ruff clean on new tests.

Refs: `docs/ux/copy-fix-list.md` (G.1-G.8, LOGIN.1-4, INICIO.1-17,
PROD.11), `docs/ux/copy-ux-decisions.md` (D9: prod-manana promoted to
Phase 1 because the duplicate H2 is a screen-reader bug, not just visual).

## 2026-10-07g — SASKIA-303: POS regression locks (Phase 2)

**Audit result:** the POS templates (`pedidos_nuevo.html`,
`pedido_detalle.html`, `pedido_board.html`, `pedido_publico.html`,
`pedido_stock_preview.html`) are already well-written. The 4 issues
listed in `docs/ux/copy-fix-list.md` under POS.* are all already
addressed in earlier work (Phase 13/14 ventana_text with `no es
garantía` suffix, kanban redesign, etc.).

**No code changes** — only regression tests to lock the good state.

**Tests:** 1 new test file, 10 tests, all pass in 7s:
- `tests/test_SASKIA-303_pos.py` (10) — locks placeholder hints,
  status pill coverage, kanban column labels, public-page total
  wording, ventana_text rendering, and stock preview table.

**Lesson:** sometimes the highest-value deliverable is a regression
test that says "this is already good, don't break it in a future
refactor". Future POS work can now build on a tested foundation.

## 2026-10-07h — SASKIA-304: clientes + productos + recetas (Phase 3)

**Shipped:**

- **CLI.3** — added `+595 9XX XXXXX` placeholder to `cliente_editar.html`
  phone input (was missing; users typed without format guidance).
- **PROD.1 (P0)** — removed duplicate `Importar CSV` button in
  `productos.html` (lines 27 and 33 were both rendering the same link;
  kept the primary Importar on `/productos/importar` flow).
- **RECETA.1 (P1)** — replaced the bogus margin pill in
  `receta_detalle.html`. The old formula
  `100 * (1 - unit_cost / (unit_cost / 0.65))` always computed exactly
  35% — a literal placeholder. The new pill says
  `Costo: Gs. X/u` (always honest). The full margin calculation
  requires recipe → product sale_price wiring (Phase 6.5).

**Tests:** 1 new file, 11 tests, all pass in 9s:
- `tests/test_SASKIA-304_clientes_productos.py` (11) — covers clientes
  nudge banner, phone placeholder, lifetime spend, duplicate button
  removal, producto form placeholders, filter toolbar, receta margin
  pill honesty, recetas difficulty multi-select, receta_form
  effective-ingredients panel, cliente inline form, producto_detalle.

**Decisions:**
- D9: cliente_detalle's 30d-spend indicator is out of scope for
  copy-only work (would need a router change to add `spend_30d_gs`
  to the context). The 30d window already appears in
  `pedido_detalle.html` (the cross-customer view). The ficha view
  shows lifetime spend which is the most relevant metric for that page.
- D10: removed the always-35% margin pill rather than try to fix
  the formula in place. Better to show a real, honest number
  (Costo: Gs. X/u) than a confident-looking lie.

**Regression:** SASKIA-301/302/303 (52 tests) still pass; ruff clean.

## 2026-10-07i — SASKIA-305: inventario + producción (Phase 4)

**Audit result:** the inventario + producción template family
(inventario, inventario_detalle, inventario_form, inventario_movimientos,
inventario_auditoria_etiquetas, produccion, produccion_manana,
produccion_prep, produccion_accuracy, produccion_haccp, produccion_print)
is already well-built. The main Phase 4 fix (PROD.11 — duplicate
<h2>Pedidos para mañana</h2> in produccion_manana.html) was promoted
to Phase 1 and shipped in d2164de8.

**No code changes** — only regression tests to lock the good state.

**Tests:** 1 new file, 14 tests, all pass in 12s:
- `tests/test_SASKIA-305_inventario_produccion.py` (14) — locks
  bulk-fill modal, filter toolbar (categoria/estado/alergeno/diet),
  low-stock alerts, empty state, view tabs, template-load button,
  shift badge, HACCP/accuracy/prep page existence, horneado-extra
  ad-hoc section, movimientos/auditoria page existence.

## 2026-10-07j — SASKIA-306: pedidos + proveedores + menus (Phase 5)

**Audit result:** pedidos (already covered in SASKIA-303), proveedores,
and menus templates are well-built. No copy/UX fixes required.

**No code changes** — only regression tests to lock the good state.

**Tests:** 1 new file, 12 tests, all pass in 8s:
- `tests/test_SASKIA-306_pedidos_proveedores_menus.py` (12) — locks
  supplier table+CTA, supplier form fields, volatility Gs. symbol
  (regression for Phase 0), OCR missing-key callout, menu price
  placeholder (25.000), pedido_detalle loyalty card + ventana_text
  rendering, page existence for supplier_precios / supplier_orders /
  menu_publico / menu_tablet.

## 2026-10-07k — SASKIA-307: reportes + insights + dashboard (Phase 6)

**Audit result:** reportes + insights + dashboard templates are
well-built. Food cost % is already implemented at the global level
in dashboard.html (line 131, `food_cost_pct` with `objetivo: 35%`
target) and analisis.html (line 60, semáforo + 30d Panorama KPI).

The plan's Phase 6.5 ("settings field for CMV target") is moot —
the value comes from `insights.food_cost` at runtime, no operator-
editable target needed for the simple ≤35% target_direction='low'
framing. Per-product food_cost_pct is already rendered in
insight_price_impact.html.

**No code changes** — only regression tests to lock the good state
and the Phase 0/3 currency + label fixes.

**Tests:** 1 new file, 16 tests, all pass in 12s:
- `tests/test_SASKIA-307_reportes_insights_dashboard.py` (16) — locks
  food cost semáforo, 30d food cost KPI, stars/dogs/rising/churning,
  dashboard food cost + 35% target, dashboard currency, dashboard
  'Indicadores' label, reportes_diario Spanish COGS, currency
  regression on reportes_diario / reportes_mermas_cost / insight_margenes
  / benchmarks, reportes_top_productos Spanish 'Ingresos',
  insight_price_impact per-product food_cost_pct, page existence for
  libro_ventas / retencion / iva.

## 2026-10-07l — SASKIA-308: settings + EOD + auditoria + ops (Phase 7)

**Audit result:** all settings + EOD + auditoria + ops templates are
well-built. The settings.html has a 6-tab structure (business,
payments, notifications, fiscal, theme, demo) with CSRF on every
form. EOD pages use skeleton JS for the print view. Auditoria has
two pages: list (`/auditoria`) and analytics (`/auditoria/analytics`).

**No code changes** — only regression tests to lock the good state.

**Tests:** 1 new file, 12 tests, all pass in 11s:
- `tests/test_SASKIA-308_settings_eod_auditoria.py` (12) — locks the
  6 settings tabs, Paraguay SET fiscal fields, CSRF on every form,
  eod_print currency regression, checklist format, eod_anomalies
  page existence, auditoria filter bar, login success/fail labels
  (Phase 0 fix), ops_status endpoint table + reorder rate heading,
  settings_catalog 12 tabs.

  settings_catalog 12 tabs.

## 2026-10-07m — SASKIA-301..308 follow-up: D3 currency drift fixes

CI's `currency-drift` job caught 3 raw `Gs. {{` literals our Phase 0/3
passes missed. Replaced with the shared `m.gs` / `m.gs_full` macros
(AGENTS.md rule #4 + D3 lint).

**Files fixed:**
- `app/templates/eod_print.html` (2 places): reorder summary line +
  reorder item cost cell
- `app/templates/receta_detalle.html` (1 place): SASKIA-304's honest
  cost pill used the old raw-format pattern

**Tests updated:**
- `tests/test_SASKIA-304_clientes_productos.py::test_receta_detalle_margin_pill_honest`
- `tests/test_SASKIA-308_settings_eod_auditoria.py::test_eod_print_currency_fixed`

Both now assert: bug formula gone, `m.gs` macro used, and NO raw
`Gs. {{` pattern (D3 lint via inline regex).
