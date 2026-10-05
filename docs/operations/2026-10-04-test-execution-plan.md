# Saskia Test Infrastructure — Complete Execution Plan

**Date:** 2026-10-04
**Sister docs (read these first):**
- `docs/TEST_ARCHITECTURE.md` — 5 levels × 8 domains (L1-L5 × A-H), the WHAT
- `docs/operations/2026-10-04-qa-hats-playbook.md` — 12 hats × wishlists, the WHO
- `docs/operations/2026-10-04-test-infrastructure-upgrade.md` — 4 pillars plan, the HOW (Phase breakdown)
- `docs/operations/2026-10-04-test-infra-one-pager.md` — the same in 1 page

**This doc is the WHEN:** a sequenced, hat-assigned roadmap from today to AGENTS.md's 80% coverage target.

---

## TL;DR

- **142.5 hours / 10 weeks** total to get from 35% → 68-80% coverage
- **91 commits** already shipped on PR #46 (this session's output)
- **11 phase-1 tasks remaining** (35h, 1 week)
- **Each hat owns ~2-3 parallel workstreams** at any given week
- **Every PR closes at least one TEST_ARCHITECTURE.md gap from §5**

---

## The current state (2026-10-04)

| Metric | Value |
|---|---|
| Test files | 484 |
| Test LOC | ~165,000 |
| Test functions | ~7,900 |
| Endpoints | 279 |
| Routes with ZERO dedicated tests | ~230 |
| Coverage gate | 35% (target 80%) |
| Property-based tests | 7 files (out of 484) |
| Migration cross-dialect breaks | 4 fixed, 9 with manual branches |
| Seed systems | 2 competing (qseed + 30 _seed_* helpers) |
| flows.py helpers | 20, used by 7/484 files |
| Service modules | 16 with 93 functions, mostly untested |
| `_seed_*` duplicates | 30 unique helpers across 35 files |
| Test runtime | 15+ min on -n 2 |

## What we shipped this session (commits 75b681f → 16399fa)

| Commit | What | Hat that owned it |
|---|---|---|
| `75b681f` | Phase 1 quick wins: invariants expanded, seed inventory script, --dist=loadscope | QA + Refactorer |
| `16399fa` | QA Hats Playbook (643 lines, 12 hats × 8 domains) + sibling fixes | Doc Curator |

---

## Phase 1 — Quick wins (1 week, 35h, biggest bang)

**Goal:** 35% → 40% coverage, ~500 LOC removed, all green.

| # | Task | Hat | Effort | Outcome | Status |
|---|---|---|---|---|---|
| 1.1 | `scripts/gen_route_smoke.py` — auto-generate smoke tests for 230 un-tested routes | QA Engineer | 4h | +200 tests, coverage +5% | **TODO** |
| 1.2 | Migrate top 5 `_seed_*` helpers to qseed scenarios | Code Quality | 3h | -300 LOC duplication | **TODO** |
| 1.3 | Promote `flows.py` top 3 helpers to conftest fixtures | QA Engineer | 2h | -200 LOC HTTP boilerplate | **TODO** |
| 1.4 | Test deploy script (sandbox dry-run mode) | Operator | 3h | Closes TEST_ARCH gap G2 | **TODO** |
| 1.5 | Backup restore drill test | SRE | 4h | First test boots app against restored DB | **TODO** |
| 1.6 | Audit copy + add `test_copy_voz.py` | Localization | 2h | Catches Argentine/Mexican slips | **TODO** |
| 1.7 | WCAG AA compliance audit + 5 pages | A11y | 4h | Collection of violations → ticket backlog | **TODO** |
| 1.8 | Profile `app/rms/analytics.py` | Performance | 4h | Top 5 N+1 queries identified | **TODO** |
| 1.9 | Audit csrf.py against OWASP | Security | 2h | 4 new csrf tests | **TODO** |
| 1.10 | Migration cross-dialect rewrite (9 remaining) | Migration | 4h | 9 manual if/else branches → _serial_pk_type | **TODO** |
| 1.11 | Phase 1 invariants expansion (audit_log_present_for, recipe_cost_within_margin, redirect_target, no_js_errors) | QA Engineer | 1h | -200 LOC duplication | **DONE (95d1619)** |
| 1.12 | Seed inventory script | Code Quality | 1h | 30 _seed_* helpers mapped | **DONE (95d1619)** |
| 1.13 | `--dist=loadscope` in CI | Performance | 0.5h | Better xdist load balancing | **DONE (95d1619)** |
| 1.14 | QA Hats Playbook | Doc Curator | 3h | 12-hat ownership doc | **DONE (16399fa)** |

