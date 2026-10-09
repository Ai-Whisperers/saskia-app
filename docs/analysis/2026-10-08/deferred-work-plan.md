# Sazon Deferred-Work Plan — 2026-10-09

> **Companion to:** `chore/sazon-upgrade-2026-10-09` (the upgrade PR)
> **Status:** Proposed tickets, not yet filed in the AIW kanban
> **Effort estimate:** 5-7 days total (when staffed)

The 2026-10-08 hardening sweep shipped the **tooling** (4 scripts +
pre-commit + make + CI + tests + noqa contract). The 4 deferrals below
are the **architectural** items that the tooling now guards against
growing, but doesn't fix.

Each is sized for a single focused work day. Order matters: the
refactors should land first, before the operational changes that
build on them.

---

## Tier 1 — Fix the 3 known import cycles (~6-8h, 1-2 days)

The `KNOWN_CYCLES` allow-list in `scripts/check_imports.py` documents
3 tolerated lazy-import cycles. Each is a "shim module" pattern:
one file is a thin wrapper around the other for legacy import
compatibility. Each is bounded and isolated.

### SASKIA-XXX: break settings_runtime ↔ settings_registry

**Files:** `app/rms/settings_runtime.py`, `app/rms/settings_registry.py`
**Effort:** 1-2h
**Why now:** Sprint 2.1 already cleaned up `settings.py` and
`settings_original.py`; the remaining 2-file pair is the last
settings-sprawl artifact.

**Plan:**
1. Move `settings_get` and `settings_set` from
   `app/rms/settings_runtime.py` to `app/rms/settings_registry.py`
   (the natural home — it knows the SettingsKV semantics).
2. Update `app/rms/settings_runtime.py` to import from
   `settings_registry` (one direction only).
3. Remove the KNOWN_CYCLES entry for this pair.
4. Run `make check` — should still be clean.

**Risk:** low. The 6 functions in `settings_runtime.py` that call
`get_setting_value` use the typed-keyed pattern; moving `settings_get`
to the right module doesn't change any caller.

**Tests:** the existing `tests/test_settings_kv_canonical.py` (27
tests) should continue to pass.

### SASKIA-XXX: deprecate ingredient_intel shim

**Files:** `app/rms/ingredient_intel.py`, `app/rms/tagging/classify.py`
**Effort:** 2-3h
**Why now:** `ingredient_intel.py` is a legacy shim that re-exports
`infer_allergens` and `infer_dietary_tags` from `tagging.classify.py`.
All new code should import from `tagging.classify` directly.

**Plan:**
1. `git grep ingredient_intel` — find all callers
2. Update each caller to `from app.rms.tagging.classify import
   infer_allergens, infer_dietary_tags` (already does the right thing)
3. Add `__deprecated__` marker to `ingredient_intel.py` with a
   removal deadline in the docstring
4. Remove the KNOWN_CYCLES entry
5. Run `make check` + relevant tests

**Risk:** medium. The legacy import path is used in some routers; the
refactor is mechanical but touches multiple files.

**Tests:** `tests/test_ingredient_intel.py` (if exists), `tests/test_tagging.py`.

### SASKIA-XXX: extract _get_db_url_safe to app/rms/db_url.py

**Files:** `app/rms/db.py`, `app/rms/backup.py`
**Effort:** 1h
**Why now:** `db.py` has a helper `_get_db_url_safe` that `backup.py`
needs; `backup.py` has `backup_database` that `db.py` needs. Both
are inside function bodies. The fix is a 5-line extraction.

**Plan:**
1. Create `app/rms/db_url.py` with `_get_db_url_safe`
2. Both `db.py` and `backup.py` import from it
3. Remove the KNOWN_CYCLES entry
4. Run `make check`

**Risk:** very low. The helper is small and well-tested.

**Tests:** the migration tests + the backup cron tests.

---

## Tier 2 — `create_app()` factory refactor in main.py (~6-8h, 1 day)

**Files:** `app/rms/main.py` (1396 lines, the FastAPI app definition)
**Effort:** 6-8h
**Why now:** The module-level singleton pattern
(`app = FastAPI(...)` at line 414) is an anti-pattern in multi-worker
deployments. Sazon currently runs 1 worker so it's not broken, but
the migration to multi-worker (planned for Tier 5) would silently
break the lifespan + middleware stack.

**Plan:**
1. Wrap the 9 `app.add_middleware(...)` calls + 18
   `app.include_router(...)` calls in a `def create_app() -> FastAPI: ...`
   function
2. Keep `app = create_app()` at module level for the
   `app.rms.main:app` uvicorn reference
3. Verify the lifespan is wired correctly (currently `@asynccontextmanager
   async def lifespan(app: FastAPI)`)
4. Add a smoke test: import `app` from `app.rms.main`, instantiate
   twice, verify no module-level state leaks

**Risk:** high. main.py is the most-imported file in the repo. The
refactor MUST be done in one atomic commit and verified with the full
test suite.

**Tests:** all 7,328 tests. Any regression in lifespan/middleware
ordering is a multi-day debugging session.

---

## Tier 3 — PRAGMA user_version as schema source of truth

**Decision: NOT IMPLEMENTED (rejected on 2026-10-09).**

