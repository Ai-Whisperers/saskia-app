# Three-environment deploy — operator runbook

**Date:** 2026-10-09
**Status:** Implemented on `feat/three-env-deploy`. Awaiting Cloudflare DNS + BWS bootstrap to ship.

## What this is

Three Swarm stacks sharing one VPS, one Traefik instance, and one `traefik-public` overlay network. Each env has its own hostname, image tag, SQLite volume, BWS-driven env file, Traefik middleware, and backup schedule.

```
saskia-vps.paragu-ai.com   →  saskia       stack  (prod)   sazon-rms:prod-YYYYMMDD-HHMMSS
saskia-test.paragu-ai.com  →  saskia-test  stack  (test)   sazon-rms:test-YYYYMMDD-HHMMSS
saskia-dev.paragu-ai.com   →  saskia-dev   stack  (dev)    sazon-rms:dev-YYYYMMDD-HHMMSS
```

## One-time bootstrap (do these BEFORE first deploy)

### 1. Cloudflare DNS — add 2 CNAMEs

In the Cloudflare dashboard for `paragu-ai.com`:

| Type | Name | Target | Proxied |
|---|---|---|---|
| CNAME | `saskia-test` | `paragu-ai.com` | ✅ (orange cloud) |
| CNAME | `saskia-dev` | `paragu-ai.com` | ✅ (orange cloud) |

`saskia-vps` already exists (it serves prod today).

After ~30s, verify:
```bash
dig +short saskia-test.paragu-ai.com
dig +short saskia-dev.paragu-ai.com
# both should resolve to Cloudflare IPs (orange-cloud proxied)
```

### 2. Bitwarden Secrets — create 2 new keys

The 3 envs share most BWS keys (Supabase, CF, R2, Sentry, Resend). The exceptions are the per-env user passwords. Add to BWS project `a1d64864-...`:

- `SASKIA_TEST_USER_PASSWORD` — bcrypt hash (use `python -c "import bcrypt; print(bcrypt.hashpw(b'change-me-test', bcrypt.gensalt()).decode())"`)
- `SASKIA_DEV_USER_PASSWORD` — same approach

`SASKIA_USER_PASSWORD` and `SASKIA_ADMIN_PASSWORD` already exist (used by prod today).

### 3. VPS — install the BWS token

```bash
ssh root@paragu-ai
BWS_TOKEN="0.14fe0cd6-..."  bash /tmp/install_bws_token.sh
# or run interactively and paste the token
```

This writes `/etc/sazon/bws-token` (mode 0400, root-only) and installs the `bws` CLI if missing.

### 4. VPS — first deploy of test + dev

After the DNS resolves and the token is installed:

```bash
# From your local repo (must be on feat/three-env-deploy or main once merged):
cd /opt/data/profiles/ivan/scratch/saskia-app-work
bash scripts/deploy.sh --env=test    # builds saskia-test stack
bash scripts/deploy.sh --env=dev     # builds saskia-dev stack
```

Each deploy takes ~3-5 min. Verify:
```bash
curl -sk https://saskia-test.paragu-ai.com/healthz   # expect {"status":"ok",...}
curl -sk https://saskia-dev.paragu-ai.com/healthz    # expect {"status":"ok",...}
```

## Daily usage

### Ship a feature branch to dev (AI-agent path)

Every push to a non-main branch auto-deploys via `.github/workflows/deploy-dev.yml`. No action needed. The agent that pushed last wins; siblings can re-push to redeploy.

To manually deploy from your laptop:
```bash
git checkout feat/my-feature
bash scripts/deploy.sh --env=dev
# Verify at https://saskia-dev.paragu-ai.com/
```

### PR → test (CI auto-deploys)

`.github/workflows/deploy-test.yml` runs on `pull_request: opened/synchronize/reopened` to main. The PR's HEAD is what gets deployed to saskia-test. Reviewer can click the `https://saskia-test.paragu-ai.com/` link in the PR description to verify.

