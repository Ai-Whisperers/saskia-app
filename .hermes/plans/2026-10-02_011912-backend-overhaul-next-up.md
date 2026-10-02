# Saskia RMS — Backend Overhaul Next-Up Plan (2026-10-02)

> **For Hermes:** This plan picks up after Sprint 3.1+3.2+2.4 + the EOD closed-pill work. Ivan said "continue with the nexts" — this picks the next valuable items from the live `IMPROVEMENT_BACKLOG.md`.

**Goal:** Knock out the highest-leverage remaining BACKLOG items with test coverage, one commit per task, all on `eng/2026-10-02-backend-overhaul`.

**Architecture:** Continue the existing pattern — surgical service-level changes with new tests in `tests/test_*.py`, schema changes via migration `app/rms/migrations/_NNN_*.py`, model changes via `app/rms/models_legacy.py` (or a focused submodule), and router/service split via `app/rms/services/`.

**Tech Stack:** FastAPI + SQLAlchemy 2.x + SQLite/Postgres; pytest + httpx for tests; Jinja2 templates; existing helpers (`to_int_gs`, `Decimal`, `compute_reorder_list`, etc.).

---

## Current state (where we are now)

- Branch: `eng/2026-10-02-backend-overhaul` at `a665709`
- Schema v=88; 193 sprint tests passing; 49 EOD tests passing
- Sprints 3.1+3.2+2.4 landed (MonthlyClosure, soft-delete/audit columns, integrations+seed split)
- BACKLOG refresh: marked #3, #14, #21, #24 complete; #15 partial; #4 helper re-imported
- atomic_ddl_block helper restored at `app/rms/db.py:4073`; not yet applied to all 83 migrations
- Pre-existing failures: `tests/browser/test_flows_browser.py::test_combo_component_opens_and_picks` (Phase 14 Batch C — out of scope)

## Items remaining in the BACKLOG (after this turn's updates)

| # | Item | Effort | Why it's worth doing |
|---|---|---|---|
| 16 | `/ventas/{id}` standalone HTML view | S | Tiny isolated route + template; real operator win |
| 19 | `RecipeLine.qty` Float → Numeric | S | Quick win; isolated migration; safer Decimal math downstream |
| 17 | Customer-facing share of recibo `/p/{token}` | M | Broken per audit; risk of customer-experience regressions |
| 4 | Convert 83 migrations to `atomic_ddl_block` | S (per migration, M total) | Multi-session refactor; helper exists |
| 13 | Waste deducts stock but doesn't update avg cost | M | Real cost leak — needs the "moving average" concept formalized |
| 15 | DB-level lock on closed days for all writes (not just void_sale) | M | Real correctness — second half of BACKLOG #15 |
| 26-36 | Analytics dashboards (sale_stock_move, waste ROI, plan accuracy, etc.) | M-L each | High operator value but data/feature work |
| 37-40 | Supabase / Render / R2 infra | M-L each | Vendor work; out of scope for backend overhaul |
| 1 | Consolidate `sale_stock_move` + `stock_movement` | M | High-traffic refactor; risky; defer to dedicated refactor session |
| 12 | Forward-only migrations rollback | L | Architectural; defer |

## Recommended execution order (this plan covers Sprint 4.x — see "Out of scope" below)

### Sprint 4.1 — BACKLOG #16: `/ventas/{id}` standalone view