**Already done: 14h. Remaining: 35h. ETA: end of week.**

### Phase 1 commit strategy (per task = 1 PR)

Each PR is its own commit on `feat/phase-3-ci-cleanup`:
- Commit message includes which TEST_ARCHITECTURE.md gap it closes
- Each PR runs `uv run ruff check .` and the affected test subset
- Push after each commit; sibling coordination via `git fetch origin` + ruff clean

### Phase 1 Definition of Done

- [ ] All 35h of remaining tasks completed
- [ ] Coverage gate bumped 35% → 40% in pyproject.toml
- [ ] ruff clean, format clean
- [ ] `gen_route_smoke.py` generates at least 50 tests (proof of approach)
- [ ] At least 5 `_seed_*` migrated (proof of approach)
- [ ] At least 5 tests use flows.py helpers (proof of approach)
- [ ] CI green with `--dist=loadscope`
- [ ] `state/test-coverage-2026-10-04.json` snapshot committed (compare later)

---

## Phase 2 — Refactor foundations (2 weeks, 44h, 35% → 50%)

**Goal:** Coverage floor to 50%; deep refactors that pay off across the rest of the journey.

### Pillar B1 — Single seed registry (8h)

**Hat:** Code Quality
**Outcome:** -600 LOC duplication across 35 files

| Sub-task | Effort |
|---|---|
| Build `tests/seeders.py` with all qseed scenarios + edge-case seeds | 4h |
| Migrate the 30 duplicated `_seed_*` helpers to `qseed()` calls | 3h |
| Delete the private helpers; verify no behavior change | 1h |

### Pillar B3 — Edge-case factories (6h)

**Hat:** Code Quality
**Outcome:** -200 LOC factory-calling boilerplate

| Sub-task | Effort |
|---|---|
| Add builder pattern: `make_recipe().with_n_lines(5).with_low_margin().build()` | 3h |
| Add factory traits: `make_ingredient(traits={"low_stock": True})` | 2h |
| Migrate 10 tests to use the new builder API | 1h |

### Pillar C4 — Extract services from top 10 routers (24h)

**Hat:** QA Engineer (refactor lead) + Domain SME (review)
**Outcome:** +30 unit tests, coverage +10%

**Targets** (the 10 biggest routers):
| Router | Endpoints | Test file today | Extract effort |
|---|---|---|---|
| `pedidos.py` | 15 | partial (4 files) | 3h |
| `produccion.py` | 13 | partial (3 files) | 3h |
| `sales.py` | 12 | partial (1 file) | 3h |
| `inventory.py` | 24 | none | 6h |
| `customers.py` | 20 | none | 4h |
| `reports.py` | 21 | partial (1 file) | 3h |
| `recipes.py` | 14 | partial (1 file) | 2h |
| `suscripciones.py` | 8 | none | 1h |

**Extract pattern:** move business logic from `@router.post` body into `app/services/<name>.py:<func>`; router becomes a thin shim.

### Pillar A2 — Model invariant generator (16h)

**Hat:** QA Engineer
**Outcome:** +200 property tests

| Sub-task | Effort |
|---|---|
| Build `tests/test_model_invariants.py` that introspects SQLAlchemy models | 6h |
| Generate `@given` tests for non-negative int columns | 4h |
| Generate `@given` tests for enum columns | 3h |
| Generate `@given` tests for foreign key cascades | 3h |

### Phase 2 Definition of Done

- [ ] Coverage gate 40% → 50%
- [ ] All 30 _seed_* helpers migrated
- [ ] Builder pattern live in factories.py
- [ ] Top 10 routers refactored; services live
- [ ] Model invariant tests passing
- [ ] ruff clean
- [ ] Doc: phase 2 brief doc shipped

---

## Phase 3 — The 80% push pt 1 (3 weeks, 34h, 50% → 65%)

**Goal:** Coverage 50% → 65%. Test time 15m → 6m. +700 tests.

### Pillar A4 — Template-render coverage (4h)

**Hat:** QA Engineer
**Outcome:** +500 tests, coverage +10%

