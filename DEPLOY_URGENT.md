<!-- ROADMAP-REDIRECT -->
# ⚠️ Moved / Superseded

**This file has been moved or superseded.** The canonical location is:

> **`docs/roadmap/audits/DEPLOY_URGENT_2026-09.md`**

Incident note (historical).

See [`docs/roadmap/README.md`](docs/roadmap/README.md) for the full index.

---

<!-- ORIGINAL CONTENT BELOW -->

# 🚨 URGENT: Production Server Stuck at Schema v27

## Current state (live verified at https://saskia-rms.paragu-ai.com)

```
schema_version: 27
code_schema_version: 32
migrations_pending: 5
last_1h errors: 20
```

The code is at v32 (my latest fixes are deployed) but the DB hasn't
advanced from v27. **The lifespan migrations are silently failing on
Postgres** due to a JSONB type mismatch.

## What I fixed (commit a6843b9)

1. **JSONB UPDATE bug**: All migrations 2-32 used `text("UPDATE app_meta
   SET value = 'N', ...")`. On Postgres, `app_meta.value` is JSONB —
   this UPDATE fails with `invalid input syntax for type json`. The
   lifespan catches the error and continues, but schema_version never
   advances.

   **Fix**: New helper `_bump_schema_version(conn, version)` that does
   `:v::jsonb` cast on Postgres and plain INSERT on SQLite.

2. **Missing schema_version UPDATE in migration 32**: My recent
   `pedido.cancel_reason` migration never bumped schema_version.

   **Fix**: Added `_bump_schema_version(conn, 32)` at the end.

3. **Stale schema_postgres.py**: Was a 9-model subset missing 25+ new
   tables (wishlist_item, risk_item, market_benchmark, delivery_zone,
   etc.). Production uses `schema_postgres.Base.metadata` for
   `create_all()` — so missing tables were silently skipped.

   **Fix**: `schema_postgres.py` now re-exports `models.Base` directly.
   `create_all()` now sees the full 34-table schema.

## Deploy steps

### Option A: Wait for Render auto-deploy (Render free tier may be slow)

1. Render watches `main` branch on GitHub
2. My commit `a6843b9` (and `928aba3` empty trigger) should trigger
3. Render builds a new Docker image (~2-5 min)
4. Deploys to the running service
5. **Lifespan runs `init_db()` on startup** — migrations 28-32 will fire
6. Verify: hit `https://saskia-rms.paragu-ai.com/healthz/db` —
   expect `schema_version: 32, migrations_pending: 0`

### Option B: Force redeploy via Render dashboard

1. Go to https://dashboard.render.com/web/srv-XXX (your service ID)
2. Manual Deploy → Clear build cache & deploy
3. Wait for the build to complete

### Option C: Connect to Neon Postgres and run migrations directly

If Render keeps not auto-deploying, run migrations via SQL or psql:

```bash
# Option 1: Use the CLI (runbook requires psql access)
DATABASE_URL='postgresql://user:pass@ep-XXX.us-east-2.aws.neon.tech/neondb?sslmode=require' \
  uv run aiw-saskia migrate

# Option 2: SQL directly (use Neon SQL editor or psql)
# After running, verify:
psql "$DATABASE_URL" -c "SELECT value FROM app_meta WHERE key='schema_version';"
# Expect: 32
```

## After deploy — verify everything works

```bash
# 1. Schema state
curl https://saskia-rms.paragu-ai.com/healthz/db
# Expect: schema_version: 32, migrations_pending: 0

# 2. Pages render without 500
curl -I https://saskia-rms.paragu-ai.com/  # /inicio
curl -I https://saskia-rms.paragu-ai.com/login

# 3. Log in and test:
#    - /ventas (was 500 with TemplateRuntimeError)
#    - /produccion-planner (was 500)
#    - /pedidos/nuevo (was 500 with ProgrammingError on cancel_reason)

# 4. Error count should drop
curl https://saskia-rms.paragu-ai.com/healthz/errors
# Expect: http_500_count.last_1h near 0 (was 20+)
```

## Files changed

- `app/rms/db.py`: 30 UPDATE → helper calls, migration 32 fixed
- `app/rms/schema_postgres.py`: full re-export of `models.Base`
- Commit: `a6843b9 fix: Postgres migrations no-op due to JSONB TEXT issue`
- Trigger: `928aba3 chore: trigger Render redeploy`

## Why this took so long to find

The lifespan catches migration errors and continues — the app stays up
but schema_version never advances. There was no log message visible to
the operator. The only signal was `/healthz/db` showing `code_schema_version`
ahead of `schema_version`. This is the kind of silent failure that's
worth adding monitoring for (a Prometheus alert when `migrations_pending > 0`).
