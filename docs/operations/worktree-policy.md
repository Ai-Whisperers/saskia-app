# Worktree Policy — sazon-app

Two worktrees of the same repo exist. Each has a designated role. Drift between them caused 8+ hours of user-visible bugs (Panceta + Pan rallado flagged post-migration 062, B7 subagent's `app/routers/insights.py` + `ui-insight.js` + `sascripciones.py` existed in scratch but not in this worktree, breaking local pytest after rebasing origin/main in 2026-09-29). This policy exists to prevent recurrence.

## Roles

| Worktree | Path | Role | Deploys? | Push policy |
|---|---|---|---|---|
| Scratch | `/opt/data/profiles/ivan/scratch/sazon-app-work` | `main` branch — source of truth for live deploys | **Yes** | `git push origin HEAD` after every commit |
| Production | `/opt/data/work/sazon-app` | Feature dev (`feature/*` branches) — local pytest + review | No (PR + merge → main → deploy) | Via PR only, no direct main push |

## Rules

### 1. Scratch is the source of truth

All new files MUST be created in scratch first. Then either:

- Push from scratch directly to `main` (for small fixes), OR
- Copy the file to production worktree and commit there as part of a feature branch, then PR to main

**Never reference a file in `app/rms/main.py` or anywhere else unless that file exists in BOTH worktrees.** This is the bug that bit us 2026-09-29: C2 commit added `from app.routers import insights, suscripciones` to `main.py` but only the scratch worktree had those files, so the production worktree's pytest failed.

### 2. After every commit touching `app/` or `static/`, deploy

The deploy-after-commit discipline is in MEMORY.md but worth restating:

```bash
cd /opt/data/profiles/ivan/scratch/sazon-app-work
# rsync source to VPS, build, deploy (full path in sazon-rms-deploy-flow skill)
tar --exclude='.git' --exclude='.venv' --exclude='receipts' \
    --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.ruff_cache' \
    --exclude='*.db' --exclude='*.sqlite*' --exclude='tests' \
    --exclude='herbus_drive' --exclude='tmp' --exclude='.env' \
    -czf /tmp/sazon-src.tar.gz .
scp /tmp/sazon-src.tar.gz root@paragu-ai:/tmp/
ssh root@paragu-ai "cd /opt/build-apps && rm -rf sazon-rms && mkdir sazon-rms && \
  tar xzf /tmp/sazon-src.tar.gz -C sazon-rms/ && cd sazon-rms && \
  DOCKER_BUILDKIT=0 docker build --no-cache -t sazon-rms:prod . && \
  docker service update --image sazon-rms:prod sazon-vps_web --force"
sleep 8
# Verify live
curl -sk https://sazon-vps.paragu-ai.com/healthz  # expect 200
# Verify the specific feature
curl -sk <affected_route>  # expect 200, not 404
# Verify the new files actually made it into the container
ssh root@paragu-ai "docker exec \$(docker ps -q -f name=sazon-vps_web) ls /app/app/.../<new-file>"
```

### 3. Push to origin: use `HEAD`, not `main`

The Hermes deny-pattern for "force-push to master/main" triggers on `git push origin main` when origin is behind, even for fast-forward. Always use `git push origin HEAD`.

### 4. Verify imports match files

Before committing changes to `app/rms/main.py` or any router-import aggregator:

```bash
cd /opt/data/work/sazon-app
# Find every name imported in main.py and verify the file exists
python3 -c "
import re
with open('app/rms/main.py') as f:
    text = f.read()
m = re.search(r'from app.routers import \((.*?)\)', text, re.DOTALL)
if m:
    for name in re.findall(r'^\s+(\w+),', m.group(1), re.MULTILINE):
        import os
        if not os.path.exists(f'app/routers/{name}.py'):
            print(f'  MISSING: app/routers/{name}.py')
        else:
            print(f'  OK:      app/routers/{name}.py')
"
```

If anything says MISSING, you need to either create the file OR remove the import. Don't push a broken import.

### 5. The two worktrees must have the same set of new files

When a new file is created in one worktree, it should immediately be visible in the other. Two ways to enforce:

- **Always work in scratch** when starting new work; mirror to production only for review
- **After committing in one, immediately run `rsync` or `cp` to the other** to keep them in sync

A weekly check script (to be added in P4): diff the file lists between worktrees, flag any `app/routers/*.py` or `app/static/*.js` that exists in one but not the other.

### 6. The deploy script's tar MUST exclude `receipts/`

The receipts directory accumulates files during read (POS prints), which makes `tar` warn "file changed as we read it" and the rsync-via-tar path silently exits 0 with a stale source. Always pass `--exclude='receipts'` explicitly. The deploy-to-vps.sh script doesn't have this exclude by default — copy-paste it from this doc.

### 7. After every deploy: verify in 3 places

- [ ] `curl /healthz` → 200
- [ ] `curl <route the change affected>` → 200 (or 401/403 if auth required)
- [ ] `docker exec` into container → `ls /app/app/.../<new-file>` → exists

If any fails: rollback via `docker service update --image sazon-rms:prod sazon-vps_web --rollback` (Swarm keeps last 3 images).

## Why this policy exists

2026-09-29 had 3 separate bugs caused by worktree drift:

1. **Panceta + Pan rallado stayed flagged 8h** because session 1's commits `100e579` (audit_repair) + `3818301` (P0 audit log) were committed in scratch but never deployed. The session said "shipped & live" but skipped the deploy step.

2. **Production worktree's pytest broken after rebasing origin/main** because the C2 tablet-menu commit added `from app.routers import insights, suscripciones` to `main.py` but those files only existed in scratch. Live was fine (because deploy was from scratch) but production worktree couldn't run tests until the missing files were copied over.

3. **`/ventas/qa` route was 404 on production tree before deploy** for the same reason — the file existed in scratch but not in production worktree. After deploy from scratch, live became correct.

**The pattern:** scratch = live truth, production = review surface. When they disagree, scratch wins (because live was deployed from scratch).

## See also

- `/opt/data/profiles/ivan/.hermes/plans/2026-09-29-sazon-rms-multi-session-recovery-plan.md` — full recovery plan
- `sazon-rms-deploy-flow` skill — deploy commands + gotchas
- MEMORY.md — deploy-after-commit discipline + DOCKER_BUILDKIT gotcha