| Sub-task | Effort |
|---|---|
| Discover every template from `app/templates/**/*.html` | 1h |
| Build `tests/test_template_render_auto.py` that renders each with fixture context | 2h |
| Assert no `{{Undefined }}` exceptions | 1h |

### Pillar A3 — CRUD roundtrip generator (4h)

**Hat:** QA Engineer
**Outcome:** +500 tests

| Sub-task | Effort |
|---|---|
| Find all 20 CRUD endpoints (POST/PUT/DELETE with {id}) | 1h |
| Build generator that produces a roundtrip test per endpoint | 2h |
| Validate against the 20 endpoints | 1h |

### Pillar C3 — Page Object expansion (4h)

**Hat:** A11y Reviewer
**Outcome:** -200 LOC browser tests

| Sub-task | Effort |
|---|---|
| Build 8 Page Objects: RecipeDetail, ProductDetail, ClienteDetalle, PedidoList/Detail/New, Inventory, Merma, Reports | 3h |
| Migrate 5 browser tests to use them | 1h |

### Pillar D1 — Module-scoped fixtures with rollback (16h)

**Hat:** Performance Engineer
**Outcome:** Test time 15m → 6m

| Sub-task | Effort |
|---|---|
| Audit which tests need isolation vs shared setup | 4h |
| Build module-scoped `qseed()` variant + per-test rollback | 6h |
| Migrate 50 read-only tests to module scope | 4h |
| Measure perf: pytest time --durations=20 | 2h |

### Pillar D5 — Property test expansion (6h)

**Hat:** QA Engineer
**Outcome:** +200 property tests

| Sub-task | Effort |
|---|---|
| Recipe costing properties | 2h |
| Date/timezone math properties | 2h |
| Report aggregation properties | 2h |

### Phase 3 Definition of Done

- [ ] Coverage gate 50% → 65%
- [ ] Test time measured < 8 min on -n 2
- [ ] 8 new Page Objects live
- [ ] All templates render-tested
- [ ] Property tests for costing + dates + reports
- [ ] ruff clean
- [ ] Doc: phase 3 brief doc shipped

---

## Phase 4 — The 80% push pt 2 (4+ weeks, 48h, 65% → 80%)

**Goal:** Coverage 65% → 80%. AGENTS.md target hit.

### Pillar C4 (continued) — Service extraction, remaining 20 routers (40h)

**Hat:** QA Engineer + Domain SME
**Outcome:** +60 unit tests, coverage +15%

| Sub-task | Effort |
|---|---|
| Service extraction for the next 20 routers | 30h |
| Unit tests for each new service | 8h |
| Router regression: integration test still passes | 2h |

### Pillar B4 — Hand-rolled vs polyfactory decision (4h)

**Hat:** Code Quality
**Outcome:** Adopt or reject polyfactory

| Sub-task | Effort |
|---|---|
| Pilot polyfactory on 2 value objects (Address, Money) | 2h |
| Decide: keep hand-rolled for entities, polyfactory for value objects? | 1h |
| If polyfactory: migrate 5 entity factories | 1h |

### Pillar C2 — Audit log invariant coverage (4h)

**Hat:** Security Reviewer
**Outcome:** +30 audit_log tests

| Sub-task | Effort |
|---|---|
| Audit every state-changing route writes to audit_log | 2h |
| Add property tests: state change → log row | 1h |
| Add regression: missing log = test failure | 1h |

### Phase 4 Definition of Done

- [ ] Coverage gate 65% → 80%
- [ ] All 30 routers extracted to services
- [ ] Polyfactory decision documented
- [ ] Audit log invariant library complete
- [ ] ruff clean
- [ ] AGENTS.md §Testing rule 86 satisfied (80% gate)
- [ ] Celebration PR

---

## Hat assignment matrix

Which hat leads which phase's tasks:

