# SASKIA-320: tests auditing a foreign checkout (/opt/data/work/saskia-app)

**Date:** 2026-10-08
**Owner:** Hermes (autonomous)
**Status:** shipped

## Symptom

Latest main's `test` job is red: `test_routers_require_auth` (4), `test_profitability_sales_split` (3), plus a wider cluster that only passes because tests read a *stale foreign tree*.

## Root cause

20+ test files hardcoded `/opt/data/work/saskia-app` — a separate, stale checkout on Ivan's host — and audited THAT tree instead of the repo under test. Consequences:

- Tests could pass while the real tree violated the contract (and vice versa) — pure anti-rule #20 violation (host-path dependence).
- The profitability "shim" tests passed against the stale tree's shim while main's `costing.py` is the live 776-line module; the `profitability/` + `sales/` packages coexist as parallel copies (duplication left by merge-repair 72ee3509).
- The auth-gate audit flagged `demo.py`, `photo_credits.py`, `stations.py` — two of which are deliberate designs, one a real gap.

## Fix

1. **REPO_ROOT** in `tests/conftest.py`; all 20+ files now derive paths from the repo under test.
2. **Stale shim contracts** (`test_profitability_sales_split.py`): 3 tests marked `xfail(strict=False, reason=SASKIA-321)` — the shim architecture was reverted; consolidation into profitability/+sales/ is tracked as SASKIA-321.
3. **Auth audit exemptions**: `photo_credits.py` (public attribution page, same rationale as credits.py) and `stations.py` (own pre-auth station-lock flow via `decide()`) added to `EXEMPT_FILES` with comments.
4. **Real gap fixed**: `demo.py` POST /demo/seed was flag-gated but unauthenticated — now `dependencies=[Depends(require_login)]` (defense in depth: flag + auth).
5. **dashboard KPI test** audits `dashboard.html` + its `_dashboard_kpi_row.html` partial (KPI row was extracted to a partial).
6. **bws-secrets test** skips when `/opt/data/.hermes/bws-secrets-cache.tsv` is absent (host-ops self-check, not a unit test).

## Follow-ups

- SASKIA-321: consolidate costing.py vs profitability/ + sales/ duplication (real refactor, needs its own session).
- `test_demo_reset.py::test_dashboard_empty_state_after_reset` fails on clean main too (dashboard renders an SVG placeholder) — separate investigation.
