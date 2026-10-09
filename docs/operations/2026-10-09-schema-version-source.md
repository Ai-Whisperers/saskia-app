# Schema version source: `app_meta` vs SQLite `PRAGMA user_version`

**Date:** 2026-10-09
**Owner:** Sazon dev
**Status:** Decided — `app_meta` is canonical, PRAGMA user_version is intentionally not used.

## TL;DR

Sazon tracks the schema version in a row of the `app_meta` table (`key='schema_version'`, `value=<int>`), not in SQLite's `PRAGMA user_version`. This is by design. Both options were considered; the `app_meta` approach was chosen because **it works identically on SQLite and Postgres without dialect-specific code paths**, and it keeps the schema version in the same place as other deployment metadata (rollbacks, owner info, EOD run timestamps).

## Where the version lives

| Location                            | Type    | Read by                                     | Written by                                            |
| ----------------------------------- | ------- | ------------------------------------------- | ----------------------------------------------------- |
| `app_meta` row, `key='schema_version'` | TEXT (SQLite) / JSONB (Postgres) | `_current_schema_version(conn)` in `db.py` | `_bump_schema_version(conn, version)` in `db.py`      |
| `CURRENT_SCHEMA_VERSION` in `app/rms/config.py` | Python int |  | hand-bumped when shipping a migration                 |
| `app/rms/migrations/_NNN_*.py` files      | migration code         | `init_db()` in `db.py`                       | each migration calls `_bump_schema_version(N)` at end |

`init_db()` runs the migration files in order, calling `_bump_schema_version(N)` at the end of each, until `app_meta.schema_version == CURRENT_SCHEMA_VERSION` from `config.py`.

## Why not `PRAGMA user_version`?

SQLite's built-in `PRAGMA user_version` is the textbook choice for tracking schema version in a SQLite-only app. It is:
- 4-byte integer stored in the SQLite header
- Read with `PRAGMA user_version` (returns the int)
- Written with `PRAGMA user_version = <int>`
- Automatically included in database backups (it's part of the file header)

We considered it for Sazon but **rejected it** for these reasons:

### 1. Postgres parity

Sazon supports BOTH SQLite (VPS prod) AND Postgres (Render preview). SQLite has `PRAGMA user_version`; Postgres has no equivalent. If we used `PRAGMA user_version`, we'd need a parallel `pg_*` implementation (e.g., a custom GUC, a row in a metadata table, or `current_setting('app.schema_version')`). That's two code paths to keep in sync.

`app_meta` is a plain table that exists in BOTH backends. Same code path.

### 2. Operational observability

`app_meta` is a queryable table. Operators and dashboards can read the current schema version with the same tooling they use for every other config row:

```sql
SELECT value FROM app_meta WHERE key = 'schema_version';
```

`PRAGMA user_version` requires a separate `PRAGMA` statement, which most DB tools surface as an out-of-band property rather than a row.

### 3. Audit trail

When `_bump_schema_version(conn, N)` is called, it stores the new version AND a timestamp (`updated_at`). Operators can see when the last schema bump happened:

```sql
SELECT key, value, updated_at FROM app_meta WHERE key LIKE '%schema%';
```

`PRAGMA user_version` has no associated timestamp. You'd lose the "when was the last migration applied?" signal.

### 4. Backup determinism

The backup manifest (`app/rms/backup.py:88`) stores `schema_version` in its JSON. After a restore, the operator verifies `manifest.schema_version == current_schema_version`. With `app_meta`, the restored value is in the same place as every other config row. With `PRAGMA user_version`, the value is in the file header, which IS preserved by SQLite backups, but the operator would need a separate `PRAGMA` to read it.

## When would we change this?

If Sazon ever becomes SQLite-only (no Postgres support), `PRAGMA user_version` becomes more attractive because it's slightly faster (one fewer SQL query) and the file-header storage is more "native" to SQLite. Until then, `app_meta` is the right choice.

## See also

- `app/rms/db.py` — `_bump_schema_version` (line ~4359), `_current_schema_version` (line ~4411)
- `app/rms/config.py` — `CURRENT_SCHEMA_VERSION = 116` (line 92)
- `app/rms/backup.py` — backup manifest schema version field
- `app/rms/main.py` — `migrate()` entry point (line ~1238), `if before == CURRENT_SCHEMA_VERSION: ...`
- [SQLite docs on `PRAGMA user_version`](https://www.sqlite.org/pragma.html#pragma_user_version) — the alternative we considered
