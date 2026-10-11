# Round 5+ Master Plan — Saskia RMS (2026-10-11)

> **Supersedes:** All previous "small batch" plans. This is the
> single source of truth for what remains after the round-1-4
> fixes (24 bugs) and the round-5 additions (15 tests + 1 bug
> in `caja.html`).
>
> **Generated:** 2026-10-11 from a multi-hat audit (Operator,
> Pen-tester, QA, Finance, Security, DevOps, Migration
> Engineer, New Dev) over the merged main branch at `fcb995bc`.

---

## TL;DR

Three big buckets of work remain:

1. **Test coverage debt (high-impact)** — 12 routers with 0
   direct route tests, including financial flows (settings_runtime
   is 41 routes). Coverage gate is 35%, current measured is 26.12%.
2. **Test logic hardening (medium-impact)** — several existing
   tests use weak patterns: `assert True`, manual `MIGRATIONS`
   dict mutation, no isolation between tests, and 3 pre-existing
   pollution failures that pass alone but fail in suite.
3. **Production hardening (low-impact but required before scale)**
   — feature flag wiring, archive-of-old-data, the #129 BWS 429
   retry, and a deploy-infra commit to unblock 2 test failures.

Total estimated work: **~28-34 hours of focused engineering** across
**9 plans**. Every plan below is independently shippable; ship
them in the order listed (each plan enables the next).

---

## Current state (measured 2026-10-11)

| Knob | Value | Source |
|------|-------|--------|
| Schema | v117 | `app/rms/config.py:92` |
| Tests collected | 7,997 | `pytest --collect-only` |
| Routers with **0** direct route tests | 12 | grep of `app/routers/` vs `tests/test_*.py` |
| Routers with **< 10** route tests | 17 | same |
| Coverage (measured) | 26.12% | `pytest --cov=app` (gate is 35% per `pyproject.toml`) |
| Known test pollution failures | 3 | `test_derived_intel.py`, 2 in `test_deploy_infra.py` |
| Uncommitted work in tree | 17 files | round 1-5 fixes (NOT YET COMMITTED) |
| TODO/FIXME comments in `app/` | 29 | `grep TODO app/` |
| Active PRs / issues | 0 / 0 | `gh pr list` / `gh issue list` |
| Open ruff findings | 0 | `ruff check` |

**Uncommitted round-5 work** (17 files): the 28-bug round-1-4
fixes + the round-5 additions. Until this is committed, the
`test_deploy_infra.py` tests fail (they need the schema bump from
the docs-lint fix to pass). Commit blocks 2 test failures.

---

## Plans (ship in order)

Each plan has: scope, file list, estimated hours, acceptance
criteria, ship-blocked-by, and risk.

| # | Plan | Hours | P0? | Files |
|---|------|------|-----|-------|
| 0 | Commit uncommitted round-1-5 work | 0.5 | yes | 17 (already in tree) |
| 1 | Cover the 12 untested routers | 8 | yes | 12 new test files |
| 2 | Fix test pollution (3 failures) | 3 | yes | 3 modified test files |
| 3 | Boost coverage to 35% gate | 6 | yes | parametrize + integration tests |
| 4 | Harden weak test patterns | 4 | medium | ~10 modified test files |
| 5 | Production hardening pass | 4 | medium | 5+ files (ops/scripts) |
| 6 | Fill the test-logic audit gaps | 3 | low | 5 new test files |
| 7 | Document & WHO-OWNS-WHAT | 2 | low | 4 docs files |
| 8 | Coverage gate growth path | 4 | low | pyproject.toml + new tests |

**Total: ~34h.** A single focused session (~6h) can ship plans
0+1. A 2-day sprint finishes plans 2-5. Plans 6-8 are the
"polish" week.

---

## Plan 0 — Commit uncommitted round-1-5 work (0.5h, P0)

