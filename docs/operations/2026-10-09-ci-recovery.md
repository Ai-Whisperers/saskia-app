# CI/CD Recovery Playbook — Sazon-app

**When to use this:** any time the GitHub Actions workflows are all red and you don't know why. This is the troubleshooting flow for "5 of 11 workflows are failing."

**Last updated:** 2026-10-09 (after the 5/11 → 1/11 recovery)

## Step 0: Run the diagnostic

```bash
# Get the last 50 runs across all workflows
gh run list --limit 50 --json databaseId,displayTitle,conclusion,workflowName,headBranch,createdAt \
  | jq -r '.[] | [.createdAt, .conclusion, .workflowName] | @tsv'

# Group by (workflow, conclusion) to see the pattern
gh run list --limit 100 --json conclusion,workflowName \
  | jq -r '.[] | [.conclusion, .workflowName] | @tsv' \
  | sort | uniq -c | sort -rn
```

If you see 4-5 of the same workflow failing with the same error → it's systemic, not a one-off.

## Step 1: Read the most recent failure log

```bash
# List the last 20 failures
gh run list --limit 20 --json databaseId,workflowName,conclusion \
  | jq -r '.[] | select(.conclusion == "failure") | [.databaseId, .workflowName] | @tsv'

# Read the failure log of a specific run
gh run view <run-id> --log-failed | tail -100
```

Look for these patterns:

### Pattern A: `error in libcrypto`
**Cause:** SSH key secret has a newline. `echo "$SECRET" > file` keeps it; OpenSSH can't parse.
**Fix:** `printf '%s' "$SECRET" | tr -d '\r' > file`. Workflows: `deploy-test.yml`, `deploy-dev.yml`.

### Pattern B: `File exists (os error 17)` on `.venv`
**Cause:** A sibling workflow left `.venv` behind. `uv sync` refuses to overwrite.
**Fix:** `rm -rf .venv && uv sync ...`. Affected: `tooling.yml` (was broken), `ci.yml` (already had the fix), `dev-ci.yml` (added with the fix).

### Pattern C: `Can't load plugin: sqlalchemy.dialects:sqlite`
**Cause:** `uv sync --only-group dev-base --no-default-groups` skipped dependencies. Use `--all-extras` or `--group dev` instead.
**Fix:** change the workflow's `uv sync` invocation.

### Pattern D: `JSONDecodeError` on a route test
**Cause:** real bug. An endpoint does `await request.json()` without try/except. Empty body → 500.
**Fix:** wrap the call:
```python
try:
    body = await request.json()
except Exception:
    raise HTTPException(status_code=400, detail="Invalid JSON body")
```

### Pattern E: `Level must be one of ['PASS', 'IGNORE', 'INFO', 'WARN', 'FAIL']`
**Cause:** `.github/.zap-rules.tsv` has invalid action values. ZAP action v0.10+ only accepts those 5.
**Fix:** regenerate via `zap-api-scan.py -g`, then customize.

### Pattern F: `SAWarning: Column-expression-level unary distinct() should not be used outside of an aggregate function`
**Cause:** SQLAlchemy 2.0 deprecation. `func.distinct(col)` outside aggregate → use `select(col).distinct()`.
**Fix:** refactor the query.

## Step 2: Check sibling-session collisions

Multiple agents pushing in tight windows can cause:
- `.venv` collisions (Pattern B)
- Race conditions in dev/test deploys (one branch wins, the other gets a "redeploy" message)

**Recovery:**
1. Wait 60s for sibling to finish.
2. Re-run the failed workflow: `gh run rerun <run-id> --failed`.
3. If still failing after 2 retries, the cause is real, not a collision.

## Step 3: Check BWS token expiry

The BWS access token in `/etc/sazon/bws-token` expires. Symptoms:
- `bws secret list` returns 401
- Deploys fail at the `write_env_file.py` step with a BWS API error
- env file is empty on the VPS (`cat /etc/sazon/.env.test`)

**Fix:**
```bash
# Get a new token from BWS dashboard
ssh root@38.9.96.179
BWS_TOKEN="0.14fe0cd6-..." bash /opt/build-apps/sazon-rms/scripts/install_bws_token.sh
```

## Step 4: Check the actual service on the VPS

```bash
ssh root@38.9.96.179

# Are the services running?
docker service ls | grep saskia

# What's the current image?
docker service inspect saskia-test_web --format '{{.Spec.TaskTemplate.ContainerSpec.Image}}'

# Recent logs
docker service logs saskia-test_web --tail 30

# Resource pressure
docker stats --no-stream | head -20
```

Common issues:
- **0/1 replicas** = crashed on boot. Check logs.
- **1/1 but 500 on /healthz** = app-level error (DB, BWS, etc.)
- **OOMKilled** = the resource limit is too low. Bump in `deploy/envs.yaml` + redeploy.

## Step 5: Verify DNS

```bash
# Should be A record, not CNAME (CF-proxy returns 404 for test/dev)
dig +short saskia-test.paragu-ai.com
dig +short saskia-dev.paragu-ai.com
dig +short saskia-vps.paragu-ai.com
# All should return 38.9.96.179
```

If any returns a Cloudflare IP, change the DNS record to an A record (not CNAME).

## Step 6: Promote a known-good image

If a new deploy is broken and the old one was good, you can promote:

```bash
# Find the last working image on test
ssh root@38.9.96.179 'docker images sazon-rms:test-* --format "{{.Tag}} {{.CreatedAt}}" | head -5'

# Re-tag the working one and force-update prod
ssh root@38.9.96.179 "docker tag sazon-rms:test-20261009-154017 sazon-rms:prod-recovery"
ssh root@38.9.96.179 "docker service update --image sazon-rms:prod-recovery saskia-vps_web --force"
```

## Step 7: Last resort — full reset

If everything is broken, you can do a clean reset on the VPS:

```bash
# Remove the broken stack (keeps the volume)
ssh root@38.9.96.179 "docker stack rm saskia-test"

# Wait for it to drain
sleep 30

# Re-deploy from your local
SASKIA_VPS_SSH_KEY=/opt/data/.ssh/id_ed25519 \
  ./scripts/deploy.sh --env=test
```

The data volume (`saskia-test-data`) is preserved. If you also need to wipe the DB:

```bash
ssh root@38.9.96.179 "docker volume rm saskia-test-data"
```

## Prevention: branch protection

The #1 way to keep this from happening again: **require status checks on main**. See `docs/operations/2026-10-09-three-env-deploy.md` §"Auto-deploy (CI)" for the recommended 4-check setup.

## Prevention: pre-commit hook

The repo has a pre-commit config (`.pre-commit-config.yaml`) with 14 hooks. Install it once and 90% of lint failures never reach the CI:

```bash
pip install pre-commit
pre-commit install
```

## Contact

- Owner: Ivan (`ivan@aiwhisperers.dev`)
- Resend alerts go to `ivan@aiwhisperers.dev` on CI failure (push to main only)
- For deeper issues, see `docs/operations/2026-10-09-three-env-deploy.md`
