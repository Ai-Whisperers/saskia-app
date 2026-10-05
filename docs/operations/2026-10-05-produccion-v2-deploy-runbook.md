# PRODUCCION-V2 deploy runbook (10-05)

**For:** the operator (Iván or whoever is on call).
**From:** Hermes session `20261005_140148_9273fc` (saskia-app-work worktree on the Hermes VM).

## What needs to ship

| Component | Status | Where |
|---|---|---|
| Migration 102 (`production_demand_split`) | Code complete, **not in VPS image** | `app/rms/migrations/_102_production_demand_split.py` (untracked) |
| `app/rms/production_demand.py` | Code complete, **not in VPS image** | untracked |
| `app/rms/production_scheduler.py` stub | Replaces old module, **not in VPS image** | modified |
| `app/rms/insights.py` (uses `plan_production`) | Code complete, **not in VPS image** | modified |
| `app/rms/models_legacy.py` (2 new models) | Code complete, **not in VPS image** | modified |
| `app/rms/settings.py` (TTL setting) | Code complete, **not in VPS image** | modified |
| `app/routers/pedidos.py` (6 cache hooks) | Code complete, **not in VPS image** | modified |
| `app/routers/sales.py` (1 cache hook) | Code complete, **not in VPS image** | modified |
| `app/routers/produccion.py` (UI v2 cutover) | Code complete, **not in VPS image** | modified |
| `app/templates/produccion.html` (v2 badge) | Code complete, **not in VPS image** | modified |
| `tests/test_production_demand.py` (+5 tests) | Tests green, **not in VPS image** | modified |
| `tests/test_production_close_day.py` (cutover tests) | Tests green, **not in VPS image** | modified |
| `app/CHANGELOG.md` (Fase 3+4+cutover) | Doc complete | modified |
| `docs/plans/2026-10-05-produccion-v2-post-fase-4-status.md` | Doc complete | untracked |

**Verified locally:** 131/131 production tests pass, 23/23 close-day tests pass, 76/76 dashboard/insights/pedido tests pass.

## Pre-deploy checks

1. **Verify VPS reachability** (Hermes VM has ssh root as of 10-05):
   ```bash
   ssh root@saskia-vps.paragu-ai.com "docker service ls | grep saskia"
   ```
   Expect: `saskia-vps_web   replicated   1/1   saskia-rms:prod`

2. **Confirm current image doesn't have Fase 3+4+cutover**:
   ```bash
   ssh root@saskia-vps.paragu-ai.com \
     "docker run --rm saskia-rms:prod python -c 'from app.rms.production_demand import invalidate_demand_for_sale_today'"
   ```
   Expect: `ModuleNotFoundError: cannot import name 'invalidate_demand_for_sale_today'`.
   If it imports, the VPS already has Fase 4 and you can skip the deploy.

3. **Check the worktree for the dirty tree**:
   ```bash
   cd /opt/data/profiles/ivan/scratch/saskia-app-work
   git status -s | wc -l
   ```
   599 dirty files as of 10-05. These need a separate decision — see "Tree hygiene" below.

## Tree hygiene (the hard part)

The worktree has 599 dirty files that pre-date the Fase 1-5 + cutover work. Committing all of them as one would land a noisy diff. Two paths:

**Path A — Cherry-pick only the Fase 1-5 + cutover changes into a clean branch:**
1. `git stash` everything (preserves the drift, returns to clean HEAD).
2. Create a new branch: `git checkout -b deploy/produccion-v2-fase-1-5-cutover`.
3. Re-apply ONLY the changes listed in "What needs to ship" (10 untracked files, 8 modified files). I can produce a patch for this on request.
4. Commit, push, deploy.

**Path B — Commit everything as one large "drop" commit:**
- Simpler, but lands 599 files in one diff. CI will run on the full diff; any latent breakage will surface.
- Operator review burden: high.

**Recommendation:** Path A. I can produce a focused patch in 5 minutes if asked.

## Deploy sequence (Path A)

After the clean branch is pushed to origin:

```bash
ssh root@saskia-vps.paragu-ai.com
cd /opt/build-apps/saskia-rms
git fetch origin
git checkout deploy/produccion-v2-fase-1-5-cutover
git pull --ff-only
docker build -t saskia-rms:deploy-$(date +%Y%m%d-%H%M) .
docker service update --image saskia-rms:deploy-YYYYMMDD-HHMM saskia-vps_web
docker service logs -f saskia-vps_web --tail 200
```

**Watch for:**
- `migration 102 applied` in the lifespan logs (or "schema_version=102").
- No `KeyError: 'request_id'` cascade in the loguru output.
- `/produccion` returns 200 and the v2 grilla renders (no more tab bar; static "v2 ✨" badge).

## Post-deploy smoke

```bash
# 1. UI v2 cutover: /produccion?ui=v1 should 400
ssh root@saskia-vps.paragu-ai.com "curl -s -o /dev/null -w '%{http_code}' https://saskia.paragu-ai.com/produccion?ui=v1"
# Expect: 400 or 422 (cutover removed v1)

# 2. Default: /produccion should 200 with v2 grilla
ssh root@saskia-vps.paragu-ai.com "curl -s -o /dev/null -w '%{http_code}' https://saskia.paragu-ai.com/produccion"
# Expect: 200

# 3. Cache: create a pedido via the UI, then check the snapshot
# table is empty (Fase 4 invalidation hook)
ssh root@saskia-vps.paragu-ai.com \
  "docker exec -it \$(docker ps -q -f name=saskia-vps_web) sqlite3 /var/lib/saskia/rms.sqlite 'SELECT COUNT(*) FROM production_demand_snapshot'"
# Expect: 0 immediately after a new pedido is created
```

## Rollback

The new image is tagged with a deploy timestamp. To roll back:

```bash
ssh root@saskia-vps.paragu-ai.com
docker service update --image saskia-rms:prod saskia-vps_web
```

This restores the pre-deploy image. No database rollback is needed because:
- Migration 102 is additive (new tables, no destructive ALTER on existing tables).
- The `?ui=v1` removal only affects the route's accepted `?ui` values; the route still works for `?ui=v2` and the default.
- The Fase 4 cache invalidation is best-effort; even if a hook fails, the 5-min TTL will refresh the cache.

## Open issues

- **599 dirty files in the worktree.** Path A above sidesteps this for the deploy but doesn't fix the hygiene. A separate "drop the drift" PR is needed.
- **3 pre-existing test failures** (herbus, sentry-import-cost, pedido-prefill JS handler) — all caused by hardcoded paths in test code that don't match the worktree location. Not part of PRODUCCION-V2. Mark xfail or fix in a separate commit.
- **Operator action needed:** the deploy decision (Path A vs B) is not something I can make on the operator's behalf.