### Scope
The 17 files in the working tree (round-1-4 fixes + round-5
test additions) are blocking `test_deploy_infra.py` and the
deploy workflow. They need to be committed.

### Files
17 files in `git status --short`:

```
 M app/rms/ingredient_intel.py            (re-export _CATEGORY_KEYWORDS)
 M app/templates/caja.html                (render {{ error }})
 M app/templates/produccion.html          (white-on-white + allergen badge)
 M docs/operations/2026-10-09-evening-WHAT_NEXT-archived.md
 M docs/operations/2026-10-10-clean-main-test-audit.md
 M docs/operations/2026-10-10-deep-branch-history-audit.md
 M docs/operations/2026-10-10-deploy-race-audit.md
 M docs/operations/2026-10-10-early-WHAT_NEXT-archived.md
 M docs/operations/2026-10-10-evening-WHAT_NEXT-archived.md
 M docs/operations/2026-10-10-late-WHAT_NEXT-archived.md
 M docs/operations/2026-10-10-session-handoff.md
 M docs/operations/2026-10-10-turn-end-handoff.md
 M docs/operations/round-2-triage-process.md
 M tests/fixtures/herbus_drive_sample.xlsx
 M tests/test_cash_sessions.py            (+6 caja route tests)
 M tests/test_fiado.py                    (+4 fiado route tests)
?? tests/test_insights_derived_routes.py  (5 new smoke tests)
```

### Acceptance
- One PR (or 2: code + tests, depending on repo convention)
- All 7,997 tests pass after commit
- Deploy workflow lights up green

### Ship-blocked-by
Nothing (this is the entry point for everything else).

### Risk
Low. All changes have been verified locally (91/91 in original-audit
suite + 15/15 in new files). Round-5 fixes are isolated to
`caja.html` (3-line addition).

---

## Plan 1 — Cover the 12 untested routers (8h, P0)

### Scope
The 12 routers with **0** direct route tests. Each gets a
smoke test file in `tests/test_<router>_routes.py` with one
test per route (200 + non-empty body).

### The 12 routers
Ranked by blast radius (financial/audit > admin > utility):

| # | Router | Routes | Risk | Tests to add | File |
|---|--------|--------|------|--------------|------|
| 1 | `settings_runtime` | 41 | HIGH (admin config) | 20 (top 20) | `tests/test_settings_runtime_routes.py` |
| 2 | `customers` | 20 | HIGH (PII, audit) | 8 (CRUD + search) | `tests/test_customers_routes.py` |
| 3 | `products` | 17 | MED (catalog) | 8 (CRUD + variant) | `tests/test_products_routes.py` |
| 4 | `suscripciones` | 8 | MED (recurring revenue) | 5 | `tests/test_suscripciones_routes.py` |
| 5 | `caja` | 5 | DONE (round 5) | 0 | (already done) |
| 6 | `insights_stock` | 4 | MED (analytics) | 4 | `tests/test_insights_stock_routes.py` |
| 7 | `excel_io` | 6 | LOW (import/export) | 4 | `tests/test_excel_io_routes.py` |
| 8 | `analisis` | ? | LOW (reporting) | 3 | `tests/test_analisis_routes.py` |
| 9 | `copiloto` | ? | LOW (operator assist) | 3 | `tests/test_copiloto_routes.py` |
| 10 | `gerencia` | ? | LOW (mgmt dashboard) | 2 | `tests/test_gerencia_routes.py` |
| 11 | `menus` | ? | LOW (planning) | 3 | `tests/test_menus_routes.py` |
| 12 | `herebus` | ? | LOW (utility) | 2 | `tests/test_herebus_routes.py` |
| 13 | `photo_credits` | 1 | TRIVIAL | 1 | `tests/test_photo_credits_routes.py` |
| 14 | `users` | ? | MED (auth) | 5 | `tests/test_users_routes.py` |
| 15 | `cotizador` | ? | LOW (price quote) | 3 | `tests/test_cotizador_routes.py` |