**Why first:** S effort, isolated change, high operator value (they have to click recibo currently and can't link to a sale by URL). Self-contained route + template + test.

**Files:**
- Modify: `app/routers/sales.py` (add `GET /ventas/{sale_id}` handler — read the existing one at `/recibo` for the right join shape)
- Modify: `app/templates/ventas_detalle.html` (new — copy from recibo.html, trim recibo-only bits)
- Modify: `app/rms/main.py` (template includes if applicable — most likely already imported via `template_render`)
- Test: `tests/test_ventas_detalle_view.py` (new)

**Step 1: Failing test** — assert `GET /ventas/{id}` returns 200 with the sale's items + customer info + payment breakdown.

**Step 2: Implement route** — replicate `/recibo` data-loading but with `sale_id` URL param instead of `public_token`.

**Step 3: Template** — render `sale.lines`, `customer`, `payments`, `total_gs`, discount, void indicator.

**Step 4: Test pass** + commit.

**Verification:** `pytest tests/test_ventas_detalle_view.py -v` → 3 passed.

---

### Sprint 4.2 — BACKLOG #19: `RecipeLine.qty` Float → Numeric

**Why second:** S effort but data-risky. Do it in isolation so we can revert if migrations fail.

**Files:**
- Modify: `app/rms/models_legacy.py:324` — change `qty: Mapped[float] = mapped_column(Float, nullable=False)` → `Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)`
- Create: `app/rms/migrations/_089_recipe_line_qty_numeric.py` — Postgres-side `ALTER COLUMN recipe_line.qty TYPE NUMERIC(12,4)` if not already; SQLite stores as NUMERIC affinity already
- Modify: `app/rms/db.py` — register `89: _migration_089_recipe_line_qty_numeric`; bump `CURRENT_SCHEMA_VERSION` → 89
- Modify: `app/rms/config.py` — bump `CURRENT_SCHEMA_VERSION = 89`
- Test: `tests/test_recipe_line_qty_numeric.py` (new) — verify insert/read/decimal math roundtrip

**Step 1: Migration scaffold + register** — empty migration that only registers; SQLAlchemy will rewrite CREATE TABLE for new installs.

**Step 2: Model change** — switch to `Numeric(12, 4)`.

**Step 3: Backfill for existing installs** — Postgres-side ALTER COLUMN if running against live DB.

**Step 4: Tests** — roundtrip with `Decimal("0.250")`, math with `Decimal`, ensure no float32 truncation.

**Verification:** `pytest tests/test_recipe_line_qty_numeric.py tests/test_units.py -v` → all pass; schema version = 89.

---

### Sprint 4.3 — BACKLOG #15 (second half): DB-level closed-day gate

**Why third:** M effort; the data-layer enforcement already exists for `void_sale` — extend it to the rest of the accounting-sensitive writes.

**Files:**
- Modify: `app/rms/eod_closed.py` — add `assert_day_open_or_raise(session, day, action_name)` helper
- Modify: `app/rms/costing.py` — switch `void_sale` to use the new helper (drops the duplicate logic)
- Modify: `app/routers/sales.py`, `app/routers/reorder.py`, `app/routers/inventory.py` — call the helper before any accounting write on a closed day

**Step 1: Failing test** — `test_void_sale_on_closed_day_raises` (already exists from the original closed-day work); add 3 more for sale insert/update, merma insert, inventory adjustment.

**Step 2: Helper** — `assert_day_open_or_raise(session, day, action)` checks `eod_is_day_closed` and raises `EODClosedError`.

**Step 3: Wire the callsites** — locate every write that mutates accounting state with a non-today date.

**Step 4: Test pass** + commit.

**Verification:** `pytest tests/test_eod_closed_state.py tests/test_costing.py -v` → all pass.

---

### Sprint 4.4 — BACKLOG #13: Waste deducts stock but doesn't update average cost

**Why fourth:** M effort; needs a stored "average cost" concept. Currently `purchase_price_gs` is "latest supplier price" — average cost is separate.

**Files:**
- Modify: `app/rms/models_legacy.py` (Ingredient) — add `avg_cost_gs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)` (denormalized Decimal-as-int)
- Create: `app/rms/migrations/_090_ingredient_avg_cost.py` — ADD COLUMN avg_cost_gs INTEGER, backfill from `purchase_price_gs`
- Modify: `app/rms/db.py` — register migration 90; bump version
- Modify: `app/rms/waste.py:record_waste` — recompute `ing.avg_cost_gs` after stock decrement (weighted by old avg vs new purchase_price if available)
- Modify: `app/routers/inventory.py` — set `avg_cost_gs` when purchase_price changes
- Test: `tests/test_waste_avg_cost.py` (new)

**Step 1: Migration + column** — add `avg_cost_gs` nullable.

**Step 2: Backfill** — copy `purchase_price_gs` to `avg_cost_gs` for existing rows.

**Step 3: Recompute on waste** — `avg_cost = ((old_avg * old_stock) - (cost_gs)) / new_stock` when new_stock > 0.

**Step 4: Update on price change** — when purchase_price_gs changes, weighted-blend into avg_cost.

**Step 5: Tests** — waste on 1kg bag reduces avg_cost proportionally.

---

### Sprint 4.5 — BACKLOG #4 (continued): Atomic migration conversion (10 more)

**Why this batch:** Multi-session refactor — knock out 5-10 migrations per session.

**Files:**
- Modify: each of 10 migration files, e.g. `app/rms/migrations/_073_*.py`, `_074_*.py`, etc.
- Modify: `app/rms/AGENTS.md` if needed

**Approach:** For each migration that has DDL strings, wrap each `conn.exec_driver_sql(sql)` call in `atomic_ddl_block(conn, [sql])`. Don't touch data migrations (they're idempotent upserts that already use savepoint patterns).