To manually deploy (e.g. on a hotfix before opening a PR):
```bash
git checkout fix/something
bash scripts/deploy.sh --env=test
```

### Promote a tested build to prod

**Option A — manual, after PR merge:**
```bash
git checkout main && git pull --ff-only
bash scripts/release.sh
# bumps CHANGELOG, tags vYYYY.MM.PATCH, pushes, deploys to prod
```

**Option B — re-tag an existing build (faster, no rebuild):**
```bash
# The test env is running the build you want. Promote it.
bash scripts/promote.sh --from=test --to=prod
# Re-tags the test image as the prod tag and force-updates saskia_web.
# No rebuild, no CHANGELOG bump, no git tag.
# Use this for hotfixes between scheduled releases.
```

### Tear down a dev stack (e.g. after a feature merges)

Dev is cheap; usually you leave it. If you need to free disk:
```bash
ssh root@paragu-ai 'docker stack rm saskia-dev && docker volume rm saskia-dev-data'
# This does NOT delete the saskia-prod-data or saskia-test-data volumes.
```

## How secrets flow

```
BWS (project a1d64864-...)
  ↓ bws secret list
deploy/write_env_file.py
  ↓ /etc/sazon/.env.<env> (mode 0600, root-only)
docker stack deploy -c docker-stack.<env>.yml saskia-<env>
  ↓ swarm mounts the env_file
container's environment (SENTRY_DSN, SUPABASE_URL, FERNET_KEY, ...)
```

Secrets never appear in:
- The rendered `docker-stack.<env>.yml` (uses `env_file: <path>`, not `environment:`)
- `docker service inspect saskia-<env>_web` output (env_file is read at container start, not in the service spec)
- The git history
- The image (build context excludes `/etc/sazon/`)