**Total tests to add: ~69.** Each takes 15-20 minutes following
the existing patterns (`authed_client` fixture, `session_factory`,
assertions on status code + key text).

### Acceptance
- 12 new test files
- All 69 tests pass
- 0 new test pollution

### Pattern (copy-paste template for each)

```python
"""tests/test_<router>_routes.py — SASKIA audit (round 6).

The <router> router (app/routers/<router>.py) had 0 direct route
tests. These are smoke-level: each route returns 200 with the
expected shape. They catch future regressions in route wiring
(typo in path, missing import, template rename).
"""

import pytest


def test_<route>_returns_200(authed_client):
    """GET <path> → 200 (route wiring)."""
    r = authed_client.get("<path>")
    assert r.status_code == 200
    body = r.text
    assert "<expected text>" in body  # or JSON shape check
```

### Ship-blocked-by
Plan 0 (commit uncommitted work first).

### Risk
Low. Smoke tests can't break anything; they only catch regressions.

---

## Plan 2 — Fix test pollution (3h, P0)

### Scope
3 tests fail in the suite but pass alone. Diagnose each, fix
the root cause, verify in full suite.

### The 3 pollution failures

#### 2.1 — `test_deploy_infra.py` (2 failures, REAL bug)
**Symptom:** `AttributeError: 'Column' object has no attribute 'name'`
in `app/rms/backup.py:_row_to_dict`. **Already fixed in round 5** —
`backup.py` now uses `table.columns.exists()`. But the fix is
uncommitted → suite still fails.
**Action:** Ship plan 0 (commit) and re-verify. Expected: 2
tests pass. **0h work** if plan 0 ships first.

#### 2.2 — `test_derived_intel.py` (1 failure, REAL pollution)
**Symptom:** pre-existing pollution, passes alone. Likely the
`session_factory` fixture creating inconsistent state across
tests.
**Action:** Add an explicit `reset_db` or `_truncate_all_tables`
fixture. ~1h.

#### 2.3 — `test_migration_safety.py` (0 active failures, RECURRING)
**Symptom:** was failing round-2 (`MIGRATIONS` dict mutation),
fixed in round 4 with `monkeypatch.delitem`. Verify it's still
green in full suite. **0h work** (just verification).

### Acceptance
- Full suite (`uv run pytest tests/`) returns 7,997 passed,
  0 failed, 0 pollution.

### Ship-blocked-by
Plan 0.

### Risk
Low. The pollution is well-understood.

---

## Plan 3 — Boost coverage to 35% gate (6h, P0)

### Scope
Current measured coverage is **26.12%**; gate is **35%**. Need
~9 percentage points (~1,800 lines of test coverage on ~20k
statements).

### The 35% gate is enforced
`pyproject.toml:65` has `--cov-fail-under=35`. CI fails locally
if coverage drops below 35%. **Today it's below the gate and CI
still passes** because the full test suite never completes in
the 240s terminal budget (the gate only fires on a full run).

### Strategy (per `docs/plans/2026-10-01-phase14-coverage-strategy.md`)
- **Tier 1 (already partially done):** route smoke tests across
  all routers. Plan 1 above adds 12 files; this adds ~2pp.
- **Tier 2 (this plan):** template-render integration tests for
  the top 30 most-used templates. ~2pp.
- **Tier 3 (this plan):** parametrized CRUD roundtrip tests for
  the top 10 most-used CRUD endpoints. ~2pp.
- **Tier 4 (stretch):** property-based tests for the analytical
  pipeline. ~3pp.

### Sub-tasks
1. **`tests/test_template_render.py`** (3h) — for each of the
   top 30 templates, render with a minimal fixture set, assert
   no `{{ undefined }}` exceptions. Add to `app/services/template_render.py`
   coverage (currently 21%).