```
Phase          |  QA  | Perf | Sec | Migr | A11y | SRE | Loc | Anly | Oper | Refact
---------------|---------|------|-----|------|------|-----|-----|------|------|-------
1.1 gen_route_smoke| ●LEAD |      |      |     |      |     |     |      |      |
1.2 _seed_* migrate|      |      |      |     |      |     |     |      |      | ●LEAD
1.3 flows fixtures | ●LEAD |      |      |     |      |     |     |      |      |
1.4 deploy script|        |      |      |     |      |     |     |      | ●LEAD |
1.5 backup drill |        |      |      |     |      | ●LEAD|     |      |      |
1.6 copy audit   |        |      |      |     |      |     | ●LEAD|     |      |
1.7 WCAG audit   |        |      |      |     | ●LEAD|     |     |      |      |
1.8 profile       |        | ●LEAD|     |     |      |     |     |      |      |
1.9 csrf audit   |        |      | ●LEAD|     |      |     |     |      |      |
1.10 migrations   |        |      |      | ●LEAD|     |     |     |      |      |
2.1 single seed   |        |      |      |     |      |     |     |      |      | ●LEAD
2.2 edge factories|        |      |      |     |      |     |     |      |      | ●LEAD
2.3 services top10| ●LEAD  |      |      |     |      |      |     |      |      |
2.4 model props   | ●LEAD  |      |      |     |      |     |     |      |      |
3.1+roundtrip gen | ●LEAD  |      |      |     |      |     |     |      |      |
3.2 page objects  |        |      |      |     | ●LEAD|     |     |      |      |
3.3 module scope  |        | ●LEAD|     |     |      |     |     |      |      |
3.4 prop text    | ●LEAD  |      |      |     |      |     |     |      |      |
4.1 services rest | ●LEAD  |      |      |     |      |     |     |      |      |
4.2 polyfactory   |        |      |      |     |      |     |     |      |      | ●LEAD
4.3 audit log     |        |      | ●LEAD|     |      |     |     |      |      |
```

Each phase has 5-7 hats active. No single hat burns out.

---

## The parallel-execution pattern

Within any week, ~3 hats run in parallel:

```
Week 1 (Phase 1):
  Hat A (QA Engineer): tasks 1.1, 1.3, 1.11 ✅
  Hat B (Code Quality): tasks 1.2, 1.12 ✅
  Hat C (Operator): task 1.4
  Hat D (SRE): task 1.5
  Hat E (Localization): task 1.6
  Hat F (A11y): task 1.7
  Hat G (Performance): tasks 1.8, 1.13 ✅
  Hat H (Security): task 1.9
  Hat I (Migration): task 1.10
  Hat J (Doc Curator): task 1.14 ✅

PR cadence: ~3 PRs/week per hat, ~10-15 PRs/week total.
```

---

## Dependency map (what blocks what)

```
Phase 1.1 (gen_route_smoke) → Phase 2.x (uses it to validate Phase 2 work)
Phase 1.2 (seed migration) → Phase 2.1 (single seed registry depends on this analysis)
Phase 1.3 (flows fixtures) → Phase 2.2 (builder pattern on factories.py)
Phase 1.4 (deploy test) → Phase 4 (deploy safe to use for service extraction deploys)
Phase 1.5 (backup drill) → Phase 2.3 (services can use backups before destructive ops)
Phase 1.8 (analytics profile) → Phase 2.x (use them in Phase 3 model properties)
Phase 1.10 (migrations done) → Phase 2.3 (services depend on stable schema)

Critical path: 1.1 → 2.3 → 3.3 → 4.1 (the "code path" most of the work flows through)
Optional: 1.4, 1.5, 1.7, 1.9 can be done in any week
```

---

## Tracking

### Per-PR tracking

Each PR has:
1. **Title:** `<scope>: <action> — closes <gap>`
2. **Body:** which TEST_ARCHITECTURE.md gap it closes
3. **Coverage delta:** before/after for the affected modules
4. **Sibling check:** `git fetch origin` + ruff clean before push

### Per-phase tracking

Each phase has:
1. **Coverage target** (e.g., 40% for Phase 1)
2. **Definition of Done** (above)
3. **Phase brief doc** in `docs/operations/2026-10-XX-phase-N-brief.md`

### Per-sprint tracking (weekly)

Monday: snapshot last week's work + plan next week.
Friday: ship any incomplete work to PR #46 or a follow-up PR.

---

## The "always test" indicator lives at `state/test-coverage.json`:

```json
{
  "schema": "test-coverage-v1",
  "snapshot_date": "2026-10-04T23:50:00Z",
  "current": {
    "coverage_pct": 35,
    "tests": 7900,
    "files": 484,
    "loc": 165000,
    "test_runtime_min": 15
  },
  "phase_targets": [
    {"phase": 1, "week": 1, "coverage_pct": 40, "runtime_min": 12},
    {"phase": 2, "week": 3, "coverage_pct": 50, "runtime_min": 10},
    {"phase": 3, "week": 6, "coverage_pct": 65, "runtime_min": 8},
    {"phase": 4, "week": 10, "coverage_pct": 80, "runtime_min": 6}
  ]
}
```

