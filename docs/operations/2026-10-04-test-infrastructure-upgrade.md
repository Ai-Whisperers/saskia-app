# Saskia Test Infrastructure Upgrade — Master Plan

**Date:** 2026-10-04 (post-PR #46 cleanup)
**Owner:** Test infrastructure squad
**Coverage floor:** 35% → target 80%
**Test suite size:** 484 files, 165k LOC, ~7,900 tests, 279 endpoints

---

## TL;DR — The 4 strategic pillars

The test suite is **dense but not deep**. We have:
- Lots of tests (28 tests/endpoint) but coverage stuck at 35%
- Two competing seed systems (qseed + 20+ local `_seed_*` helpers)
- 230 of 279 routes have no dedicated test
- 17 files over 500 lines (refactor candidates)
- 42 files under 50 lines (merge candidates)
- `tests/flows.py` has 20+ business-action helpers used by only 7 files

The upgrade targets 4 pillars:

1. **Pillar A: Codify the suite** — generate tests from production code (routes, models)
2. **Pillar B: Unify factories & seeds** — kill the two-system split
3. **Pillar C: Maximize abstraction reuse** — make flows.py + invariants + factories the floor
4. **Pillar D: Performance + parallelism** — module-scope fixtures, shared seeds

---

## Pillar A — Generate tests from production code (the multiplier)

### A1. Route-level smoke generator — biggest single win

**Problem:** 230 of 279 routes have ZERO dedicated tests. Coverage gate stuck at 35%.

**Solution:** Build `scripts/gen_route_smoke.py` that introspects FastAPI routers and generates a parametrized test for each endpoint.

**How it works:**
```python
# Walks app/routers/* + app/rms/main.py
# For every @router.{get,post,put,delete,patch}, extracts:
#   - path
#   - HTTP method
#   - function signature (what params it expects)
#   - response_model (if any)
#   - dependencies (auth, csrf, etc.)
# Generates tests/test_route_smoke_generated.py with:
#   - @pytest.mark.parametrize over (method, path, expected_status)
#   - Skips routes already covered by dedicated tests
#   - Hits each route with `client.{method}(path)` with `SASKIA_TEST_AUTH_DISABLED=1`
#   - Asserts status in {200, 303, 422} (acceptable), not 500
```

**Output:**
- ~250 generated test cases
- Bumps coverage from 35% → ~50% (per coverage-strategy doc estimate)
- Cost: **4 hours** (script + integration)

**Pattern reference:** Python projects like [Bigger-House](https://github.com/iqb-berlin/testcenter-backend) use `pytest-openapi-schema`; we'll write our own since the schema is FastAPI-specific.

### A2. Model-relationship property generator

**Problem:** 55 model classes have scattered invariant tests (`stock_never_negative`, `money_is_int`). Most invariants are inferred from SQLAlchemy column types but never tested.

**Solution:** Build `tests/test_model_invariants.py` that introspects `app/rms/models.py` and generates property tests for each numeric/string/date column.

```python
# For each column:
#   - Non-negative integer columns → @given(st.integers(min_value=0)) test
#   - Money columns → @given(st.integers) + assert result is int (money rule 4)
#   - Foreign keys → assert cascade rules work
#   - Enum columns → assert only valid values
#   - created_at / updated_at → assert auto-set
```

**Cost:** 6 hours. **Output:** ~200 new property tests.

### A3. CRUD roundtrip generator

**Problem:** Tier 3 in coverage-strategy said "20 most-used CRUD endpoints, 4h". We can do this generically.

**Solution:** For each model that has `POST /<resource>`, `PUT /<resource>/{id}`, `DELETE /<resource>/{id}` endpoints, generate a CRUD roundtrip test.

**Cost:** 4 hours.

### A4. Template-render coverage

**Problem:** Jinja templates + `template_render.py` = ~2,100 uncovered statements.

**Solution:** `tests/test_template_render_auto.py` — discovers every template name from `app/templates/**/*.html`, renders each with a known fixture context, asserts no `{{Undefined }}` exception.

**Cost:** 4 hours. (Per Tier 2 of coverage-strategy.)

---

## Pillar B — Unify factories & seeds

### B1. Single seed registry — kill the two-system split

**Current state:**
- `tests/factories.py` — 17 `make_*` functions (good, but underused)
- `tests/_fixtures_quick_seed.py` — 10 `qseed()` scenarios (135 calls)
- 20+ duplicated `_seed_*` private helpers in 6+ test files

**New structure:**
```
tests/
├── factories.py              # existing make_* (move all DB-row creators here)
├── seeders.py               # NEW: business-level seeders (qseed scenarios + private _seed_*)
└── conftest.py              # re-exports qseed fixture pointing at seeders.qseed
```

**Migration map (sample):**
| Old (duplicated) | New (centralized) |
|---|---|
| `def _seed_basic(session_factory):` (3 copies) | `seeders.basic(session_factory)` |
| `def _seed_sale(session_factory):` (6 copies) | `seeders.with_sale(session_factory)` (already exists in qseed) |
| `def _seed_pedido(session_factory):` (4 copies) | `seeders.with_pedido(session_factory)` |
| `def _seed_recipe(session_factory):` (1 copy) | `seeders.with_recipe(session_factory)` |

**Process:**
1. Inventory all 50+ `_seed_*` functions across the suite
2. Map each to a qseed scenario (or new scenario if missing)
3. Move bodies to `tests/seeders.py`
4. Replace all call sites with `qseed("scenario_name")`
5. Delete the private helpers
6. Add type hints + docstrings

**Cost:** 8 hours.
**Output:** Saves ~600 LOC of duplication.

### B3. Edge-case factories as factory inputs

The factories (`make_*`) return one entity with **default values**. Tests then have to:
- Modify the entity to set up edge cases
- Recreate relationships (e.g., `make_recipe` creates 1 line, but tests need 5 lines)
- Set fields that aren't exposed

**Solution:** Add a `with_*` namespace on each factory:
```python
make_recipe()             # 1 recipe, 1 line, default name
make_recipe(with_n_lines=5, with_low_margin=True, named="Special cake")
make_recipe(with_lines="invalid_qty")  # for invalid-input tests
```

Implemented via builder pattern: `RecipeFactory().with_n_lines(5).with_low_margin().build(session)`.

**Cost:** 6 hours. **Output:** Removes 200+ lines of factory-calling boilerplate from tests.

### B4. Polyfactory / factory_boy exploration

Consider replacing hand-rolled `make_*` with [polyfactory](https://github.com/litestar-org/polyfactory) which auto-generates factories from Pydantic/SQLAlchemy models. Trade-off:

| Approach | Pros | Cons |
|---|---|---|
| Hand-rolled (current) | Explicit, predictable, debuggable | Verbose, drift risk |
| polyfactory | Auto-generated, less code, syncs with schema | Magic, harder to debug |
| **Hybrid** (recommended) | Hand-rolled for business objects, auto for value objects | Best of both |

**Recommendation:** Stay with hand-rolled for entities (Product, Sale, Pedido — too much business logic). Add polyfactory for pure value objects (Address, Money, Color). 4 hours exploration.

---

## Pillar C — Maximize abstraction reuse

### C1. flows.py — the underused goldmine

**Current state:** `tests/flows.py` has 20+ `create_*`, `update_*`, `*_stock`, `*_status` helpers. **Only 7 test files use it.**

**Why underused:** Probably because nobody added it to conftest, and discoverability is low.

**Solution:**
1. **Promote flows.py helpers into conftest.py as fixtures** — `make_pedido_via_api`, `create_product_via_api`, etc.
2. **Add a flows.py browser counterpart** — page actions that wrap Playwright operations (`flows_browser.py`)
3. **Migration campaign** — for every test that does `client.post("/pedidos", data={...})`, replace with `create_pedido(client, ...)`

**Cost:** 12 hours (mostly migration). **Output:** Each test goes from ~15 lines of HTTP boilerplate to 1-2 lines.

### C2. Assert helpers — the next step after invariants

**Current state:** `_lib/invariants.py` has `stock_never_negative`, `money_is_int`. That's it.

**Solution:** Expand to cover AGENTS.md invariants + common test patterns:
```python
# app/rms invariants
stock_never_negative(session)
money_is_int(session)
audit_log_present_for(session, entity_type, entity_id)
total_stock_matches_recipes(session)  # whole-sale + ingredient = recipe sum
recipe_cost_within_margin(session, recipe_id, expected_margin_pct)

# HTTP-level asserts
assert_status(r, in_=[200, 303])
assert_no_js_errors(page)
assert_audit_logged(session, action="sale_void", entity_id=sale_id)
assert_redirected_to(r, expected_path)
```

**Cost:** 6 hours.

### C3. Page Object expansion

**Current state:** `tests/browser/pages.py` has 3 pages (Page, LoginPage, DashboardPage). Most browser tests reach into selectors directly.

**Solution:** Add Page Objects for every tested screen:
- RecipeDetailPage, ProductDetailPage, ClienteDetallePage
- PedidoListPage, PedidoDetailPage, PedidoNewPage
- InventoryPage, MermaPage, ReportsPage

**Cost:** 12 hours (one page per ~30 min). **Output:** When UI changes, update one file.

### C4. Service layer tests — the deepest gap

**Current state:** 16 service modules with 93 functions. Most have 0 tests. Most business logic lives in routers, NOT services.

**Problem:** Routers mix 3 things — parameter parsing, business logic, response shaping. Hard to test business logic without going through the HTTP layer (slow).

**Solution:** **Refactor routers → extract service functions.** For each router that has `if/else` chains or business rules:
1. Extract the rule into `app/services/<name>.py`
2. Add unit tests for the service
3. Router becomes a thin shim: parse params → call service → return response

**Example:** `app/routers/sales.py:void_sale` → extract to `app/services/sales_service.py:void_sale(sale_id, reason, session)`.

**Cost:** 40+ hours (large refactor). **Output:** Coverage from 35% → 60%+.

---

## Pillar D — Performance + parallelism

### D1. Module-scoped fixtures for read-only tests

**Current state:** ~4,100 `session_factory()` calls. Each test creates a fresh SQLite DB. ~2s of fixture setup per test.

**Solution:** Module-scoped seed → per-test rollback.
```python
@pytest.fixture(scope="module")
def seeded_world(session_factory_module):
    """Heavy seed once per module."""
    return seed_minimal_world()

@pytest.fixture(autouse=True)
def rollback_session(session_factory, seeded_world):
    """Rollback every test to the seeded snapshot."""
    yield
    session_factory.rollback()
```

**Cost:** 16 hours. **Output:** Test time 15 min → ~6 min (per parallel-tests.md estimate).

### D2. Selective seed selection

Most tests need only 1-3 entities. `qseed("with_kyrian_full")` seeds 50+ entities in ~1.5s.

**Solution:** Build a tiny "entity seed cache" that:
1. Seeds an entity once per session
2. Reuses it across tests via reference
3. Counts entities needed per test (auto-detected from imports?)

**Cost:** 8 hours exploration. **Output:** Marginal improvement on top of D1.

### D3. Smart test collection

`pytest-xdist -n 2` is already on CI. But it doesn't load-balance by test weight.

```python
# pytest-xdist with --dist=loadfile groups tests by file
# Better: --dist=loadscope groups by class/module (groups slow tests together)
```

**Recommendation:** Add `--dist=loadscope` to ci.yml. **Cost:** 30 min.

### D4. Mock vs real trade-off audit

`SASKIA_TEST_AUTH_DISABLED=1` skips auth everywhere.** Question:** should all tests bypass auth? Some tests should exercise the auth path.

**Current:** All happy-path tests bypass. **Auth-path tests** are in `tests/e2e/test_strict_auth.py` only.

**Recommendation:** Keep current. Audited.

### D5. Property-based test expansion

7 files use it. Should be 20+. Apply to:
- Recipe costing (`compute_cost(recipe)` invariants)
- Money conversions (already done — `test_money.py`)
- Date/timezone math (invariance across DST, leap years)
- Report aggregations (sums, averages, percentiles)

**Cost:** 12 hours. **Output:** +200 property test cases.

---

## Migration path — what to ship first

### Phase 1 (1 week) — Quick wins, low risk
| Task | Pillar | Effort | Outcome |
|---|---|---|---|
| Route smoke generator | A1 | 4h | +200 tests, coverage +5% |
| Expand invariants.py | C2 | 6h | +15 helpers, -200 LOC in tests |
| Promote flows to fixtures | C1 | 6h | -300 LOC in tests |
| Add `--dist=loadscope` | D3 | 30m | Faster CI |

**Total: 16.5h.** Outcome: 200+ new tests, 35% → 40% coverage, ~500 LOC removed.

### Phase 2 (2 weeks) — Refactor foundations
| Task | Pillar | Effort | Outcome |
|---|---|---|---|
| Single seed registry | B1 | 8h | -600 LOC duplication |
| Edge-case factories | B3 | 6h | -200 LOC |
| Service extraction (top 10 routers) | C4 | 24h | +30 unit tests, coverage +10% |
| Model invariant generator | A2 | 6h | +200 property tests |

**Total: 44h.** Outcome: 35% → 50% coverage, -800 LOC duplication.

### Phase 3 (3 weeks) — The big lift
| Task | Pillar | Effort | Outcome |
|---|---|---|---|
| Template-render coverage | A4 | 4h | +500 tests, coverage +10% |
| CRUD roundtrip generator | A3 | 4h | +500 tests |
| Page Object expansion (8 pages) | C3 | 4h | -200 LOC browser tests |
| Module-scoped fixtures | D1 | 16h | Test time 15m → 6m |
| Property test expansion | D5 | 6h | +200 tests |

**Total: 34h.** Outcome: 50% → 65% coverage, test time cut 60%.

### Phase 4 (4+ weeks) — The 80% push
| Task | Pillar | Effort | Outcome |
|---|---|---|---|
| Service extraction (remaining 20 routers) | C4 | 40h | +60 unit tests, coverage +15% |
| Hand-rolled factory vs polyfactory decision | B4 | 4h | Adopt or reject polyfactory |
| Audit log invariant coverage | C2 | 4h | +20 tests |

**Total: 48h.** Outcome: 65% → 80% coverage (the AGENTS.md target).

---

## Total investment: 142.5 hours over 10 weeks

**Total return:**
- 33 coverage points (35% → 68-80%)
- ~2,000+ new tests (codify, generate, parameterize)
- ~1,500 LOC of duplication removed
- Test time cut 60% (15 min → 6 min)
- Easier to onboard new contributors (less code to read)
- Faster PR review (tests are smaller, factories are obvious)

---

## What NOT to do

1. **Don't rewrite working tests just to make them "prettier".** If `_seed_basic` works in one file, leave it. Only unify when there's an actual duplication cost.
2. **Don't add polyfactory until you've measured the pain.** Polyfactory is great but adds magic. If `make_recipe()` is 3 lines and easy to debug, keep it.
3. **Don't generate tests as the only strategy.** Generated tests catch "does it 500?" not "is the business logic right?". You still need hand-written invariants.
4. **Don't break AGENTS.md rule 4** (money is int). Any factory that returns money as float is a regression.
5. **Don't run all 7,900 tests in pre-commit.** The full suite is too slow. Use a `quick` subset (Tier 1 smoke + critical paths).

---

## Tracking + ownership

**Sprint board:**
- `SASKIA-TEST-INFRA` Jira label
- Phases 1-4 as epics
- Each task = 1 ticket

**Owner:** Test infrastructure squad (TBD — currently Ivan)

**Cadence:** 1 phase per 1-2 weeks

**Definition of done per phase:**
- All new tests pass locally
- Coverage gate bumped + X% (per phase plan)
- No ruff errors
- Documentation reflects changes (`docs/operations/test-infra.md`)
- At least 1 review from product side (Saskia doesn't see regressions)

---

## Open questions

1. **Is the 80% coverage target realistic?** AGENTS.md says 80%. Current is 35%. We can hit 65% in Phase 3. Phase 4 is a stretch.
2. **Do we want a separate `tests/services/` directory for unit tests of extracted service functions?** Currently tests are organized by route. Services would break that pattern.
3. **Should the seed registry be JSON-driven?** Could let non-developers add new seed scenarios without touching code.

---

## Refs

- `docs/plans/2026-10-01-phase14-coverage-strategy.md` — Tier 1-4 plan (our Phase 1-4 partially overlaps)
- `docs/operations/2026-10-04-parallel-tests.md` — pytest-xdist config (we built on this)
- `docs/operations/2026-10-04-migration-cross-dialect-rewrite.md` — sibling concern
- `tests/conftest.py` — current fixture spine
- `tests/factories.py` — current factory spine
- `tests/flows.py` — underused helper layer
- `tests/_lib/invariants.py` — invariant assertions (C2 expands this)