<!-- ROADMAP-REDIRECT -->
# ⚠️ Moved / Superseded

**This file has been moved or superseded.** The canonical location is:

> **`docs/operations/PRODUCTION_500_RUNBOOK.md`**

Runbook (moved to operator-facing folder).

See [`docs/roadmap/README.md`](docs/roadmap/README.md) for the full index.

---

<!-- ORIGINAL CONTENT BELOW -->

# 🚨 Production Server Runbook — 2026-09-23 500s

## What's happening

The live site at `https://sazon-rms.paragu-ai.com` has been returning 500 errors on:
- `/ventas` (TemplateRuntimeError — fixed in code)
- `/pedidos/bulk-cancel` (ProgrammingError — fixed by migration 32)
- `/produccion-planner/compute` (IntegrityError — fixed in code)
- `/produccion-planner` (TemplateRuntimeError — fixed in code)
- `/recetas/api/search` (AttributeError — fixed in code)

## Why

The Postgres database on Render/Neon is at **schema version 27**, while the
code expects version 32 (after my latest push). **5 migrations pending**:
- 28: recipe.yield_qty CHECK constraint
- 29: HEREBUS integration (10 new tables: DeliveryZone, WishlistItem, etc.)
- 30: Recipe.image_url column
- 31: ck_risk_status accepts 'activo'
- 32: pedido.cancel_reason column

The code reads model columns that don't exist in the DB yet → ProgrammingError.

## Deploy steps (1 command)

The lifespan in `app/rms/main.py` calls `init_db(engine)` on every startup.
It auto-applies all pending migrations idempotently.

```bash
# On the Render production instance, restart the service.
# Or push the latest commit + Render auto-deploys.

git pull origin main  # or trigger Render deploy from GitHub UI
```

The lifespan will log:
```
MIGRATIONS: applied (idempotent, no-op if already current)
```

Then `/healthz/db` will report:
```json
{
  "schema_version": 32,
  "code_schema_version": 32,
  "migrations_pending": 0
}
```

## Manual migration (if Render isn't auto-deploying)

```bash
# From the project root, on the prod server or via Render one-off shell:
DATABASE_URL='postgresql://user:pass@host:5432/db' \
  uv run sazon migrate
```

Expected output:
```
schema_version: 27 -> 28
schema_version: 28 -> 29
schema_version: 29 -> 30
schema_version: 30 -> 31
schema_version: 31 -> 32
schema applied at version 32
```

## Verify after deploy

1. Hit `https://sazon-rms.paragu-ai.com/healthz/db` — expect `migrations_pending: 0`
2. Navigate to `/ventas` — should render with the 30-day default
3. Navigate to `/produccion-planner` — should render
4. POST to `/pedidos/bulk-cancel` with `reason=...` — should redirect

## Files changed in this fix

- `app/rms/db.py` — added `_migration_032_pedido_cancel_reason`
- `app/rms/config.py` — bumped `CURRENT_SCHEMA_VERSION` to 32
- `app/routers/herebus.py` — planner_compute now sets `planned_at`
- `app/routers/recipes.py` — removed `r.description` (Recipe has no such column)
- `app/templates/planner.html` — uses `m.gs()` instead of nonexistent `|format_gs`
- `app/templates/ventas.html` — replaced `|merge` Jinja2 filter with manual loop

Commit: `0f3692c fix: ventas template (Jinja2 |merge filter), production_plan.planned_at, planner |format_gs, recetas.search (no description col)`