To rotate a secret:
1. Update it in BWS.
2. Run `python3 deploy/write_env_file.py --env=<env>` on the VPS (it'll rewrite because the SHA changed).
3. Run `docker service update --force saskia-<env>_web` to pick up the new env_file (or just run a fresh deploy).

## Verifying a deploy

Per the saskia-rms-deploy-flow skill's verify-after-deploy ladder:

```bash
ENV=prod  # or test or dev
HOST="saskia-vps.paragu-ai.com"
[ "$ENV" = "test" ] && HOST="saskia-test.paragu-ai.com"
[ "$ENV" = "dev" ]  && HOST="saskia-dev.paragu-ai.com"

# 1. Healthz (this is the auth-exempt endpoint)
curl -sk "https://$HOST/healthz"     # expect {"status":"ok",...}

# 2. Running task is fresh (NOT older than your deploy)
ssh root@paragu-ai "docker service ps saskia-${ENV}_web --format '{{.Image}} {{.CurrentState}}' | head -3"
# Top row must show 'sazon-rms:<env>-<timestamp> Running <seconds> ago'

# 3. Schema version matches code
ssh root@paragu-ai "CID=\$(docker ps -q -f label=com.docker.swarm.service.name=saskia-${ENV}_web | head -1); \
  docker exec \$CID python -c 'from app.rms.db import make_engine; from sqlalchemy import text; print(make_engine().connect().execute(text(\"SELECT value FROM app_meta WHERE key=\\\"schema_version\\\"\")).scalar())'"
# Compare to: grep CURRENT_SCHEMA_VERSION app/rms/config.py
# Both must match.

# 4. Tail service logs for the NEW container (filter by CID, not service name)
ssh root@paragu-ai "CID=\$(docker ps -q -f label=com.docker.swarm.service.name=saskia-${ENV}_web | head -1); \
  docker logs \$CID --tail 100 2>&1 | grep -iE 'error|exception|traceback' | head -10"
# 0 lines = healthy. Anything else = investigate before declaring done.
```

## Troubleshooting

### Deploy says "OK" but healthz is 404

The saskia-rms-deploy-flow skill's "stale service name" trap. Verify the running task:
```bash
ssh root@paragu-ai 'docker service ps saskia-<env>_web --format "{{.Image}} {{.CurrentState}}" | head -3'
```
If `no such service`, the deploy is pointing at the wrong stack name. Check `deploy/envs.yaml[env].stack_name` matches what's actually deployed:
```bash
ssh root@paragu-ai 'docker stack ls'
```

### Prod healthz says "ok" but login fails with "credenciales inválidas"

The saskia-rms-development skill's DRIFT-3 env var trap. Both `AIW_RMS_DB_PATH` and `AIW_SASKIA_DB_PATH` must point to the same SQLite file. Verify the env_file has them both:
```bash
ssh root@paragu-ai 'docker exec $(docker ps -q -f label=com.docker.swarm.service.name=saskia-prod_web | head -1) env | grep -E "AIW_(RMS|SASKIA)_DB_PATH"'
# Expect:
#   AIW_RMS_DB_PATH=/data/rms.sqlite
#   AIW_SASKIA_DB_PATH=/data/rms.sqlite
# If only one is set, edit deploy/docker-stack.template.yml and re-deploy.
```

### Cloudflare returns 521 (Web server is down)

Traefik can't reach the swarm service. Verify:
```bash
ssh root@paragu-ai 'docker service ps saskia-prod_web --format "{{.Image}} {{.CurrentState}}" | head -3'
# If "Running 0/1", the service is down. Check:
ssh root@paragu-ai 'docker service logs saskia-prod_web --tail 30'
# Common cause: BWS env file is missing or empty. Re-run:
ssh root@paragu-ai 'python3 /opt/build-apps/sazon-rms/deploy/write_env_file.py --env=prod'
```

### Two AI agents on different branches both deploy to dev at the same time

Per `docs/operations/2026-10-04-sibling-session-coordination.md`, this is expected behavior. The agent that pushed most recently wins. The losing agent should re-push to redeploy:
```bash
# On the loser's branch:
git commit --allow-empty -m "redeploy: re-trigger dev deploy"
git push origin <branch>
```

### `bws secret list` returns 401 Unauthorized

The token in `/etc/sazon/bws-token` is expired or revoked. Get a new one from BWS and re-run `scripts/install_bws_token.sh` on the VPS.

### Want to add a 4th env (e.g. staging)

1. Add a row to `deploy/envs.yaml` with all the env-specific values.
2. Add the env name to `ALLOWED_ENVS` in `deploy/render_stack.py` and `deploy/write_env_file.py`.
3. Add a Cloudflare CNAME for the hostname.
4. Create a BWS secret set (or reuse prod's if isolation isn't required).
5. Update `scripts/deploy.sh` with the per-env stack name + service name + cron schedule.
6. Update `scripts/promote.sh` with the allowed directions.
7. Add tests to `tests/test_deploy_infra.py`.

## Files in this change

| File | What it does |
|---|---|
| `deploy/docker-stack.template.yml` | One template, three envs |
| `deploy/envs.yaml` | Per-env config (hostname, volumes, CSP, BWS keys) |
| `deploy/render_stack.py` | Template + envs.yaml → docker stack yml |
| `deploy/write_env_file.py` | BWS → /etc/sazon/.env.<env> (idempotent) |
| `scripts/deploy.sh` | Per-env deploy (replaces deploy-to-vps.sh) |
| `scripts/promote.sh` | Re-tag + force-update between envs |
| `scripts/release.sh` | CHANGELOG bump + tag + push + prod deploy |
| `scripts/install_bws_token.sh` | One-time BWS token install on VPS |
| `.github/workflows/deploy-test.yml` | PR auto-deploy to test |
| `.github/workflows/deploy-dev.yml` | Push auto-deploy to dev |
| `tests/test_deploy_infra.py` | 28 tests for the above |
| **Removed** `deploy-to-vps.sh` | Old single-env script (replaced) |
| **Removed** `docker-stack.yml` (root) | Old single-env stack with hardcoded secrets |
| **Removed** `tests/test_deploy_script.py` | Old dry-run tests (superseded) |

---

## 2026-10-09 Post-deployment lessons (what we learned shipping this)

The 3-env deploy went live 2026-10-09. 4 of 11 tracked GitHub Actions workflows
went from broken-on-every-push to green-on-every-push. The fixes are recorded
here so the next deploy doesn't repeat them.

### What broke in the first deploy

1. **Deploy test + Deploy dev SSH key error**: `Load key ~/.ssh/id_ed25519: error in libcrypto`. The GH Secret was a multi-line key. `echo "$SECRET" > file` preserves the newlines, which OpenSSH can't parse. Fix: `printf '%s' "$SECRET" | tr -d '\r' > file`.
2. **Tooling workflow `.venv: File exists`**: a sibling workflow left `.venv` behind. `uv sync` refuses to overwrite. Fix: `rm -rf .venv && uv sync --all-extras --group dev`.
3. **Route Smoke tests caught two real bugs** (uncovered only when the deploy test workflow started running the smoke):
   - `POST /ventas/nueva/multi` returned 500 with `JSONDecodeError` on empty body. Fix: wrap `await request.json()` in try/except → 400.
   - `GET /reportes/precios` triggered a SQLAlchemy 2.0 deprecation: `column.distinct().where(...)` should be `select(column).distinct().where(...)`. Fix: refactor the query.
4. **No gate on dev deploys**: broken code landed on dev 9/9 times because `deploy-dev.yml` had no quality gate. Fix: added `.github/workflows/dev-ci.yml` that runs lint + fast test + CHANGELOG discipline before `deploy-dev`.

### What works now (verified live)

- `saskia-vps.paragu-ai.com` (prod) — `saskia-vps_web` 1/1
- `saskia-test.paragu-ai.com` (test) — `saskia-test_web` 1/1, seeded with La Vaquita data
- `saskia-dev.paragu-ai.com` (dev) — `saskia-dev_web` 1/1, seeded with La Vaquita data
- Login: `saskia` / `saskia1234` works on all 3 (prod uses Supabase; test/dev use local-bcrypt)
- Healthz: 200 on all 3

### Next steps (operator checklist)

- [ ] **Click branch protection on main** (Settings → Branches → main):
  - Require: Currency Drift Lint, Smoke (deploy-shape), Browser (Playwright), Route Smoke
  - Require linear history
  - Include administrators
- [ ] **Standardize GH secret name** to `SASKIA_VPS_SSH_KEY` (currently aliased from `VPS_KEY`)
- [ ] **Promote `security-zap.yml` to required** after 2 consecutive clean weekly runs
- [ ] **Add `release.yml`** to auto-deploy on CalVer tag push (currently manual via `release.sh`)
- [ ] **Resolve CI budget** (A: public repo, B: GH Pro, C: move CI off GH Actions)

### The full audit

The complete analysis of every workflow + their real failure patterns is in
the 2026-10-09 conversation history. Key numbers:

| Workflow | Before 2026-10-09 | After |
|---|---|---|
| Tooling | 0/10 success | ✅ (`.venv` fix + concurrency block) |
| Security ZAP | 0/10 success | ⚠️ (TSV needs regenerate; deferred) |
| Deploy test | 0/10 success | ✅ (SSH key fix) |
| Deploy dev | 0/9 success | ✅ (SSH key fix) |
| Route Smoke | 0/10 success | ✅ (real bugs fixed) |
| CI | 0/10 success | ✅ (lint + format clean) |
| qa-gates | 0/10 success | ⚠️ (external service; deferred) |
| Browser | 9/10 success | ✅ (unchanged) |
| Currency Drift | 10/10 success | ✅ (unchanged) |
| Smoke | 10/10 success | ✅ (unchanged) |
