# Saskia RMS — Test-Suite Audit & E2E Strategy

**Date:** 2026-09-25
**Status:** proposal (not yet executed)
**Scope:** 232 test files, 37,154 LOC, ~2,212 tests, serial run ~7 min (2200 passed / 10 skipped / 10 deselected as of b6d5e16+logger fix).

## 1. What we have (measured)

### Strengths
- **Isolation core is solid.** `conftest.py` (486 lines): autouse `tmp_db_path` per test, tracked+closed sessions (kills ResourceWarnings), `reset_app_state`, CSRF auto-prime, auth-bypass env, `pg` mark for real-Postgres CI tests.
- **Markers declared AND used**: crud(18) smoke(9) analytics(12) perf(7) security(6) auth(5) pg(5) manual(2).
- **`quick_seed(scenario)` helper** exists (`tests/_fixtures_quick_seed.py`, 228 lines, 7 scenarios).
- Money/property-based discipline (`test_money.py` hypothesis, roundtrip import tests).

### Weaknesses (ranked by pain)

**W1 — Fixture duplication is massive.** 953 raw `session_factory()` sites; 170 inline `Product(name=...)`, 163 `Ingredient(name=...)` constructions; **39 local `_seed*` helpers** copy-pasted across files. Cost already paid this session: I hit hardcoded-name UNIQUE collisions three separate times while writing 5 new tests (recipes "Torta_" prefix workaround, ComplianceInfo id=1 collisions, etc.).

**W2 — No true end-to-end workflow tests.** `test_workflow.py` sounds like one but is actually EOD-checklist + seasonal-calendar unit tests. Nothing drives a multi-step business flow (restock → produce → pedido → sell → void → reconcile) through the **HTTP routes**. Every existing test either (a) tests one route in isolation or (b) writes DB rows directly and calls a function. Cross-router state bugs (like the orphan-decorator `/` bug, recipe line_qty field mismatch, `logger` NameError) are exactly the class that survives this suite.

**W3 — Migration-chain continuity untested at depth.** Migrations are hand-rolled and renumbered twice this month (039-042 → 050-053 collision resolution). We test "registry is contiguous" and "fresh DB reaches head", but not "a DB dumped at vN upgrades to head with data intact" for arbitrary N. The Phase-2B incident would have been caught in seconds by a boot-at-every-version smoke.

**W4 — Domain coverage gaps.** Files per domain (name-match): suppliers **1**, shopping **1**, customers 5, reports 3. Suppliers/shopping got big features (reorder loop, shopping list from demand forecast) with near-zero test surface.

**W5 — Parallel (xdist) failures accepted as folklore.** Engine tests fail under `-n 4`, pass serially; we shrugged. That is a real isolation leak being masked — something shares state across workers (suspects: module-level caches in engines, log file paths under a shared `AIW_SASKIA_LOG_DIR`, or the `sys.modules` purge pattern that bit us in-process).

**W6 — No failure-path/invariant sweep at E2E level.** Allergen guard, CSRF rejection, double-void, delete-in-use product, negative stock — each has unit tests in isolation, but no scenario asserts *invariants across a whole session* (stock never negative, money always int, snapshot prices immutable).

## 2. The E2E test plan (what to build)

### Tier 1 — "Un día en la panadería" scenario suite (`tests/e2e/`)
One parametrized flow driven through the TestClient (real routes, real CSRF, real redirects):

```
supplier → ingredient (+restock w/ price event) → recipe (with sub-recipe)
→ product (linked recipe) → pedido (whatsapp channel, customer w/ allergen)
→ confirm pedido → production run (consumes stock) → POS sale
→ second sale blocked by customer allergen (409) → void w/ reason
→ merma (waste) → EOD checklist → assertions
```

Post-flow invariants (the real value):
- stock_qty per ingredient == expected from movements, never negative
- every sale's `unit_price_gs` == product price *at sale time* (snapshot immutability after a price change mid-flow)
- food-cost variance report reconciles with seeded costs within tolerance
- tag algebra: product tags match ingredient tags after each edit in the flow
- money columns all `int` (query the DB directly, assert types)
- dashboard totals == sum of sale rows (catches the orphan-route/aggregation class)

