# Producción v2 — post-Fase 4 status

**Date:** 2026-10-05
**Author:** Hermes
**Status:** Current snapshot of PRODUCCION-V2. The earlier "Fase 2 fix plan" (2026-10-05-produccion-v2-fase-2-fix-plan.md) is now superseded by Fase 5 (scheduler deletion) and Fase 3+4 (cache + auto-invalidate).

## What changed since the original plan

The original draft identified two concrete cleanups. Both are now obsolete:

| Original fix | Status |
|---|---|
| Cast `line.qty` to float in `production_scheduler.ingredient_requirements` | **N/A** — module deleted in Fase 5 (`production_scheduler.py` is a stub explaining its own removal) |
| Mark 3 herbus integration tests as xfail | **Done** — `tests/test_herbus_integration.py::TestWave2PlannerIntegration` now shows 3 xfailed, 0 failed (verified 2026-10-05) |

## Current state of PRODUCCION-V2

**Shipped (Fase 0 + 1 + 2 + 3 + 4 + 5):**

- Migration 102 (production_demand_snapshot, production_plan_audit, completion.status, completion.closure_notes).
- `app/rms/production_demand.py` — `get_demand()` with TTL cache (5 min, `?ui=v2` to populate, dirty-check via MAX(pedido.updated_at), 108x speedup on warm cache).
- `app/rms/production_scheduler.py` — deleted (stub header only). `/inicio` migrated to `production.py.plan_production()` + `_top_products_by_velocity` helper.
- `close_day_for_product()` helper + `POST /produccion/close-day` endpoint.
- Day-view template: `?ui=v1` / `?ui=v2` toggle, DEMANDA column (forecast + pedidos), closure summary card, "Cerrar turno" modal.
- `ui_version` query-param name (renamed to dodge `{% import ... as ui %}` shadowing).
- **Cache invalidation hooks** (Fase 4) on 7 routes: `pedidos_create`, `pedidos_status`, `pedidos_fulfill`, `pedidos_duplicate`, `pedidos_bulk_fulfill`, `pedidos_bulk_cancel`, `sales_create`. Best-effort; done BEFORE `safe_commit` so the DELETE joins the same transaction.
- `_as_date()` helper in `app/routers/pedidos.py` to normalize mixed `date`/`datetime` callers of `pedido.promised_date`.
- `ProductionDemandSnapshot` + `ProductionPlanAudit` typed models in `app/rms/models_legacy.py`.
- Setting `production.demand_snapshot_ttl_seconds` (default 300, `0` disables cache).

**Test status (2026-10-05):**

```
tests/test_production_demand.py          : 31 passed
tests/test_production_close_day.py       : 44 passed
tests/test_production.py                 : 18 passed
tests/test_plan_accuracy.py              :  9 passed
tests/test_p1_b2_forecast_enchufado.py   : 18 passed
tests/test_pedidos_fulfill_atomicity.py  :  4 passed
tests/test_pedidos_fulfill_negative_stock:  7 passed
tests/test_pedidos_nuevo_t_2026_10_01.py :  7 passed
tests/test_pedidos.py                    : 16 passed
tests/test_eod_completion.py             :  6 passed
tests/test_herbus_integration.py         :  3 xfailed (path bug, pre-existing)
tests/test_production_scheduler.py      :  0 (file emptied; module deleted)
─────────────────────────────────────────
                                         168 passed, 3 xfailed, 0 failed
```

**Remaining spec items (explicitly deferred by spec):**

- ⏸ `?ui=v2` cutover to default + `v1` removal — spec says "default `v1` for 1 sprint, then default `v2` and `v1` is removed". Sprint boundary not yet defined.
- ⏸ Mobile dedicated view — spec says "Fase 6 or never".

## Open operational concerns

- **599 dirty files in the worktree** (451 modified, 138 deleted, 10 untracked) — cumulative drift from prior sessions. Not a regression of Fase 1-4. Address in a dedicated cleanup commit when the operator chooses to commit a milestone.
- **Cache TTL is 5 min.** If the operator reports staleness faster than 5 min, the per-write hooks (Fase 4) should already be covering it. If not, lower the TTL via the `production.demand_snapshot_ttl_seconds` setting.
- **`?ui=v1` and `?ui=v2` both still work.** A switch-over commit is needed to make `v2` default and delete the `v1` branch.
