# Test Infrastructure Upgrade — One-Pager

**Date:** 2026-10-04
**Sister doc:** [2026-10-04-test-infrastructure-upgrade.md](2026-10-04-test-infrastructure-upgrade.md)

---

## What we have today (the numbers)

| Metric | Value | Where |
|---|---|---|
| Test files | 484 | `tests/` |
| Test LOC | ~165,000 | `tests/` |
| Test functions | ~7,900 | collected |
| Endpoints | 279 | `app/routers/` + `app/rms/main.py` |
| Coverage gate | 35% → target 80% | `pyproject.toml`, AGENTS.md |
| Property-based test files | 7 | use `hypothesis` |
| Files > 500 LOC | 17 | refactor candidates |
| Files < 50 LOC | 42 | merge candidates |
| Existing abstractions | 6 | factories, qseed, flows, pages, invariants, supabase_fake |

## What we have today (the gaps)

| Gap | Severity | Evidence |
|---|---|---|
| 230/279 routes have NO dedicated test | 🔴 Critical | `bash scan.sh` output |
| 2 competing seed systems (qseed + 20 local `_seed_*`) | 🟡 Important | `_seed_sale` defined in 6 files |
| `tests/flows.py` used by only 7/484 files | 🟡 Important | 20 helpers underused |
| 16 service modules with 93 funcs, most untested | 🟡 Important | refactor + test together |
| Coverage gate stuck at 35% | 🔴 Critical | pyproject.toml |
| Test runtime 15+ min on -n 2 | 🟡 Important | `parallel-tests.md` |
| Money/stock invariants live in 1 helper file | 🟢 Minor | `tests/_lib/invariants.py` |

---

## The 4 pillars (one sentence each)

| Pillar | Pitch |
|---|---|
| **A. Codify** | Generate tests from production code (routes, models) instead of writing them by hand |
| **B. Unify** | Kill the two-system split between qseed and local `_seed_*` helpers |
| **C. Reuse** | Make flows.py + invariants + factories the floor of every new test |
| **D. Parallelize** | Module-scope fixtures + smarter xdist = test time cut 60% |

---

## Phase 1 — 1 week, 16.5h, biggest wins

| Task | Pillar | Effort | Outcome |
|---|---|---|---|
| `scripts/gen_route_smoke.py` — auto-generate smoke tests for 230 un-tested routes | A1 | 4h | +200 tests, coverage +5% |
| Expand `tests/_lib/invariants.py` (15 new helpers: audit_log_present_for, recipe_cost_within_margin, etc.) | C2 | 6h | -200 LOC in tests |
| Promote `tests/flows.py` helpers into `conftest.py` fixtures | C1 | 6h | -300 LOC in tests |
| Add `--dist=loadscope` to `.github/workflows/ci.yml` | D3 | 30m | Faster CI load balancing |

**Definition of done:** 200+ new tests, coverage gate bumped 35% → 40%, ~500 LOC removed, ruff clean.

---

## Phase 2 — 2 weeks, 44h, refactor foundations

| Task | Pillar | Outcome |
|---|---|---|
| Single seed registry (`tests/seeders.py` + migration) | B1 | -600 LOC duplication |
| Edge-case factories (`make_recipe(with_n_lines=5, with_low_margin=True)`) | B3 | -200 LOC |
| Extract services from top 10 routers | C4 | +30 unit tests, coverage +10% |
| Model invariant generator (`@given` over SQLAlchemy columns) | A2 | +200 property tests |

**Definition of done:** Coverage 40% → 50%, ~800 LOC removed.

---

## Phase 3 — 3 weeks, 34h, the 80% push (part 1)

| Task | Pillar | Outcome |
|---|---|---|
| Template-render coverage (`tests/test_template_render_auto.py`) | A4 | +500 tests, coverage +10% |
| CRUD roundtrip generator | A3 | +500 tests |
| Page Object expansion (8 pages: RecipeDetail, ProductDetail, ClienteDetalle, PedidoList/Detail/New, Inventory, Merma, Reports) | C3 | -200 LOC browser tests |
| Module-scoped fixtures with rollback | D1 | Test time 15m → 6m |
| Property test expansion (recipe costing, date math, report aggregations) | D5 | +200 tests |

**Definition of done:** Coverage 50% → 65%, test time cut 60%.

---

## Phase 4 — 4+ weeks, 48h, the 80% push (part 2)

| Task | Pillar | Outcome |
|---|---|---|
| Service extraction (remaining 20 routers) | C4 | +60 unit tests, coverage +15% |
| Hand-rolled factory vs polyfactory decision | B4 | Adopt or reject polyfactory |
| Audit log invariant coverage | C2 | +20 tests |

**Definition of done:** Coverage 65% → 80% (AGENTS.md target).

---

## Total

- **142.5 hours / 10 weeks**
- **+2,000 tests** (generated + parameterized)
- **-1,500 LOC** (deduplication)
- **+33 coverage points** (35% → 68-80%)
- **-60% test time** (15 min → 6 min)

---

## The 5 things to do RIGHT NOW (this session)

1. **Create `scripts/gen_route_smoke.py` skeleton + 1 router test to validate the approach** (45 min)
2. **Audit `tests/flows.py` — pick the top 3 underused helpers and migrate 5 tests to use them** (1 hr)
4. **Inventory every `_seed_*` helper across the suite** — produce a migration map (45 min)
4. **Add 3 new invariants to `_lib/invariants.py`** (audit_log_present_for, total_stock_matches_recipes, recipe_cost_within_margin) (30 min)
5. **Add `--dist=loadscope` to ci.yml** (15 min)

**Total: 3.5 hours.** Wins: validates Phase 1 approach, makes 5 tests shorter, documents the seed migration, makes CI faster.

---

## What NOT to do

1. ❌ Don't rewrite working tests for "prettier" — only unify when duplication hurts
2. ❌ Don't add polyfactory until you've measured the pain
3. ❌ Don't generate tests as the only strategy — still need hand-written invariants
4. ❌ Don't break AGENTS.md rule 4 (money is int)
5. ❌ Don't run all 7,900 tests in pre-commit — use a `quick` subset

---

## Tracking

- Jira label: `SASKIA-TEST-INFRA`
- Phases 1-4 as epics
- Each task = 1 ticket
- Owner: Test infra squad (TBD)
- Cadence: 1 phase per 1-2 weeks
- Review: 1 product-side reviewer per phase (Saskia shouldn't see regressions)