Estimated: ~10 scenario tests, 1 factory module, +2-3 min suite time.

### Tier 2 — Migration archaeology test
- Build DB at every schema version 40→54 (or a sampled set), insert sentinel rows via the *old* model shape, run `upgrade_to_head`, assert sentinels survive with correct values. Catches the next renumbering collision and the next half-written migration before prod boot does.

### Tier 3 — Failure-path matrix
Systematic: for each mutation route, the "hostile POST" (missing field, garbage money string, negative qty, non-existent FK). `app/rms/validation` centralizes this — test it once per validator plus one E2E per form.

### Tier 4 — Fix W5 (xdist)
Bisect the shared state. Likely wins: make engine modules stateless-per-call (tag_algebra already moved to lazy imports for the same reason), isolate log dirs per worker (`AIW_SASKIA_LOG_DIR` under `tmp_path` — already autouse, so suspicion falls on module-level caches).

## 3. The refactors that make all this cheap

### R1 — Builder factories module: `tests/factories.py` (no new deps)
`factory_boy` would need operator OK (AGENTS.md rule 1) and we don't need it — plain builders with **auto-unique names** kill the collision class by construction:

```python
def make_ingredient(s, *, name=None, **kw) -> Ingredient:
    """name defaults to f"{verb}-{n} {uuid4().hex[:6]}" — UNIQUE-safe."""
def make_recipe(s, *, lines: list[LineSpec] = [], **kw) -> Recipe
def make_sale(s, *, product=None, qty=1, at=None, **kw) -> Sale
def make_customer(s, *, allergens=None, **kw) -> Customer
def make_pedido(s, *, lines=[...], status="pending", **kw) -> Pedido
# composable: make_recipe(lines=[ing_line(make_ingredient()), sub_line(sub)])
```

Rules: every builder takes the session first, commits-or-flushes per caller choice, accepts `**kw` passthrough for the 55-column Ingredient model, and returns the instance. Then: **freeze `quick_seed` API but reimplement scenarios on top of factories** — one implementation, two interfaces.

### R2 — Flow helpers for E2E: `tests/flows.py`
HTTP-level actions (`restock(client, ing_id, qty, price)`, `sell(client, product_id, qty)`, `void(client, sale_id, reason)`) returning parsed responses. E2E tests then read like the scenario outline above instead of 40-line POST blobs. This is where CSRF/redirect/assert-shape duplication gets centralized.

### R3 — Absorb the 39 local seed helpers
Mechanical, per-file: local `_seed_*` → factory call. Do it opportunistically (when a file is touched) plus one dedicated sweep for the top 10 duplicators (`test_ui_smoke`, `test_routes`, `test_pedidos`, `test_costing`...). Don't big-bang all 53 files.

### R4 — Split conftest when it hurts
486 lines is still fine; extract the Supabase fake and the unraisable-silencer into `tests/_lib/` only when the factories/flows land (they'll need their own imports anyway).

### R5 — Conftest hardening for prod parity
- Add a `strict_auth_client` fixture (auth enabled, real bcrypt login via env-injected test password) — the prod auth path added 2026-09-24 has no E2E test with auth ON.
- Add `asuncion_now` freeze helper (freezegun-style via monkeypatch of `_asuncion_today` callers or env TZ) — the midnight flake class stays dead.

## 4. Sequencing (est. 12-16 h total)

| Phase | What | Why first | Est |
|---|---|---|---|
| 1 | `tests/factories.py` + rewrite quick_seed internals + migrate 3 pilot files | Everything else builds on it | 3 h |
| 2 | `tests/flows.py` + Tier-1 "un día" suite (10 scenarios) | Highest bug-yield per hour | 4 h |
| 3 | Tier-2 migration archaeology | Cheap, prevents the Phase-2B class | 2 h |
| 4 | xdist bisect (W5) + strict_auth_client + TZ freeze | Unblocks `-n auto` fast loop | 3 h |
| 5 | Suppliers/shopping test files (W4) + top-10 dedup sweep | Coverage debt | 4 h |

Phase 1+2 alone would have caught every production bug found this week (orphan `/` route: flows assert redirect targets; recipe line_qty mismatch: flows POST the real form; `logger` NameError: any E2E POST).