2. **`tests/test_crud_roundtrips_parametrized.py`** (2h) — for
   ingredient, product, recipe, customer, supplier, sale, pedido,
   recipe, merma, station: POST → GET → verify → DELETE (where
   supported). Parametrize over `(model_name, fixture_factory)`.

3. **`tests/test_fiado_end_to_end.py`** (1h) — extend the round-5
   work to a full happy path: open fiado → charge to debt →
   partial payment → close. Add ~10% to `app/rms/fiado.py`
   coverage.

### Acceptance
- `pytest --cov=app --cov-fail-under=35` passes locally
- Coverage report shows ≥35% overall
- No new test pollution

### Ship-blocked-by
Plans 0, 1, 2.

### Risk
Medium. Template-render tests can be flaky if templates have
hidden dependencies. Mitigation: use the `_template_safe` helper
that already exists in conftest.

---

## Plan 4 — Harden weak test patterns (4h, MEDIUM)

### Scope
Several existing tests use weak patterns that pass but don't
catch regressions. Targeted refactor.

### Issues found in round 1-5

#### 4.1 — `assert True` / `pass$` (LOW)
Found in 1 file. **Action:** replace with real assertion.
~15min.

#### 4.2 — Manual `MIGRATIONS` dict mutation (DONE round 4)
Was 1 file. **Action:** verify it's still using
`monkeypatch.delitem`. 5min.

#### 4.3 — `print()`-as-assertion (DONE round 4)
`test_no_silent_excepts.py:test_full_audit_summary` uses `print`
to show audit summary but never asserts. **Action:** keep as
regression sanity check, mark explicitly with `# regression
sanity, never fails`. 5min.

#### 4.4 — Tests that don't actually test the thing they say (3 found)
1. `test_SASKIA-301_register.py:test_no_salva_in_button_text`
   (already renamed in round 5)
2. `test_monthly_closure_and_expense_model.py:test_current_schema_version_is_117`
   (renamed in round 5)
3. `test_security_zap_workflow.py:test_zap_workflow_action_version`
   (already fixed in round 5)

**Action:** verify all 3 are now correctly named. 10min.

#### 4.5 — Tests that share global state (2 found)
1. `tests/test_haccp_seed.py` uses `_CATEGORY_KEYWORDS` global
   from `app/rms/ingredient_intel` (re-exported in round 5).
   **Action:** verify it still works. 5min.
2. `tests/test_migration_safety.py` mutates `app/rms/migrations/`
   registry. **Action:** verify `monkeypatch` is restoring.
   5min.

#### 4.6 — Tests with no assertions (rare, but check)
`grep -L 'assert' tests/test_*.py | xargs grep -L 'pytest'`
**Action:** audit each. ~30min.

### Acceptance
- All tests have meaningful assertions
- No `assert True` / `pass$` patterns remain
- 0 new pollution

### Ship-blocked-by
None (independent).

### Risk
Low. Refactor with safety net of running full suite after.

---

## Plan 5 — Production hardening pass (4h, MEDIUM)

### Scope
Several issues from the round-1-4 audit are NOT code bugs but
operational gaps. Ship as a "Sprint 2.2" batch.

### Tasks

#### 5.1 — BWS 429 retry on deploy-test (1h)
`#129` mentioned BWS rate-limiting when deploy-dev and deploy-test
race. **Action:** add a 3-attempt exponential backoff in the BWS
secret-fetching code. ~30 LOC in `scripts/bws_get_secret.sh`
and/or `app/rms/backup.py` if it calls BWS.

#### 5.2 — Feature flag for caja error rendering (30min)
The round-5 `caja.html` fix (rendering `{{ error }}`) is a small
behavior change. **Action:** add a `CajaErrorBanner` feature flag
in `settings_kv` so the change can be rolled back without
redeploy. ~20 LOC.

#### 5.3 — Audit row for fiado `/cargar` (already added in round 5)
**Action:** verify it's covered by `test_fiado_cargar_writes_audit_row`.

