# SASKIA-317: parallel-suite FD exhaustion (xdist INTERNALERROR cascade)

**Date:** 2026-10-08
**Owner:** Hermes (autonomous)
**Status:** shipped

## Symptom

Full pytest runs under `-n 2 --dist=loadscope` (the CI invocation) died mid-suite with
`sqlite3.OperationalError: unable to open database file` escalating to a pytest-xdist
`INTERNALERROR: KeyError: <WorkerController gw0>`, erroring out every remaining test —
hundreds of spurious errors per run, flaky per run (crash point varied: 11%, 14%, 40%).

## Root cause (proven with FD instrumentation)

Three migration-time hooks (`_migration_060` cascade step, `_migration_062`,
`_migration_061` in `app/rms/db.py`) opened `make_engine()` with no url. That resolves
`config.DB_PATH` — a module-level constant frozen at **import** time. Under pytest, the
`tmp_db_path` autouse env override happens *after* import, so the engine pointed at the
**real production DB path** (`~/.local/share/aiw-restaurant/rms.sqlite`).

`init_db()` runs on every function-scoped `app_engine` fixture (~1,900 tests), so each
worker accumulated pooled sqlite connections (+WAL sidecars) to the real DB — ~2 FDs per
call, never disposed. FD trajectory measured: 13 → 510 in 80s, 4,096 (soft limit) at ~84%
of the run. Every `open()` after that fails → worker internal error → xdist marks all
remaining tests as errors.

## Fix

The hooks now build their ORM Session **on the migration's own `conn`**
(`Session(bind=conn)`) instead of a fresh default engine. Same DB the migration targets
(semantically correct for a migration-time backfill), zero extra engines, zero FDs leaked.
Plus coverage `parallel = true` so concurrent runs can't collide on the shared
`/tmp/.coverage-sazon` sqlite.

## Verification

- Full suite `-n 2 --dist=loadscope` (7,888 items): **completed in 52 min** — 7,466 passed,
  worker FDs flat at 15 the whole run (pre-fix: dead at ~14% with FDs ≥ 4,096).
- Remaining failures in that run are pre-existing on latest main (verified on a clean
  checkout): `routers_require_auth` + `profitability_sales_split` shims, the pg-flavored
  `host.example` fixture errors (CI runs those in the dedicated `-m pg` job), and a
  wall-clock `test_qseed_is_fast` perf assertion.

## Follow-ups (out of scope here)

- `test_qseed_is_fast` wall-clock assertion violates anti-rule #20.
- 21 psycopg `host.example` errors: fixture leaks a PG URL into non-pg tests.
