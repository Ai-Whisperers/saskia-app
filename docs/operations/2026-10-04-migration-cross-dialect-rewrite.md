# Migration cross-dialect rewrite — project plan

> **Date:** 2026-10-04
> **Status:** Proposed (not yet started)
> **Owner:** Whoever has 3-5 focused days
> **Related:** PR #46 (this is the strategic follow-up to the tactical
> `Base.metadata.create_all()` pre-provision workaround in
> `.github/workflows/smoke.yml`)

## Why this project exists

The saskia-app migration chain (83 functions in `app/rms/db.py`,
1-99) was written for SQLite first. The `app/rms/db.py:init_db()`
function calls them in order on every app start. On SQLite, this works
correctly: each migration is dialect-aware enough for SQLite, the
schema_version is bumped at the end, and the app starts.

On Postgres, the same migrations fail with errors like:

- `ProgrammingError: syntax error at or near "PRAGMA"` (migrations 7, 31)
- `ProgrammingError: syntax error at or near "AUTOINCREMENT"` (23 migrations)
- `DatatypeMismatch: column "is_default" is of type boolean but expression is of type smallint` (migrations 35, 41, 42, 47)
- `InFailedSqlTransaction: current transaction is aborted, commands ignored until end of transaction block` (after any failed `ALTER TABLE` in a `try/except` block on Postgres)