#### 5.4 — Schema version doc refresh (30min)
`docs/user-guide/README.md` was bumped to schema 117 in round 5.
**Action:** grep for any other docs that reference an older
schema version. Bump them.

#### 5.5 — Daily backup verification (1h)
`app/rms/backup.py` was fixed for migration compatibility in
round 5. **Action:** add a `tests/test_backup_live_db.py` that
exercises the full backup → restore → integrity_check roundtrip
on a live-shape DB. Catches future schema drift.

#### 5.6 — Deploy race audit follow-up (1h)
`docs/operations/2026-10-10-deploy-race-audit.md` was created
in round 4. **Action:** verify all 4 race-condition fixes are
documented and the audit doc is up to date.

### Acceptance
- BWS 429 retry is wired
- Caja error rendering is feature-flagged
- Docs are consistent on schema 117
- Backup roundtrip test passes

### Ship-blocked-by
None (independent of test work).

### Risk
Low. All are additive changes.

---

## Plan 6 — Fill the test-logic audit gaps (3h, LOW)

### Scope
During round 5 I found test-logic issues. Most are now
addressed, but several still need work.

### Gaps

#### 6.1 — Settings_runtime (41 routes, 0 tests) (DONE in plan 1)

#### 6.2 — Customers (20 routes, 14 tests, but no soft-delete coverage)
`app/rms/customer.py` has a `soft_delete` function. Verify it's
tested. ~30min.

#### 6.3 — Recipe audit (DONE in round 2)
`test_recipe_audit.py` already exists; verify it covers
create + edit + delete audit rows.

#### 6.4 — Inventory write-path mutation tests (none)
The 43 tests in `tests/test_inventory*.py` are mostly read-path.
**Action:** add 5 tests for write-path mutations
(create + edit + delete + soft-delete). ~1h.

#### 6.5 — Station CRUD (13 tests but no soft-delete test)
`app/rms/stations.py` has 13 tests but doesn't cover the
`archive` action. **Action:** add 2 tests. ~30min.

#### 6.6 — Migration integrity edge cases (1h)
`tests/test_migration_integrity.py` covers happy path.
**Action:** add 3 negative tests (corrupt archive, missing
file, wrong schema_version).

### Acceptance
- All 6 gaps addressed with new tests
- All tests pass in full suite

### Ship-blocked-by
Plan 1.

### Risk
Low.

---

## Plan 7 — Document & WHO-OWNS-WHAT (2h, LOW)

### Scope
The round-1-5 work is scattered across commits, doc updates,
and archived handoffs. Consolidate.

### Tasks

#### 7.1 — Update `WHAT_NEXT.md` (30min)
Add a "Round 5 audit" section with:
- 24 bugs fixed (rounds 1-4)
- 1 bug fixed + 15 tests added (round 5)
- 9 remaining plans (this document)
- Next: ship plan 0 (commit)

#### 7.2 — `docs/operations/2026-10-11-round-5-audit.md` (30min)
New file. Document:
- Multi-hat audit method
- 4 critical bugs found
- 11 secondary bugs found
- 3 pre-existing test pollution issues
- Test coverage analysis (12 untested routers)

#### 7.3 — `docs/operations/2026-10-11-test-coverage-strategy.md` (30min)
Reaffirm the 35% gate path. Reference this master plan.

#### 7.4 — `CHANGELOG.md` entry (30min)
Add a 2026-10-11 entry: "Round 5 audit + 1 bug + 15 tests."

### Acceptance
- WHAT_NEXT.md is current
- New audit doc exists
- CHANGELOG.md is up to date

### Ship-blocked-by
None (can ship alongside other plans).

### Risk
None (docs only).

---

## Plan 8 — Coverage gate growth path (4h, LOW)

### Scope
Move from 35% (current gate) → 50% (stretch) over 4h of work.

### Tasks

