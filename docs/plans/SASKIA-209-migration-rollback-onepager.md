# SASKIA-209 one-pager — Forward-only migration rollback path (backlog #7)

**Status:** scoped, not started. L effort (~2 days). Priority grows with every migration added (113+).

## Problem

Migrations are forward-only by rule (AGENTS.md 13-15). The only undo today is `restore_database()`
(`app/rms/backup.py:212`) — but it's a **merge-restore pinned to schema_version 6** and skips
Tag/TagLink. After a bad migration on prod (VPS, `/data/rms.sqlite`, WAL), the operator's actual
options are: pre-migration JSON.gz backup (written by `sync_backup_before_migration`,
fail-closed) + manual surgery. That's a 2 a.m. procedure nobody has rehearsed.

## Design (what "rollback" should mean here)

**Not** down-migrations. Rollback = **restore-to-pre-migration-state**, executable in one command:

1. **`sazon migrate --rollback`** (CLI entry, `app/cli.py` if present else `scripts/`):
   - Reads `schema_version`. Refuses if >1 migration ahead of the last known-good marker
     (rollback is per-migration, not per-batch).
   - Locates the newest pre-migration backup (`/tmp/sazon_backups/<db>-pre-v<A>-to-v<B>.json.gz`,
     rule 17 — already written, fail-closed, restorable; 3 tests lock it).
   - **Stop-the-world**: SQLite single-file → swap, no locking dance:
     a. `VACUUM INTO` the CURRENT (bad) state to `/tmp/sazon_backups/<db>-post-v<B>-<ts>.json.gz`
        (evidence + retry point).
     b. Restore the pre-migration archive into a FRESH db file, `PRAGMA integrity_check`.
     c. Atomic rename over the live file; restart-safe (WAL rebuilds on next open).
   - Marks the rolled-back version in `app_meta` (`migration_rollback_log`) so the next
     `init_db` re-applies B cleanly instead of thinking it's done.
2. **What it does NOT do**: no data migration reversal (rows added by B's data backfills stay —
     documented; forward fixes are the norm), no Postgres variant (prod is SQLite; the
     models_legacy CheckConstraints target Postgres parity only).

## Why backups aren't enough today

The backup EXISTS but there's no single-command, integrity-checked, version-marked restore.
The gap is operational, not archival. Steps (a)-(c) are ~80 lines; the CLI + tests are the rest.

## Test plan

- Roundtrip: migrate 100→113, rollback to 112, assert schema + `migration_rollback_log` row,
  re-migrate to 113, assert idempotent.
- Fail-closed preserved: corrupt backup → refuse rollback, keep bad state, loud error.
- WAL: rollback with a `-wal` file present leaves no orphan/stale WAL.

## Est

- CLI + restore-swap logic: 0.5d
- `migration_rollback_log` (app_meta keys, no new table): 0.25d
- Tests (roundtrip, fail-closed, WAL): 0.75d
- Docs + runbook (`docs/operations/`): 0.25d
- Buffer for `restore_database` v6-pin discovery (likely rewrite that function to
  schema-agnostic table iteration): 0.25d
