# Session 0 — Operational Drift Fix (Partial)

**Date:** 2026-10-05
**Goal:** Fix the 3 drift items identified in `audits/2026-10-05-backlog-verification.md` so that the BACKLOG ✅ Done items are actually live in prod.
**Duration:** ~25 min in this turn.
**Outcome:** 1/3 drift items fully fixed locally, 2/3 left as no-ops for operator review.

## What was done

### DRIFT-2 (Migration 098 source recovery) — ✅ DONE

The deployed prod DB is at schema_version 98 but `app/rms/config.py` said 97. Migration 098 ran on prod in two unmerged phase-3 branches (`feat/phase-3-ci-cleanup` + `feat/phase-3-m1-product-detail`) and was lost to a rebase.

**Recovered both 098 candidates:**

1. **`app/rms/migrations/_098_production_closed_day.py`** (new, ~80 lines)
   - `production_closed_day` table: one row per closed date with reason, closed_by, closed_at
   - Idempotent: `CREATE TABLE IF NOT EXISTS`
   - Source: `origin/feat/phase-3-ci-cleanup` commit `6da78a4` (paraphrased — actual hash was on the closed-day file at ref origin/feat/phase-3-ci-cleanup)

2. **`app/rms/migrations/_098_customer_phone.py`** (new, ~120 lines)
   - `customer_phone` table: 1:N from customer with kind (mobile/whatsapp/work/home/other), label, is_default, is_active, sort_order
   - Idempotent: `CREATE TABLE IF NOT EXISTS` + `NOT EXISTS` backfill from `customer.phone`
   - Source: `origin/feat/phase-3-m1-product-detail`

**Wired into `app/rms/db.py`:**
- Added imports for both new modules (line 47-48)
- Added `_migration_098_production_closed_day()` and `_migration_098_customer_phone()` (line 4021-4050)
- Added `_migration_098_combined_098()` wrapper (line 4053-4066) because two functions can't share dict key 98
- Registered `98: _migration_098_combined_098` in MIGRATIONS dict (line 4156)
- Bumped `CURRENT_SCHEMA_VERSION` 97 → 98 in `app/rms/config.py:71`

**Updated 3 stale migration tests** that hardcoded `assert int(v) == 92` to `== 98`:
- `tests/test_migration_090_stock_movement_recipe.py`
- `tests/test_migration_091_backfill.py`
- `tests/test_migration_092_drop_sale_stock_move.py`

**Verification:**
- `python -m pytest tests/test_migration_090_*.py tests/test_migration_091_*.py tests/test_migration_092_*.py tests/test_migrations_registry.py --no-cov` → **18/18 pass**
- `python -m pytest tests/test_lifespan_migrations.py tests/test_migration_partial_apply_detector.py --no-cov` → **7/7 pass, 6 skipped (PG)**
- `python -c "from app.rms.db import MIGRATIONS; print(98 in MIGRATIONS)"` → `True`

**Committed and pushed as `5c1e1b1` on origin/main.**

### DRIFT-1 (Redeploy) — ⏸️ NOT DONE

**Reason:** Operationally risky. Running `./deploy-to-vps.sh` will:
- Build a new Docker image on the VPS (10-15 min)
- `docker stack deploy` which rolls the service
- Could fail if the env is misconfigured, breaking prod
- Requires no manual input but is **not reversible without operator action**

I did the local-source-prep work (DRIFT-2) so the next deploy will be safe (idempotent migrations, no source/schema mismatch). The actual deploy command needs operator approval because:
- A new deploy will restart the prod container
- If something goes wrong, the operator needs to be ready to roll back
- The deploy script is already correct (just `./deploy-to-vps.sh` from `/opt/data/work/saskia-app/`)

**Recommended next:** Run `./deploy-to-vps.sh` (10-15 min) then verify with:
- `curl https://saskia-vps.paragu-ai.com/healthz/summary` → should return 200
- `curl https://saskia-vps.paragu-ai.com/p/abc123` → should return 404 (no such token) NOT 404 (no route)
- `curl https://saskia-vps.paragu-ai.com/healthz/db` → `schema_version: 98, drift: 0`

### DRIFT-3 (Missing env vars) — ⏸️ NOT DONE

**Reason:** Operator-input required. The missing env vars are:
- `SENTRY_DSN` (Sentry.io project DSN URL)
- `SUPABASE_SECRET_KEY` (Supabase service-role key)
- `R2_*` (Cloudflare R2 access key, secret, account ID, bucket name)

I don't have access to these secrets. They need to be:
- Generated from each service's dashboard
- Added to the VPS's `.env` file (currently at `/opt/build-apps/saskia-rms/.env` on the VPS, excluded from rsync)
- Redeployed to take effect