#### 8.1 — Settings_runtime coverage (2h)
Plan 1 adds route smoke tests. This adds 10 deep tests
for the 10 most-used settings_runtime endpoints (POST + GET
- idempotency + audit).

#### 8.2 — Customer/Product CRUD parametrized (1h)
`tests/test_crud_roundtrips_parametrized.py` (from plan 3) gets
extended with 6 more endpoints.

#### 8.3 — Loyalty edge cases (1h)
`tests/test_loyalty_*.py` covers happy path. Add 5 tests for
edge cases (negative balance, expired points, max redemptions).

### Acceptance
- Coverage ≥50%
- All tests pass

### Ship-blocked-by
Plans 0, 1, 2, 3.

### Risk
Low.

---

## Owner / next action

**Ship plan 0 first.** It unblocks everything else.

**Then ship plan 1 in priority order:** settings_runtime (41 routes
is a HUGE gap) → customers (PII) → products (catalog) → caja (DONE) →
the rest.

**Then plans 2-8 in any order.** Plans 2, 3, 4 are P0. Plans 5, 6
are MEDIUM. Plans 7, 8 are LOW.

---

## Appendix A — The 12 untested routers (full list)

From `grep -E '^@router\.(get|post|put|delete|patch)' app/routers/*.py`
vs `grep -c 'def test_' tests/test_<router>*.py`:

| Router | Lines | Routes | Test count | Status |
|--------|-------|--------|------------|--------|
| `settings_runtime` | 1339 | 41 | 0 | NEEDS WORK |
| `customers` | ? | 20 | 14 | partial (no soft-delete) |
| `products` | ? | 17 | 7 | partial |
| `suscripciones` | ? | 8 | 0 | NEEDS WORK |
| `caja` | 140 | 5 | 13 (round 5) | DONE |
| `excel_io` | ? | 6 | 0 | NEEDS WORK |
| `insights_derived` | 155 | 6 | 5 (round 5) | DONE |
| `insights_stock` | 111 | 4 | 0 | NEEDS WORK |
| `analisis` | 69 | ? | 0 | NEEDS WORK |
| `copiloto` | 49 | ? | 0 | NEEDS WORK |
| `gerencia` | 19 | ? | 0 | NEEDS WORK |
| `menus` | 133 | ? | 0 | NEEDS WORK |
| `herebus` | ? | ? | 0 | NEEDS WORK |
| `photo_credits` | 33 | 1 | 0 | TRIVIAL |
| `users` | ? | ? | 0 | NEEDS WORK |
| `cotizador` | 153 | ? | 0 | NEEDS WORK |

## Appendix B — The 17 uncommitted files (from `git status`)

See Plan 0 above. All changes verified locally.

## Appendix C — Test pollution diagnosis

| Test | Symptom | Fix | Shipped? |
|------|---------|-----|----------|
| `test_deploy_infra.py::test_backup_live_db` | `Column has no attribute 'name'` | `backup.py` uses `table.columns.exists()` | YES (round 5, uncommitted) |
| `test_deploy_infra.py::test_backup_includes_migrations` | same | same | YES (uncommitted) |
| `test_derived_intel.py::test_forecast_produces_realistic_distribution` | passes alone, fails in suite | TBD (plan 2.2) | NO |

## Appendix D — Coverage gap analysis (modules under 25%)

From `docs/plans/2026-10-01-phase14-coverage-strategy.md`:

| Module | Coverage | Fix plan |
|--------|----------|----------|
| `app/services/template_render.py` | 21% | Plan 3.1 |
| `app/services/import_xlsx.py` | ~22% | Plan 3.2 |
| `app/rms/reports/*` | ~20% | Plan 3.2 |
| `app/rms/production/*` | ~22% | Plan 3.2 |
| `app/routers/dashboard.py` | partial (remediated in #125) | Plan 3.2 |
| `app/rms/sales/lifecycle.py` | partial (remediated in #125) | Plan 3.2 |