This file gets committed each phase. Future sessions diff against it to track progress.

---

## Risks + mitigations

### Risk 1 — Sibling session lands conflicting work

**Likelihood:** high (sibling landed 4 commits this session)
**Mitigation:** `git fetch origin` before every push; rebase if divergence; ruff clean before push. **Always run the affected tests locally** if test cost < 30s.

### Risk 2 — Coverage gate fails after a refactor

**Likelihood:** medium (Phase 2 service extraction may drop coverage temporarily)
**Mitigation:** Add new unit tests in the same PR as the refactor. Don't bump the gate in `pyproject.toml` until the PR is green.

### Risk 3 — Test runtime regression

**Likelihood:** medium (Phase 3 module-scoped may surface isolation leaks)
**Mitigation:** Profile first with `pytest --durations=20`. Module scope only on tests that don't need isolation.

### Risk 4 — Generated tests are too shallow

**Likelihood:** high (a 200-test smoke PR adds 200 weak tests, not 200 strong ones)
**Mitigation:** Generated tests have explicit quality bar: each must assert non-empty body + status in (200, 303, 422). Hand-written invariants supplement them.

### Risk 5 — Operator can't run all tests in 240s

**Likelihood:** high (sandbox budget is 240s; full suite is 15+ min)
**Mitigation:** Use `pytest --co` to validate the architecture; run subsets per env; the CI is the final source of truth.

---

## What this doc is NOT

- **Not** a backlog (use `IMPROVEMENT_BACKLOG.md`)
- **Not** a test plan (use `docs/qa/round1-qa-plan.md`)
- **Not** the docs themselves (the 3 sister docs are the docs)

This is the **execution plan**: who does what, in what order, with what dependencies.

---

## Open questions

1. **Single owner or shared?** — Default: primary hat owns, others review.
2. **Cadence per hat** — Each hat should aim for 1 PR/week.
3. **Coverage bump timing** — Bump `--cov-fail-under` after each phase, not within.
5. **Sibling integration** — When sibling lands work, incorporate it into the next PR's plan.

---

## TL;DR

| What | When | Who |
|---|---|---|
| Phase 1 quick wins (11 tasks, 35h) | Week 1 | 9 hats in parallel |
| Phase 2 refactor foundations (44h) | Weeks 2-3 | 3 hats (QA, Code Quality, Refactorer) |
| Phase 3 coverage push (34h) | Weeks 4-6 | 4 hats (QA, Performance, A11y, Code Quality) |
| Phase 4 final push (48h) | Weeks 7-10 | 3 hats (QA, Security, Code Quality) |
| **Total** | **10 weeks** | **All 12 hats rotating** |

**Outcome: 35% → 80% coverage (AGENTS.md target). +2,000 tests. -1,500 LOC. Test time 15m → 6m.**

---

## Refs

- `docs/TEST_ARCHITECTURE.md` — 5 levels × 8 domains (the WHAT)
- `docs/operations/2026-10-04-qa-hats-playbook.md` — 12 hats × wishlists (the WHO)
- `docs/operations/2026-10-04-test-infrastructure-upgrade.md` — 4 pillars (the HOW)
- `docs/operations/2026-10-04-test-infra-one-pager.md` — same in 1 page
- `docs/plans/2026-10-01-phase14-coverage-strategy.md` — coverage growth plan (subsumed by this)
- `docs/plans/2026-09-25-test-improvement-complete-catalog.md` — 309-line catalog
- `docs/plans/2026-09-25-test-suite-e2e-strategy.md` — E2E strategy
- `docs/plans/2026-09-25-e2e-gap-analysis.md` — E2E gap analysis
- `scripts/inventory_seed_helpers.py` — seed inventory (Phase 1 input)
- `tests/_lib/invariants.py` — invariant library (Pillar C2)
- `tests/factories.py` — entity factories (Pillar B)
- `tests/flows.py` — HTTP-level helpers (Pillar C1)
- `AGENTS.md` — repo build rules (especially §Testing rule 86)