---

## Out of scope for this round

- **BACKLOG #17** (customer-facing `/p/{token}`) — has its own audit; defer to a separate security review session.
- **BACKLOG #1** (sale_stock_move + stock_movement consolidation) — too risky for an autonomous run; needs Ivan's sign-off on the data model decision.
- **BACKLOG #12** (forward-only migrations rollback) — architectural; needs a separate design.
- **BACKLOG #26-36** (analytics dashboards) — feature work, not backend correctness.
- **BACKLOG #37-40** (Supabase / Render / R2 infra) — vendor work, not backend overhaul.

---

## Tracking

| Sprint | Item | Status |
|---|---|---|
| 4.1 | BACKLOG #16 `/ventas/{id}` view | ⏳ pending |
| 4.2 | BACKLOG #19 RecipeLine.qty Numeric | ⏳ pending |
| 4.3 | BACKLOG #15 closed-day gate for all writes | ⏳ pending |
| 4.4 | BACKLOG #13 Waste → avg_cost | ⏳ pending |
| 4.5 | BACKLOG #4 convert 10 migrations to atomic | ⏳ pending |

## Execution approach

Per your "continue with the nexts" instruction, I'll execute Sprint 4.1 → 4.5 sequentially on `eng/2026-10-02-backend-overhaul`, committing after each phase. Each sprint = one or more commits, all green tests.

**Safety guardrails (same as before):**
- No `rm ... saskia` patterns
- Avoid destructive patterns that have hit me in previous sessions
- Verify each migration roundtrip with `init_db()` before bumping `CURRENT_SCHEMA_VERSION`
- Commit immediately after every logical unit (concurrent session can wipe the branch)
- Do NOT deploy — wait for Ivan's review (standing instruction)

## What this plan does NOT do

- Does NOT touch the live VPS
- Does NOT touch the deploy.sh script
- Does NOT modify concurrent-session hazards (those are outside this repo)
- Does NOT address the browser combo migration (Phase 14 Batch C — separate session)

---

## Where this plan lives

- This file: `.hermes/plans/2026-10-02_011912-backend-overhaul-next-up.md`
- Companion: `app/IMPROVEMENT_BACKLOG.md` (operator-curated, in-repo, updated as we complete work)
- Prior context: `app/SPRINT_SUMMARY.md` (Sep 23 sprint summary), `.hermes/plans/2026-10-01-phase14-post-phase13.md` (Phase 14 plan that started this work)