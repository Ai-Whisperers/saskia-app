# Coverage Gate Strategy — Phase 14 (2026-10-01)

## TL;DR

AGENTS.md §Testing says coverage gate is 80%. The CI workflow ran
`pytest --cov=app` but **never enforced** `--cov-fail-under`, so the
gate was advisory-only. Phase 14 Batch H wires the gate for real, but
sets the threshold to **30%** (current measured floor) — not 80%.

Setting 80% would fail the gate immediately. The honest move is:
1. Enforce **today's floor** so a coverage regression breaks CI.
2. Grow it to 80% over time using a tiered plan.

## Current state (2026-10-01, measured)

Run: `pytest --ignore=tests/browser --ignore=tests/visual --cov=app`
(18419 statements, 12380 missing → 32.79% with the Phase 14 test set,
~25-28% with smaller subsets).

Floor chosen: **30%**. Below that = gate fails. Above = gate passes.

## What's covered well (>70%)

These modules are tested through behavior:

| Module | Coverage | Why |
|---|---|---|
| `app/rms/models/__init__.py` | 100% | Re-exports only |
| `app/rms/tagging/__init__.py` | 100% | Re-exports only |
| `app/rms/money.py` | ~95% | Property tests + every persistence path |
| `app/rms/units.py` | ~95% | Property tests + cross-family rejection |
| `app/rms/costing.py` | ~90% | Cycle detection + recipe walk tests |

(AGENTS.md §Testing module breakdown is correct for money/units/costing.)

## What's NOT covered (the gap)

The biggest contributors to the 12k missing statements:

| Category | Lines missing | Why uncovered |
|---|---|---|
| Routers (HTTP plumbing) | ~3500 | Most routes return HTML; testing requires spinning a TestClient with auth bypass per route. Phase 14 added 4 endpoints with full tests. The other 250 routes have thin smoke tests at most. |
| Templates + Jinja macros | ~2100 | Jinja has no native coverage tracking; `app/services/template_render.py` is a soft target since it touches every render. |
| Side-effect services (Herebus, Supabase, OAuth) | ~1800 | These hit external systems; tests are integration-only (testcontainers in CI). |
| Static-content audit helpers | ~1200 | Many of these are intentional one-shots that ran during their phase and don't need new coverage. |
| Legacy / migrations | ~900 | `app/rms/migrations/*` is excluded from coverage (`pragma: no cover`) — historical, not importable. |
| Big routes not yet exercised | ~800 | `pedido_router` create + cancel + logica actions — covered by smoke tests but not by route-level integration tests. |

## Path to 80% (growth plan)

Each tier adds tests + raises the gate. Estimated cost in parentheses.

### Tier 1 — 30% → 45% (≈6h)
- Add `tests/test_route_smoke.py`: spin TestClient, hit each `@router.get`
  with `SASKIA_TEST_AUTH_DISABLED=1`, assert 200 + non-empty body.
  Skips `app/rms/main.py` (`pragma: no cover` for the assertion).
- This single test file covers ~1500 statements and gets us to 45%.
- **Move first.**

### Tier 2 — 45% → 60% (≈4h)
- Add `tests/test_template_render.py`: render every template name from
  a known fixture set, assert no `{{ undefined_var }}` exceptions.
  Covers `app/services/template_render.py` and the route → template glue.
- Bump gate to 60%.

### Tier 3 — 60% → 80% (≈8h)
- Replace boilerplate with `@pytest.mark.parametrize` over `(route,
  fixture_customer)` tuples for the customer / pedido / venta / receta
  modules. About 4h.
- Add CRUD roundtrip tests for the 20 most-used CRUD endpoints. 4h.
- Bump gate to 80% (matches AGENTS.md).

## Tier 4 (stretch) — 80% → 90%
- Property-based tests for the analytical pipeline (daily_summary,
  weekly_report, monthly_close). 4h.
- Tighter branch coverage on `app/rms/accounting.py`.

## CI integration

`.github/workflows/ci.yml` already runs:
```
uv run pytest --cov=app --cov-report=term-missing
```

After this batch, the gate is wired into `addopts`, so it applies
locally and in CI equally. The workflow file does not need editing —
the threshold travels with `pyproject.toml`.

## How to verify locally

```bash
uv run pytest --cov=app --cov-report=term-missing
```

The last line of output will be:

```
Required test coverage of 30% reached. Total coverage: 32.79%
```
or
```
FAIL Required test coverage of 30% not reached. Total coverage: 27.31%
```

## Why 30% and not 35%?

The 35% number I tried first only holds for the wider Phase 14 test
set. Smaller subsets (e.g. running just one phase's tests) drop into
the high 20s. 30% is the floor that survives the smallest reasonable
subset (`tests/test_money.py` + `tests/test_units.py` plus the current
Phase 14 additions).

## Owner / next action

Tier 1 is the cheapest + biggest win. Recommend opening a
`SASKIA-NNN` ticket for it and shipping as the next batch after
Phase 14 closes.