The current **tactical workaround** (added in PR #46): the CI smoke
workflow runs `Base.metadata.create_all()` to provision the schema
on Postgres, then seeds `app_meta.schema_version` to 99, so
`init_db()` no-ops the chain. This works but is fragile:

- `create_all()` only knows about the current model state. If a
  migration adds a column that the model no longer reflects (e.g., a
  dropped column), `create_all()` won't add it.
- New contributors who run `uv run python -c "from app.rms.db
  import init_db; init_db(engine)"` locally on Postgres will hit
  failures.
- Any future migration run on production Postgres (e.g., for a
  schema fix) will fail the same way.

The **strategic fix** is to rewrite the migrations to be
dialect-aware. This is a multi-day project.

## Scope (83 migrations, ~50 need changes)

Surveyed on 2026-10-04. Numbers are exact.

| Issue | Count | Affected migrations |
|---|---|---|
| Uses `PRAGMA table_info(...)` | 2 | 7 (product_sku), 31 (risk_status_activo) |
| Uses `AUTOINCREMENT` (SQLite-only) | 23 | 18, 21, 23, 27, 31, 34, 35, 39, 41, 42, 44, 45, 46, 47, 48, 49, 51, 65, 69, 74, 75, 77, 78, 80, 82 |
| Uses `INTEGER PRIMARY KEY` (works in PG but means "int" not "serial") | 20 | (subset of above) |
| Inserts integer literal into boolean column | 1 | 35 (compliance_info) — `VALUES (1, 'resimple', '10', 1, 1, 25000, 15, 1, ...)` — at least one of those `1`s is supposed to be a boolean |
| Uses `datetime('now')` (SQLite function syntax) | 1 | 51 (ingredient_variant) — already fixed in PR #46 |
| `try/except` around `ALTER TABLE` without `conn.rollback()` | 0 | (already fixed in PR #46) |

**Estimated migrations needing change: ~25 of 83** (the ones with
AUTOINCREMENT, plus the 2 with PRAGMA, plus 35's boolean issue).

## Refactor strategy

### 1. Add a `_dialect()` helper

```python
def _dialect(conn: Any) -> str:
    """Return 'postgresql' or 'sqlite' (the two we support)."""
    try:
        return conn.dialect.name
    except Exception:
        return "sqlite"
```

This already exists inline in many migrations. Hoisting it removes
duplication and makes the intent explicit.

### 2. Add a `_serial_pk_type(dialect)` helper

```python
def _serial_pk_type(dialect: str) -> str:
    """Return the dialect-appropriate auto-incrementing primary key type."""
    return "SERIAL PRIMARY KEY" if dialect == "postgresql" else "INTEGER PRIMARY KEY AUTOINCREMENT"
```

Migrations that create a new table with `id INTEGER PRIMARY KEY
AUTOINCREMENT` get rewritten to:

```python
conn.execute(text(f"CREATE TABLE foo (id {_serial_pk_type(d)} ..."))
```

### 3. Add a `_now()` helper

```python
def _now(dialect: str) -> str:
    """Return the dialect-appropriate CURRENT_TIMESTAMP expression."""
    return "CURRENT_TIMESTAMP"  # both dialects support this
```

For `datetime('now')` (SQLite-only), use `CURRENT_TIMESTAMP` which
both dialects support.

### 4. Add a `_add_column_if_missing()` helper (already exists)

The current `_add_column_if_missing(conn, table, column, pg_type,
sqlite_type)` in `app/rms/db.py:215` already does the right thing for
most `ALTER TABLE ADD COLUMN` cases. Expand it to also handle the
Postgres-rollback case (already fixed in PR #46 for migration 3).

### 5. Rewrite the 25 problematic migrations

For each:

- Replace `INTEGER PRIMARY KEY AUTOINCREMENT` with `_serial_pk_type(_dialect(conn))`
- Replace `PRAGMA table_info(...)` with `_columns(conn, table)` helper
- Replace `datetime('now')` with `CURRENT_TIMESTAMP`
- Cast integer literals to boolean where the column is boolean: `... 1::boolean, ...`
- Add a dialect guard for migrations that are fundamentally SQLite-only (e.g., 31's `risk_item` recreation — already partially fixed in PR #46)

### 6. Add a CI matrix job

Add a `postgres` job to `.github/workflows/ci.yml` that boots a real
Postgres container and runs the full test suite (not just `-m pg`).
This catches dialect issues at PR time instead of at deploy time.

```yaml
postgres-test:
  runs-on: ubuntu-latest
  services:
    postgres:
      image: postgres:16-alpine
      env:
        POSTGRES_USER: saskia
        POSTGRES_PASSWORD: saskia
        POSTGRES_DB: saskia
      ports: ['5432:5432']
  steps:
    - uses: actions/checkout@v7
    - run: uv sync --all-extras
    - run: |
        uv run python -c "
        from app.rms.db import init_db
        from sqlalchemy import create_engine
        init_db(create_engine('postgresql+psycopg://saskia:saskia@localhost:5432/saskia'))
        "
    - run: uv run pytest -n auto --no-cov
```

The init_db step in CI will fail loudly on any migration that isn't
dialect-aware.

## Estimated effort

| Task | Effort | Notes |
|---|---|---|
| Helpers (1-4 above) | 1 day | All in `app/rms/db.py`, well-tested |
| Rewrite 25 migrations | 2 days | Mechanical; can be done in batches |
| Add CI matrix job | 0.5 day | YAML + Postgres container setup |
| Verification on real prod Postgres | 0.5 day | Smoke test against VPS Postgres |
| **Total** | **3.5-4 days** | |

## Risk and mitigation

### Risk: data loss on existing Postgres DBs

The `app_meta.schema_version` is at 99 on the current prod Postgres
(per Ivan's pre-provision workaround). If a migration gets rewritten
to be more strict, the re-run might fail. **Mitigation:** each
migration rewrite should be idempotent (use `IF NOT EXISTS` or the
helpers above) and verified against a copy of prod data.

### Risk: behavior drift between dialects

Even with helpers, the dialects can behave differently. For example,
Postgres `BOOLEAN` accepts `TRUE`/`FALSE`/`'t'`/`'f'`/`1`/`0` (with
cast), while SQLite treats `BOOLEAN` as `INTEGER` and accepts `0`/`1`
natively. **Mitigation:** add `tests/e2e/test_dialect_consistency.py`
that runs the same migration chain against both dialects and asserts
the resulting schema is equivalent (same columns, same types, same
constraints).

### Risk: the work stalls mid-refactor

This is a 4-day project. If interrupted, the branch could be in a
half-migrated state. **Mitigation:** do the work in 5 PRs, one per
batch of 5 migrations, each individually mergeable:

1. PR 1: Add the 4 helper functions. No migration changes.
2. PR 2: Rewrite migrations 1-20 (lowest numbers, oldest code).
3. PR 3: Rewrite migrations 21-40.
4. PR 4: Rewrite migrations 41-60.
5. PR 5: Rewrite migrations 61-99 + add CI matrix job.

Each PR can be reviewed and merged independently.

## What this enables

- New contributors can run `init_db()` on Postgres without the
  pre-provision workaround.
- Migrations become a single source of truth for schema changes
  (currently `create_all()` + migrations can drift).
- The smoke test verifies init_db end-to-end on Postgres, not just
  the create_all path.
- Future schema changes don't have to think about which dialect
  they're for — the helpers handle it.

## What this does NOT do

- It does not change the test data in `tests/fixtures.py` or
  `tests/factories.py`. Those are still SQLite-only (the test suite
  uses SQLite in-memory via the `tmp_db_path` fixture).
- It does not change the production Postgres schema. The current
  prod schema is correct (we've been running on it for months); this
  rewrite is about making the migration chain portable, not about
  fixing data.
- It does not add multi-tenancy or any new feature. Pure plumbing
  work.

## Open questions

1. Should we use SQLAlchemy's `create_all()` as the primary
   provisioning path (and let `init_db()` only handle `ALTER TABLE`
   migrations)? This would simplify a lot, but loses the migration
   history. **Recommendation:** keep both for now.
2. Should we adopt Alembic? It's the standard Python migration
   library. **Recommendation:** no — adding a heavy dep to a 70h
   project is a worse trade than the current 2-day migration
   cleanup. The dev plan §9 Task 1 explicitly chose hand-rolled
   migrations; this rewrite preserves that decision.
3. Should we run the migration rewrite in a single weekend or batch
   it across multiple weeks? **Recommendation:** single weekend if
   possible, but batching across 5 PRs is fine if time-constrained.

## See also

- `app/rms/db.py` — the migration registry and helpers (current state)
- `app/rms/migrations/_098_production_closed_day.py` — example of a
  cross-dialect migration written correctly from the start
- `app/rms/migrations/_051_ingredient_variant.py` — example of a
  fixed-in-PR-46 migration (the `datetime('now')` backfill bug)
- `.github/workflows/smoke.yml` — the tactical pre-provision
  workaround that this project will make obsolete
- `app/rms/AGENTS.md` — the "Why hand-rolled (not Alembic)" section
  documents the design choice