**Recommended next:** Add to VPS `/opt/build-apps/saskia-rms/.env`:
```
SENTRY_DSN=https://...@sentry.io/...
SUPABASE_SECRET_KEY=eyJ...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_ACCOUNT_ID=...
R2_BUCKET_NAME=saskia-backups
```

## Cherry-picks attempted but deferred

### `feat/prod-quick-merma` — `/api/smoke/waste-source-mix`

I tried to cherry-pick the smoke endpoint commit `f032723` to bring `/api/smoke/waste-source-mix` to main. **Failed** because:

- The endpoint SQL references `waste_log.source` column
- That column was added in the SAME branch (commit `03a0977 feat(merma): PROD-MERMA-2 batch I - denormalize WasteLog.source`) but that migration is also unmerged
- Cherry-picking the column-add would also need 4+ other commits (model, merma UI, etc.) for a complete picture
- 4 tests in `tests/test_waste_source_mix_endpoint.py` failed because the test calls `record_waste(source="manual")` but `record_waste` doesn't accept `source` yet

**Decision:** Reverted the cherry-pick. Document here as a future work item. The smoke endpoint is NOT a BACKLOG item — it's a PROD-MERMA-2 follow-up. **Defer to a future "PROD-MERMA" cherry-pick session** where we take the whole 5-commit batch (UI + model + migration + tests).

### `sprint-2-2-tagging` — tagging refactor

I reviewed this branch (1 commit, Hermes-authored on 2026-10-01): `b55dde7 refactor(tags): consolidate into tagging/ package`. It:
- Deletes `app/rms/tags.py` (415 lines) and `app/rms/tag_algebra.py` (96 lines)
- Creates `app/rms/tagging/{model,ensure,filters,classify,__init__}.py`
- Modifies `app/rms/db.py` and `app/routers/products.py` and 5 other files
- Has 7 new tests in `tests/test_tagging_api.py`

**Concern:** The branch's merge base is `d0dada3` which is BEFORE my migration 098 work. Merging now would require a rebase AND conflict resolution on `db.py` (which I just modified for 098). The risk of breaking 25+ tests that I just made green is high.

**Decision:** Defer to a dedicated refactor session. This is **BL#1** territory (refactor `app/rms/`) which is explicitly listed as a "defer" item in EXECUTION-PLAN.md §6.

## Status of EXECUTION-PLAN.md Session 0

| Item | Status |
|---|---|
| DRIFT-1 Redeploy | ⏸️ Operator action required (run `./deploy-to-vps.sh`) |
| DRIFT-2 Migration 098 | ✅ DONE (commit `5c1e1b1`) |
| DRIFT-3 Env vars | ⏸️ Operator action required (add to VPS `.env`) |
| Cherry-pick smoke endpoint | ⏸️ Deferred (needs larger PROD-MERMA batch) |
| Cherry-pick tagging refactor | ⏸️ Deferred (BL#1 territory) |

**Net result:** Session 0 is 33% done. The local work is complete and the operator has clear next steps for the remaining 67%.

## What I learned

- **The deployed prod image is older than main HEAD.** Several routes that exist in main (like `/healthz/summary`) return 404 in prod. The deploy script works; it just hasn't been run.
- **The DB schema is ahead of the source.** Schema 98 ran on prod without the corresponding source files. This is the rebase-drift pattern that BACKLOG #4 was supposed to prevent — Sprint 4.5 fixed it for fresh installs but didn't recover already-deployed state.
- **`CURRENT_SCHEMA_VERSION` is the source of truth for fresh installs.** Bumping it ensures future deploys are consistent. Existing prod doesn't need it (already at 98) but the new deploy from main will run the recovered 098 which is idempotent — no harm.
- **The `feat/prod-quick-merma` branch is bigger than it looks.** The 5 commits touch UI + model + migration + tests, all interdependent. Cherry-picking one commit in isolation breaks the others.

## Files changed in this session

- `app/rms/config.py` — `CURRENT_SCHEMA_VERSION 97 → 98`
- `app/rms/db.py` — imports + 3 new migration functions + MIGRATIONS[98] entry
- `app/rms/migrations/_098_production_closed_day.py` — new (recovered)
- `app/rms/migrations/_098_customer_phone.py` — new (recovered)
- `tests/test_migration_090_stock_movement_recipe.py` — `== 92` → `== 98`
- `tests/test_migration_091_backfill.py` — `== 92` → `== 98`
- `tests/test_migration_092_drop_sale_stock_move.py` — `== 92` → `== 98`

## Next session

Run `./deploy-to-vps.sh` (10-15 min, no manual input needed). Verify `/healthz/summary`, `/p/{token}`, `/healthz/db` all return correct values. Then move to **Session 1: Cerrar puertas A.1-A.6** (3 days, 6 critical security/correctness items, all local code work).
