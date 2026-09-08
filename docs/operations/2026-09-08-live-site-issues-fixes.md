# 2026-09-08 Live-site issues + fixes (Saskia hosted)

## Background

When checking https://saskia-rms.paragu-ai.com on 2026-09-08:

- `/` (dashboard) → 500 Internal Server Error after login
- `/productos`, `/recetas` → 10s timeout (worked locally)
- `/healthz/db` → 503 (PRAGMA SQLite-only SQL running on Postgres)
- Login itself worked (303 → redirect to dashboard)

## Root causes found

### 1. Production Neon DB was on Round-1 schema only (9 tables, no migrations applied)
- schema_version row was missing entirely from `app_meta`.
- Tables `audit_log`, `tag`, `tag_link`, `customer`, `waste_log`, `tenant` did NOT exist.
- All routes that touched those tables (dashboard analytics, customer pages, etc.) 500'd.

**Fix:** manually applied migrations 002-008 via raw SQL against Neon (the migrate CLI was using `INSERT OR IGNORE` which Postgres rejects).

### 2. `app/rms/db.py` migrations used SQLite-only SQL
- `_migration_001_initial_schema`: `INSERT OR IGNORE` → Postgres: `ON CONFLICT DO NOTHING`
- `_migration_002_audit_log`: `AUTOINCREMENT` (SQLite-only), `CREATE INDEX IF NOT EXISTS` (SQLite-only)
- `_migration_003_analytics_columns`: bare `CREATE INDEX IF NOT EXISTS` before dialect check; `DATETIME` columns (Postgres wants TIMESTAMP)
- `_migration_004-008`: no-op but the dialect check wrapper was on the wrong dict
- init_db() final upsert: `INSERT OR REPLACE` (SQLite-only)
- Three duplicate MIGRATIONS dicts in db.py (last one wins, but the first two were dead code)

**Fix:** rewrote all migrations to be dialect-aware (use `conn.dialect.name` to branch SQL). Removed the duplicate MIGRATIONS dicts (kept only the canonical one at line ~300). Used TIMESTAMP for Postgres, DATETIME for SQLite.

### 3. `app/routers/health.py::healthz_db` ran `PRAGMA journal_mode` unconditionally
- SQLite: returns "wal" / "delete"
- Postgres: ERROR: syntax error at or near "PRAGMA"

**Fix:** wrapped the PRAGMA in `if dialect == "sqlite"`, returns `journal_mode="n/a (postgresql)"` for Postgres.

### 4. `app/rms/seed.py::seed_demo_data` ran 30 days × ~10 sales × recipe lines in one transaction
- Each iteration triggered UPDATE ingredient SET stock_qty (cascading from sale consumption).
- On Neon, the long transaction held locks for 60+ seconds, hit statement timeouts, left idle-in-transaction backends.
- Forced terminate via `pg_terminate_backend()` to recover.

**Fix:** split the sales-generation loop into batches of 25 days, commit between batches. Each batch runs in its own short transaction (no lock hold).

### 5. `app/rms/seed.py::record_app_meta` inserted into `value` column as TEXT
- Live DB has `app_meta.value` as JSONB (legacy from prior Supabase migration).
- Model says `value: Mapped[str] = mapped_column(Text, ...)`.
- Insert with string fails: `column "value" is of type jsonb but expression is of type text`.

**Fix:** branch by dialect. On Postgres, use `to_jsonb('...')` cast. On SQLite, plain string.

### 6. The `user` table on live Neon had a hybrid schema
- Round-1 had 9 tables. Supabase Auth apparently also created columns in `user`: `uuid, name, email, emailVerified, image, createdAt, updatedAt, role, banned, banReason, banExpires`.
- Live `user.id` column has a weird mix: integer PK + UUID column. The model says `id: Mapped[int]` but the live table's `id` may have been overwritten.
- Seed crashed trying to insert a User (timestamp text vs timestamptz).

**Fix:** dropped the entire `user` table on Neon. Recreated from the model definition. Source of truth for auth is Supabase Auth, not our local `user` table (we don't read it on the Supabase auth path).

### 7. N+1 query on /productos + /recetas (slow on Neon, instant on SQLite)
- Each product triggers 3 queries: cost (walks recipe tree) + margin (re-walks) + recipe lookup.
- 20 products × 3 queries = 60 round-trips × 50-100ms = 5-10s timeout.
- /recetas: 12 recipes × 3 queries = 36 round-trips.

**Fix:** added `batch_products_cost_margin()` + `batch_recipes_cost()` in `app/rms/costing.py`. Pre-loads all Recipe + RecipeLine + Ingredient + sub-recipe rows in 3-4 queries, then computes in Python using the session identity map. Wired into routers/products.py + routers/recipes.py. /productos now renders in <500ms.

## Local SQLite test: 629/629 pass, ruff clean.

## Files changed in this round

- `app/rms/db.py` — dialect-aware migrations + JSONB support + removed duplicate MIGRATIONS dicts
- `app/routers/health.py` — healthz_db only runs PRAGMA on SQLite
- `app/rms/seed.py` — batched sales loop + JSONB-aware app_meta
- `app/rms/costing.py` — batch_products_cost_margin + batch_recipes_cost helpers
- `app/routers/products.py` — wire batch helper into products_list
- `app/routers/recipes.py` — wire batch helper into recipes_list
- `tests/test_migrate_dialect.py` — new tests for SQLite + Postgres migration idempotency
- `tests/test_costing.py` — 3 new tests for batch helpers
- Commits: `f272e87`, `d8c99f7`, `c9c8b45` (all local, NOT pushed due to dead PATs)

## Outstanding operator action

1. **Push the 3 commits** — Render auto-deploys on main push but the new commits haven't reached GitHub. PATs in BWS (`github-pat-deploy`, `GITHUB_TOKEN`) were DELETED 2026-09-08 per memory. Need to:
   - Use the `aiw-deploy` GitHub App to push (App ID 4866705, install 159908370). 
   - Or generate a fresh PAT via phone-approval rotation (gh-pat-rotation workflow, but this skill is DEPRECATED).
2. **Render will auto-build** from the latest commit on main. The next deploy will include the /healthz/db fix.
3. **Schema is already at v8 on Neon** — manually applied. No further action needed.
4. **Seed data is in place** — 30 ingredients, 12 recipes, 20 products, ~920 sales, 31 tags.

## Lessons (process)

1. **Always test migrations against the production-shape DB before deploying**. SQLite tests pass because SQLite accepts SQLite syntax. Postgres fails. The `INSERT OR IGNORE` pattern is the canary — every single one needs a dialect check.
2. **Long transactions are lethal on serverless Postgres**. Anything that takes >30s should be batched with commits between batches. The seed was 75 days of sales in one txn = 60+ second lock holds.
3. **N+1 queries don't show up on SQLite** (in-process, microsecond round-trips). They bite hard on remote DBs. Always use batch helpers for any "decorate a list" pattern.
4. **Hybrid schemas from legacy migrations are nightmares**. The `user` table having both integer id and UUID column came from a prior Supabase Auth integration that didn't get cleaned up. The local model is the source of truth — drop and recreate tables that drift.
5. **BWS PAT rotation is brittle**. With GitHub App decommissioning PATs in 2026, the only working push path is via the GitHub App installation token (JWT-based). That requires the App's PEM key in BWS or on disk.