Sazon dev decided to keep `app_meta.value='schema_version'` as the
canonical schema version and NOT adopt `PRAGMA user_version`. The
rationale is in `docs/operations/2026-10-09-schema-version-source.md`
(commit `5e56980c`, 2026-10-09 01:15 by saskia-rms-bot). Four reasons:

1. **Postgres parity** — Sazon supports BOTH SQLite (VPS prod) AND
   Postgres (Render preview). `app_meta` works on both; `PRAGMA
   user_version` is SQLite-only. Two code paths to keep in sync.
2. **Operational observability** — `app_meta` is a queryable table
   that operators can read with normal SQL tools. `PRAGMA
   user_version` is out-of-band.
3. **Audit trail** — `app_meta` has `updated_at` timestamp; `PRAGMA
   user_version` does not.
4. **Backup determinism** — backup manifest reads `app_meta` for
   the schema_version field. `PRAGMA user_version` is preserved by
   SQLite backups but requires a separate query to read.

**Re-open this tier if:** Sazon becomes SQLite-only (no Postgres
support). Then `PRAGMA user_version` becomes more attractive.

**Previous sketch (kept for context):**
- Effort: 1-2 days. AGENTS.md rule 18 P1. Risk: medium.
- Plan: 1) migration that runs `PRAGMA user_version = N` on upgrade;
  2) read `PRAGMA user_version` at session start, fall back to
  Python constant; 3) CI gate; 4) AGENTS.md update.
- Tests: all migration tests (likely 50+).

---

## Tier 4 — `ruff format` the 8 pre-existing drift files (~30 min)

**Files:** mostly `app/rms/seed/sazon.py` (2,900 lines; the curated
compact tuples) and a few scripts
**Effort:** 30 min
**Why now:** `make check` reports "8 files would be reformatted" but
the operator decision is whether to expand the curated tuples. The
Sazon AGENTS.md should document the policy.

**Plan:**
1. The operator reviews each of the 8 files
2. For `app/rms/seed/sazon.py`: keep the curated compact format
   (add `# ruff: noqa: E501` per line OR a per-file `# fmt: off`)
3. For the other 7 files: `ruff format .` is safe
4. Add a one-line note in `app/rms/AGENTS.md` documenting the seed
   data format policy

**Risk:** low. Per-line noqa is local; ruff format is idempotent.

**Tests:** no new tests; existing seed tests verify the data.

---

## Tier 5 — Multi-worker uvicorn + `create_app()` (depends on Tier 2)

**Files:** `pyproject.toml` (uvicorn config), `scripts/deploy.sh`
**Effort:** 2h after Tier 2
**Why now:** Sazon will need to handle Sazón Feliz pre-launch traffic
in Q1 2027.

**Plan:**
1. Tier 2 lands
2. Add `uvicorn --workers 4` to deploy.sh
3. Smoke test: 2 concurrent `/ventas` POSTs from 2 clients
4. Promote the create_app refactor from "needed for multi-worker" to
   "done; tested under multi-worker"

**Risk:** depends on Tier 2.

---

## Tier 6 — `sensez` + `ty` evaluation (~4h, optional)

**Files:** `pyproject.toml` (replace one of the scripts)
**Effort:** 4h evaluation + possibly 1-2 days migration
**Why now:** the alternatives are mature enough to consider.

**sensez** (Rust, 0.27s for comprehensive scan) would replace
`check_imports.py` + `check_duplicate_files.py` + `check_duplicate_code.py`.
Pros: 100x faster; 1 tool instead of 3. Cons: alpha; no Sazon-specific
rules.

**ty** (Astral's Rust type checker) would augment mypy. Pros: faster;
better Sazon framework integration. Cons: alpha; type coverage in
Sazon is sparse.

**Plan:**
1. Add sensez to a dev branch, run it on a fresh Sazon clone, compare
   to my 3 scripts
2. Add ty, run on `app/rms/money.py` and `app/rms/units.py` (the two
   most type-strict modules)
3. If either is 80% as good, replace the Sazon-specific tool
4. Document the decision

**Risk:** none — this is research, not change.

---

## What I will NOT do in the upgrade branch

1. **Multi-tenant RLS** — Sprint 7 work; out of scope
2. **Supabase Storage** — Sprint 8 work; out of scope
3. **Any model changes** — the Sazon schema is mature; modifications
   need product review
4. **Routing changes** — the chooser/station split is in production;
   any changes risk breaking user workflows
5. **Auth changes** — auth is in production; changes are Sprint 9

These are tracked in the AIW org's `aiw-org` repo (agent: ops-monitor
or engineering-monitor).

---

## Execution order recommendation

If you have 2 engineers for 1 week:

1. Day 1: Tier 1 (all 3 cycles) + Tier 4 (format drift)
2. Day 2: Tier 2 (create_app)
3. Day 3: Tier 2 testing + Tier 5 (multi-worker smoke)
4. Day 4: Tier 3 (PRAGMA) + Tier 6 (sensez/ty evaluation)
5. Day 5: docs, retest everything, ship the 5 PRs

Each tier is a separate PR. The 5 PRs total ~1,000 lines of
net-positive code (mostly deletions from the cycle refactors).
