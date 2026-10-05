# Saskia RMS — Test-Code Deep Analysis: Refactors & Abstractions

**Date:** 2026-09-25
**Baseline:** 233 test files in `tests/` + 7 in `tests/e2e/`; 2,231 tests green
serial; 2,216 green under `-n 4`. Factories exist (7 builders), flows exist
(6 route paths), conftest has 34 fixtures.

All numbers below are measured with regex sweeps over the actual test code —
not estimates.

## 1. Measured state

| Metric | Value | Meaning |
|---|---|---|
| Raw `session_factory()` sites | 998 | hand-rolled DB setup everywhere |
| `make_*` factory calls | 126 | adoption is ~11% of the way |
| Inline `Ingredient(name=` | 161 remaining | the collision-prone pattern |
| Inline `Product(name=` | 170 remaining | same |
| Local `_seed*`/`_make*` helpers | 49 across ~30 files | copy-paste surface |
| Direct `client.post(` sites | 299 (non-e2e) | repeated HTTP boilerplate |
| `flows.*` uses | 26 (all in e2e) | flows not adopted outside e2e |
| `assert status==200` (content-blind) | 379 | smoke-only assertions |
| Literal-ID (`== 1`) reliance | ~210 sites | fresh-db ordering assumptions |
| Model classes / factory coverage | 45 / 7 | 38 models never factory-built |
| Marker adoption | 74 total marks | tiny vs 2,231 tests |
| conftest.py | 509 lines, 34 fixtures | near extraction threshold |
| e2e/ dir | 7 files / 37 tests | new, healthy |

## 2. The refactor program (ranked by leverage)

### R1 — `tests/factories.py`: complete the model coverage (biggest lever)
38 of 45 models have no builder. The high-value additions (used repeatedly
by tests but never centralized):
- `make_ingredient_variant` (+ `preferred` flag), `make_price_event`
- `make_waste_log`, `make_delivery_zone`
- `make_user(role=)` — needed for every future authz test
- `make_production_plan(+overrides)`, `make_production_completion`
- `make_tag`/`make_tag_link` (tag-algebra tests hand-roll these today)
- `make_import_batch`

Design rule to keep: auto-unique names + `**kw` passthrough + session-first.
**Est: 3 h** — then the inline-construction sweep below gets mechanical.

### R2 — Adopt factories across the top duplicators (mechanical sweep)
Kill the remaining 161+170 inline constructions and 49 local helpers file by
file, prioritized by count: `test_ingredient_intel` (66), `test_visual_revolution`
(40), `test_ui_smoke` (38, partially done), `test_recipe_intel` (31),
`test_routes` (28), `test_reports` (22). Rule: when touching a file, convert
it; do not big-bang all 233. **Est: 6-8 h total, incremental.**

### R3 — Extend `flows.py` from 6 → ~30 paths
299 direct `client.post(` sites exist because flows only covers recipes,
sales, stock, pedidos, merma, shopping. Add: products CRUD, customers CRUD,
suppliers CRUD, reorder/restock, EOD, excel upload, settings-runtime JSON
helpers (`api_crud(path, payload, update)` — generic over the /api/ cluster),
exports. Each new flow centralizes CSRF/redirect/assert-shape handling once.
**Est: 3 h** — pays off for every future scenario.

### R4 — `tests/_lib/` extraction from conftest
509-line conftest with 34 fixtures is at the edge. Extract:
- `_lib/supabase_fake.py` (the Fake class + fixtures)
- `_lib/warnings.py` (the unraisable-hook silencer)
- keep fixtures in conftest, move machinery out
Also: the e2e dir needs its own thin `conftest.py` declaring the `e2e` marker
and importing flows/factories paths explicitly. **Est: 2 h**

### R5 — Assertion upgrades: beyond `status == 200`
379 content-blind assertions. Pattern to adopt (already proven in e2e):
```python
resp = flows.page(client, "/dashboard")
assert "Gs." in resp.text and "Ventas" in resp.text
```
A lint-style review (one pass per file during R2) converts the worst ones.
Add a `assert_see(client, path, *needles)` flow helper. **Est: folded into R2.**

### R6 — Literal-ID elimination
~210 `== 1` sites assume fresh-DB id ordering. They work only because every
test gets a fresh DB; they break the moment a test legitimately seeds
multiple rows or the fixture ordering changes. Fix: capture ids from
creation returns (factories already return instances). **Est: folded into R2.**

### R7 — Marker discipline + CI tiers
74 marks / 2,231 tests is noise. Target: every test file carries ≥1 of
smoke/crud/analytics/auth/security/e2e. Then CI can run:
- PR: `-m "smoke or crud or auth or security"` (~5 min)
- nightly: full serial + xdist verification + `-m perf`
- weekly: `-m manual` + migration archaeology full sweep (all 54 versions)
**Est: 2 h mechanical + pyproject config.**

### R8 — xdist as the DEFAULT fast loop
Now that `-n 4` is green, make it the documented standard (`just test-fast`),
keep serial as the release gate. Saves 2 min per iteration × dozens/day.
**Est: 30 min (docs + Makefile).**

### R9 — Property-based expansion
hypothesis exists for money/units only. Highest-value additions:
- stock reconciliation property: for any sequence of (sale, void, adjust,
  waste) ops, final stock == initial + Σ moves (generative mini-day)
- snapshot property: sale prices never change on catalog edits
- tag algebra properties: intersection commutativity, allergen union
  monotonicity (adding an ingredient never removes an allergen)
**Est: 4 h** — these find whole classes at once.

### R10 — Determinism audit
- `test_shopping_benchmarks` hard-depends on `/tmp/herbus_drive/dump.json`
  → convert to pytest.importorskip or build the fixture from
  `tests/fixtures/build_herbus_drive_fixture.py` in CI.
- Any remaining `datetime.now()` in test bodies (vs factories' injected
  timestamps) — sweep to `freeze_asuncion` or explicit timestamps.
**Est: 1.5 h**

## 3. Sequencing

| Phase | Items | Est |
|---|---|---|
| A | R1 (factories complete) + R3 (flows 30 paths) + R4 (conftest split) | 8 h |
| B | R2 sweep of top-6 duplicators (+ R5/R6 folded in) | 8 h |
| C | R7 markers/tiers + R8 xdist-default + R10 determinism | 4 h |
| D | R9 property-based suite | 4 h |

Phases A+B transform day-to-day test writing; C makes CI honest; D catches
bug classes instead of bug instances. Total ≈ 24 h of largely mechanical,
low-risk work with no production-code changes.
