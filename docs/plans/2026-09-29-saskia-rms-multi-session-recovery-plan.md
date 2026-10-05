# Sazón — Multi-Session Recovery & Forward Plan

**Date:** 2026-09-29
**Author:** Hermes (Ivan's profile)
**Scope:** Recover and ship the work from 4 sessions (20260921 / 20260929×3), close all open items, ship B7/B6/test gaps, clean up the two diverged worktrees, deploy every committed-but-not-live change, prevent the same drift from happening again.
**Repo:** `Ai-Whisperers/sazon-app`
**Live URL:** https://sazon-vps.paragu-ai.com (ServaRica VPS, Docker Swarm + Traefik)

---

## TL;DR — what this plan does

Five concrete passes, in strict order. Each pass has a verifiable end state before the next begins.

| Pass | Goal | Verifier | Time |
|---|---|---|---|
| **P0 — Recover** | Deploy `100e579` + `3818301` to live; auto-repair Panceta + Pan rallado on live DB | `audit_repair.py` exists in container, `/inventario/auditoria-etiquetas` shows 0 issues | 15 min |
| **P1 — Stabilize worktrees** | Pick one canonical worktree, push 30+5 commits to origin, kill the other | `git status -sb` shows `[ahead 0, behind 0]` on both branches | 20 min |
| **P2 — Ship uncommitted work** | Commit + push B7 insights card, C4/C5 tests, combo `data-source` alias, recipe form fixes | CI green; new commits pushed; no work in `git status` | 45 min |
| **P3 — Close pre-existing bugs** | Fix `pedido_publico.html` CSRF gap, deduplicate `parse_money_gs`, add `/healthz/errors` alert | Tests pass; live endpoint OK | 30 min |
| **P4 — Prevent recurrence** | Pre-commit deploy hook, worktree policy doc, schema-version discipline, logging audit follow-through | Document committed; `git push` triggers rebuild | 45 min |

**Total: ~2.5 h of focused work, single operator flow.** Spread across two evenings if you want review checkpoints.

---

## P0 — Recover: ship what's already committed but not live

### Why this is P0

Two days of work (`100e579` audit auto-repair + `3818301` P0 audit log) is sitting on the scratch worktree's `main` branch, **30 commits ahead of `origin/main`**, never pushed, never deployed. The live `/inventario/auditoria-etiquetas` page is showing Panceta (#62) + Pan rallado (#66) with `sin gluten` still on the ingredient because the auto-repair migration never ran. Session 1 explicitly closed the work and shipped "100e579" but the deploy never happened.

This is the single biggest correctness gap. Fixing it touches 4 ingredients in the live DB automatically.

### Steps

1. **Confirm pre-deploy state** (read-only check)
   ```bash
   cd /opt/data/profiles/ivan/scratch/sazon-app-work
   git log --oneline origin/main..HEAD | head -5
   # Expected: 3818301, 100e579, 8fdacb3, 02f6931, 3fc7d68
   ```

2. **Rebuild the prod image** (with `DOCKER_BUILDKIT=0` per memory gotcha)
   ```bash
   cd /opt/data/profiles/ivan/scratch/sazon-app-work
   DOCKER_BUILDKIT=0 docker build --no-cache -t sazon-rms:prod -f Dockerfile . 2>&1 | tail -20
   ```

3. **Verify the new file is in the image** (don't trust "build succeeded")
   ```bash
   docker run --rm sazon-rms:prod bash -c 'ls -la /app/app/rms/tagging/audit_repair.py /app/app/templates/ventas_qa.html'
   # Expected: both files exist
   ```

4. **Deploy via Docker Swarm**
   ```bash
   docker service update --image sazon-rms:prod sazon-vps_web --force
   sleep 8  # let the migration run on startup
   ```

5. **Verify live**
   ```bash
   # Health check
   curl -sk -o /dev/null -w "%{http_code}\n" https://sazon-vps.paragu-ai.com/healthz
   # Expected: 200
   
   # Audit page should now show 0 issues after auto-repair migration runs
   curl -sk https://sazon-vps.paragu-ai.com/inventario/auditoria-etiquetas | grep -c 'Panceta\|Pan rallado\|Café espresso\|Jengibre'
   # Expected: 0 (after auto-repair runs on first request)
   
   # /ventas/qa page should now be reachable (login required)
   curl -sk -o /dev/null -w "%{http_code}\n" https://sazon-vps.paragu-ai.com/ventas/qa
   # Expected: 401 (auth required) or 200, NOT 404
   
   # Ingredient state on live DB should be clean
   ssh -i /opt/data/.ssh/id_ed25519 root@38.9.96.179 \
     "docker exec \$(docker ps -q -f name=sazon-vps_web) python -c \"
   import sqlite3
   c=sqlite3.connect('/data/rms.sqlite').cursor()
   c.execute('SELECT id,name,allergens,dietary_tags FROM ingredient WHERE id IN (62,66,39,70)')
   for r in c.fetchall(): print(r)
   \""
   # Expected: Panceta no longer has 'sin gluten'; Pan rallado no longer has 'sin gluten'; Jengibre in 'especias' not 'carnes'
   ```

6. **Push the branch** so it isn't stranded on the scratch worktree
   ```bash
   git push origin main
   # Expected: 30 commits pushed, origin/main catches up
   ```

### Acceptance criteria

- [ ] Live `sazon-rms:prod` container contains `app/rms/tagging/audit_repair.py` and `app/templates/ventas_qa.html`
- [ ] `/inventario/auditoria-etiquetas` shows 0 ingredientes con problemas after auto-repair runs
- [ ] Live DB: Panceta #62, Pan rallado #66 dietary_tags no longer contain `sin gluten`
- [ ] Live DB: Jengibre #70 category is `especias` not `carnes`
- [ ] `/ventas/qa` returns 200 or 401 (not 404)
- [ ] `origin/main` is `[ahead 0, behind 0]` of the scratch worktree's `main`

### Rollback

If anything breaks, the previous live image is the one tagged `sazon-rms:prod` before this rebuild — Docker Swarm keeps the last 3. Roll back with:
```bash
docker service update --image sazon-rms:prod sazon-vps_web --rollback
```

---

## P1 — Stabilize the two diverged worktrees

### The problem

Two clones of the same repo with different states:

| Worktree | Path | Branch | HEAD | State |
|---|---|---|---|---|
| Scratch | `/opt/data/profiles/ivan/scratch/sazon-app-work` | `main` | `3818301` | 30 ahead of origin, 13 files uncommitted (B7 subagent + C4/C5 tests) |
| Production | `/opt/data/work/sazon-app` | `feature/ui-master-menu` | `7bee267` | 5 ahead of origin/main, 13 files modified (combo alias + form fixes), tests interrupted |

The scratch tree is what the live deployment runs from (after this session's deploy). The production tree has different uncommitted UI work and a different branch. We can't keep both — git will fight us on the next deploy.

### Decision: keep both, designate roles

**Recommendation: keep both worktrees but designate them.**

| Worktree | New role | Branch | Push policy |
|---|---|---|---|
| `/opt/data/profiles/ivan/scratch/sazon-app-work` | **Main + deploy source** | `main` | `git push origin main` after every commit; deploy via `DOCKER_BUILDKIT=0 docker build` |
| `/opt/data/work/sazon-app` | **Feature development** | `feature/ui-master-menu` → PR to `main` | All changes via PR; never direct-push to main; CI gate before merge |

The reasoning: the scratch tree is what session 1 deployed from, it's the path `MEMORY.md` references for the deploy command, and changing it now means rebuilding the deploy script and memory. The production tree is the "real" working copy Ivan uses daily — it should stay as the dev branch.

### Steps

1. **Push scratch `main` first** (do P0 step 6 first)
   ```bash
   cd /opt/data/profiles/ivan/scratch/sazon-app-work
   git push origin main
   ```

2. **In the production worktree, fetch + rebase against the freshly-pushed main**
   ```bash
   cd /opt/data/work/sazon-app
   git fetch origin
   git checkout main
   git rebase origin/main  # should be no-op or trivial
   git checkout feature/ui-master-menu
   git rebase main  # pull in the new commits from main
   ```
   Expect: feature branch now includes `3818301`, `100e579`, etc.

3. **Verify nothing is broken on the rebased feature branch**
   ```bash
   cd /opt/data/work/sazon-app
   timeout 300 ./.venv/bin/python -m pytest tests/ -x --tb=short -q \
     --ignore=tests/test_performance.py \
     --ignore=tests/browser 2>&1 | tail -5
   # Expected: ~120+ tests pass (one pre-existing CSRF failure on pedido_publico.html is OK)
   ```

4. **Document the worktree policy** — `docs/operations/worktree-policy.md` (created in P4 below)

5. **Add a pre-push reminder to the scratch worktree's shell init** — `echo "git push origin main && cd /opt/data/work/sazon-app && git fetch && git rebase origin/main" >> ~/.bashrc.sazon-rms`

### Acceptance criteria

- [ ] `origin/main` matches scratch `main` HEAD exactly
- [ ] `feature/ui-master-menu` rebases cleanly onto the new `main`
- [ ] Pytest still passes on the rebased feature branch
- [ ] `docs/operations/worktree-policy.md` exists (P4 work) and is referenced in AGENTS.md

---

## P2 — Ship the uncommitted work

There are **two batches of uncommitted work** to ship: one in scratch, one in production.

### P2a — Scratch tree (B7 subagent + C4/C5 tests)

The scratch tree has 13 uncommitted files. The origins:

| File | Origin | Action |
|---|---|---|
| `app/rms/insights.py` (M) | B7 subagent | Review + commit (see below) |
| `app/rms/main.py` (M) | B7 subagent (registered insights router) | Review + commit |
| `app/routers/dashboard.py` (M) | B7 subagent | Review + commit |
| `app/static/shortcuts.js` (M) | P1-B6 (cmd-K shortcuts) | Commit |
| `app/templates/analisis.html` (M) | B7 subagent + C4 semáforo | Commit |
| `app/templates/base.html` (M) | B7 subagent | Commit |
| `app/templates/inicio.html` (M) | B7 subagent | Commit |
| `app/routers/insights.py` (??) | B7 subagent (new file) | Review + commit |
| `app/static/ui-insight.js` (??) | B7 subagent (new component) | Review + commit |
| `tests/test_c4_food_cost_semaphor.py` (??) | C4 work (Camila's semáforo) | Commit |
| `tests/test_c5_test_gaps.py` (??) | C5 audit doc | Commit |
| `tests/test_p1_b6_cmdk_shortcuts.py` (??) | P1-B6 cmd-K | Commit |
| `tests/test_p1_b7_insights.py` (??) | B7 subagent tests | Commit |
| `debug_main.py` (??) | Operator scratch — should NOT commit | **Delete** |
| `test_import.py` (??) | Operator scratch | **Delete** |
| `test_main_simulation.py` (??) | Operator scratch | **Delete** |
| `test_router.py` (??) | Operator scratch | **Delete** |

**B7 subagent status (per session 2 transcript)**: the subagent was running 670+ seconds debugging route 404s. It eventually finished and reported the work done, but the report was unverified. We need to:

1. Read the subagent's live transcript to see what it actually changed
2. Verify the `/inicio` page shows 3 actionable insights
3. Run the new tests to confirm they pass

**Steps**:

1. **Delete debug scratch files first** (they pollute git status)
   ```bash
   cd /opt/data/profiles/ivan/scratch/sazon-app-work
   rm -f debug_main.py test_import.py test_main_simulation.py test_router.py
   ```

2. **Read the B7 subagent's live transcript to see what it shipped**
   ```bash
   # Find the latest B7 transcript
   ls -lat /opt/data/profiles/ivan/cache/delegation/live/ 2>/dev/null | head -3
   # Read the most recent one
   tail -100 /opt/data/profiles/ivan/cache/delegation/live/<most-recent-dir>/task-1.log
   ```

3. **Run the new tests in isolation to confirm they pass**
   ```bash
   cd /opt/data/profiles/ivan/scratch/sazon-app-work
   timeout 120 ./.venv/bin/python -m pytest tests/test_p1_b7_insights.py tests/test_c4_food_cost_semaphor.py tests/test_c5_test_gaps.py tests/test_p1_b6_cmdk_shortcuts.py -v --tb=short 2>&1 | tail -30
   ```

4. **Visual smoke-test the /inicio page in dev**
   ```bash
   cd /opt/data/profiles/ivan/scratch/sazon-app-work
   SASKIA_TEST_AUTH_DISABLED=1 ./.venv/bin/python -c "
   from fastapi.testclient import TestClient
   from app.rms.main import app
   c = TestClient(app)
   r = c.get('/inicio')
   print('status:', r.status_code, 'len:', len(r.text))
   for m in ['Restock urgente', 'Stock bajo', 'Cliente recurrente', 'insight-card', 'data-insight-id']:
     print(f'  {m!r}: {\"OK\" if m in r.text else \"MISSING\"}')
   "
   ```

5. **Commit only verified work**
   ```bash
   cd /opt/data/profiles/ivan/scratch/sazon-app-work
   git add app/rms/insights.py app/rms/main.py app/routers/dashboard.py \
           app/static/shortcuts.js app/templates/analisis.html app/templates/base.html \
           app/templates/inicio.html app/routers/insights.py \
           app/static/ui-insight.js \
           tests/test_c4_food_cost_semaphor.py tests/test_c5_test_gaps.py \
           tests/test_p1_b6_cmdk_shortcuts.py tests/test_p1_b7_insights.py
   git -c user.email=hermes@nous.local -c user.name=Hermes commit -m "..."
   ```

6. **Push**
   ```bash
   git push origin main
   ```

7. **Deploy** (don't skip this — same trap as P0)
   ```bash
   DOCKER_BUILDKIT=0 docker build --no-cache -t sazon-rms:prod -f Dockerfile . && \
   docker service update --image sazon-rms:prod sazon-vps_web --force
   ```

### P2b — Production tree (combo alias + form fixes)

The production tree has 13 modified files + 17 untracked. The untracked breakdown:

| Path | Action |
|---|---|
| `LOGGING_ERRORS_AUDIT_2026-09-29.md` | Commit (it's a real artifact) |
| `LOGGING_STATUS_2026-09-29.md` | Commit |
| `docs/plans/2026-09-23-second-review-execution-plan.md` | Commit (also a real artifact) |
| `app/static/combo-rows.js` | Review + commit |
| `app/static/combobox.css` | Review + commit |
| `app/static/uploads/20260929-*.png` (×14) | **Do NOT commit** — `.gitignore` them (P4 work) |

The modified files are mostly related to:
- `<ui-combo>` `data-source` alias (compatibility with v1 markup + tests)
- `row-label` macro param for per-instance row renderers
- `inventario_form.html` + `receta_form.html` UI tweaks
- `inventory.py` + `recipes.py` route additions

**Steps**:

1. **Run the interrupted pytest first** — was running when session 4 ended
   ```bash
   cd /opt/data/work/sazon-app
   timeout 600 ./.venv/bin/python -m pytest tests/ --tb=no -q \
     --ignore=tests/test_performance.py --ignore=tests/browser 2>&1 | tail -20
   ```

2. **Verify the combo alias doesn't break the picker** (this was the v51 critical fix)
   ```bash
   cd /opt/data/work/sazon-app
   SASKIA_TEST_AUTH_DISABLED=1 ./.venv/bin/python -c "
   from fastapi.testclient import TestClient
   from app.rms.main import app
   c = TestClient(app)
   for path in ['/ventas', '/clientes', '/inventario/nuevo']:
     r = c.get(path)
     print(f'{path}: status={r.status_code}, len={len(r.text)}, has_combo={\"<ui-combo\" in r.text}')
   "
   ```

3. **Move screenshots out of the way** so they don't block staging
   ```bash
   cd /opt/data/work/sazon-app
   mkdir -p .scratch/2026-09-29-screenshots
   git mv app/static/uploads/20260929-*.png .scratch/2026-09-29-screenshots/ 2>/dev/null || \
     mv app/static/uploads/20260929-*.png .scratch/2026-09-29-screenshots/
   # These will be .gitignored via the .gitignore rule added in P4
   ```

4. **Commit in 2 logical batches** (smaller, reviewable commits)

   **Batch A — combo component compat + row-label macro:**
   ```bash
   git add app/static/ui-combo.js app/templates/_components/atoms.html \
           app/static/combo-rows.js app/static/combobox.css \
           tests/test_combo_extension.py
   git commit -m "feat(ui-combo): data-source alias + row-label macro param"
   ```

   **Batch B — recipe/inventory form fixes + route additions:**
   ```bash
   git add app/routers/inventory.py app/routers/recipes.py app/rms/main.py \
           app/templates/inventario_form.html app/templates/receta_form.html \
           app/templates/base.html \
           tests/test_merma_combos.py tests/test_pedido_combos.py \
           tests/test_receta_form_combo.py tests/fixtures/herbus_drive_sample.xlsx
   git commit -m "feat(forms): recipe/inventory form fixes + combo integration"
   ```

   **Batch C — docs:**
   ```bash
   git add LOGGING_ERRORS_AUDIT_2026-09-29.md LOGGING_STATUS_2026-09-29.md \
           docs/plans/2026-09-23-second-review-execution-plan.md
   git commit -m "docs(audit): logging/errors audit + 2nd-review execution plan"
   ```

5. **Push the feature branch + open a PR**
   ```bash
   git push origin feature/ui-master-menu
   # Then create the PR via gh CLI or browser:
   gh pr create --base main --head feature/ui-master-menu \
     --title "feat: ui-master-menu (combo alias + form fixes + logging audit)" \
     --body "Closes: refactor the combo + form layer. Adds data-source alias for back-compat. See LOGGING_ERRORS_AUDIT for the full observability findings."
   ```

6. **Wait for CI green on the PR, then merge to main**
   ```bash
   # After CI:
   gh pr merge --squash
   ```

7. **Pull main into the scratch worktree and deploy**
   ```bash
   cd /opt/data/profiles/ivan/scratch/sazon-app-work
   git pull origin main  # gets the squash-merged commits
   DOCKER_BUILDKIT=0 docker build --no-cache -t sazon-rms:prod -f Dockerfile . && \
   docker service update --image sazon-rms:prod sazon-vps_web --force
   ```

### Acceptance criteria

- [ ] Scratch tree `git status` shows no uncommitted changes (except the 14 PNGs which get gitignored)
- [ ] Production tree `feature/ui-master-menu` has 3+ atomic commits with sensible messages
- [ ] PR is open and CI green
- [ ] Live deployment reflects the merged combo + form fixes
- [ ] `/ventas`, `/clientes`, `/inventario/nuevo` all still render with `<ui-combo>` working

---

## P3 — Close pre-existing bugs

### P3a — `pedido_publico.html` missing CSRF token

**Bug**: The CSRF middleware was added in `056e422` but the public comprobante upload template (`app/templates/pedido_publico.html`, added in `8fdacb3`) was never retrofitted with the token. Discovered by session 3.

**Risk**: CSRF protection is bypassed for the public `/p/{token}` upload endpoint — an attacker could trick a logged-in user into uploading a fake comprobante.

**Fix** (5 min):
1. Read `app/templates/pedido_publico.html`
2. Find the `<form>` for upload
3. Add the CSRF token: `{{ csrf_input() }}` or whatever pattern the other templates use (check `app/templates/_components/atoms.html` for the macro)
4. Confirm test `tests/test_p0_confirm_modal_csrf.py::test_all_post_forms_have_csrf` passes
5. Commit on main: `fix(security): add CSRF token to pedido_publico.html upload form`

### P3b — Deduplicate `parse_money_gs` vs `parse_gs`

**Bug**: `app/rms/validation.py::parse_money_gs` and `app/rms/money.py::parse_gs` are duplicate logic (per IMPROVEMENT_BACKLOG #18).

**Fix** (15 min):
1. Read both functions, identify the canonical one (the one used more often)
2. Replace all callers of the other with the canonical
3. Delete the unused one
4. Add a test that exercises both edge cases (negative, zero, decimal string)
5. Commit on main

### P3c — Proactive alert route from `/healthz/errors`

**Gap**: `/healthz/errors` returns counts but no operator gets pinged. the operator only finds out something broke by checking.

**Fix** (30 min):
1. Add a `last_alert_at` and `last_alert_severity` field to a small new `app_health_alert` table (one row)
2. Cron job (use aiw-org's cron catalog) checks `/healthz/errors` every 5 min, writes an alert if the count increased and is > threshold
3. Alert destination: existing notification path (email/Discord/etc. — pick what already works in the aiw-org)

**Decision needed**: do you want this in the sazon-app repo (it crosses into ops concerns) or in aiw-org's monitor catalog?

### Acceptance criteria

- [ ] `test_p0_confirm_modal_csrf` passes (1 fix, 0 regressions)
- [ ] `parse_money_gs` / `parse_gs` deduplicated; no duplicate behavior; test covers both
- [ ] `/healthz/errors` alert route exists (or decision documented why deferred)

---

## P4 — Prevent recurrence

The root cause of the P0 problem is structural: a session can commit work and say "shipped & live" without the deploy actually happening. The plan needs to remove that option.

### P4a — Pre-commit deploy reminder hook

Add `scripts/check_after_commit.py` as a `post-commit` hook that, when files in `app/rms/` or `app/templates/` change, prints:

```
⚠️  COMMITTED TO APP/ — REMINDER: deploy with
   DOCKER_BUILDKIT=0 docker build --no-cache -t sazon-rms:prod -f Dockerfile . && \
   docker service update --image sazon-rms:prod sazon-vps_web --force
   Confirm you have done this before claiming "shipped & live".
```

Wire it in `.git/hooks/post-commit` (or document it in AGENTS.md as a manual habit).

### P4b — `.gitignore` for ephemeral artifacts

Add to `.gitignore`:
```
# Test/dev artifacts
app/static/uploads/2026*.png
debug_*.py
test_import*.py
test_main_simulation*.py
test_router*.py
.scratch/
*.pyc
__pycache__/
.pytest_cache/
.venv/
htmlcov/
.coverage
```

The 14 PNGs are screenshots from today's sessions — they're ephemeral, not source.

### P4c — Worktree policy document

Create `docs/operations/worktree-policy.md`:

```markdown
# Worktree Policy — sazon-app

Two worktrees exist for the same repo. Each has a designated role.

| Worktree | Path | Role | Deploys? | Push policy |
|---|---|---|---|---|
| Scratch | `/opt/data/profiles/ivan/scratch/sazon-app-work` | main branch, deploy source | **Yes** | After every commit |
| Production | `/opt/data/work/sazon-app` | Feature dev (`feature/*` branches) | No (PR + merge → main → deploy) | Via PR only |

## Rules

1. **Never edit code in `/opt/data/work/sazon-app` and deploy from scratch in the same session** without first pushing + rebasing. The two trees drift.
2. **Always run `git status --short` before claiming "done"** in chat. Empty status = done. Modified files = open items.
3. **Always deploy after pushing main.** Session 1 (20260921) committed + tested + said "shipped & live" but the deploy step was never executed. Panceta + Pan rallado stayed flagged for 8 hours until discovered.
4. **Always verify live** with `curl https://sazon-vps.paragu-ai.com/healthz` after a deploy. Status 200 + check the page that the change affected.
```

### P4d — Schema version discipline

The live DB has `PRAGMA user_version=0` and no `schema_info` table, but session 1's migration 062 expects `schema_info` to track versions. The auditor code "works" because it reads via SQLAlchemy ORM — but the schema-version logic is broken.

Two options:

**Option A — Add `schema_info` and migrate live DB** (1 hour):
1. Create migration 063 that creates `schema_info` table if missing
2. Insert current schema_version = (latest applied migration)
3. Update migration runner to use `schema_info` as the source of truth

**Option B — Use `PRAGMA user_version`** (30 min):
1. Every migration bumps `PRAGMA user_version`
2. Migration runner reads `PRAGMA user_version` instead of `schema_info`

Recommendation: **Option B**. It's simpler, matches SQLite's native idiom, and the migrations are forward-only anyway. The `app_meta` table exists in the live DB but seems to be a different mechanism.

### P4e — Logging audit follow-through

The `LOGGING_ERRORS_AUDIT_2026-09-29.md` documented 7 broken things and 7 gaps. Phase 8 shipped P0 fixes (`d5b34f9` + `6bb21c7`). What's left:

| Item | Status | Action |
|---|---|---|
| `#41` user_id=None | ✅ Done (d5b34f9) | — |
| `#42` search.py silent except | ✅ Done | — |
| `#43` auth_supabase.py bare except | ✅ Done | — |
| `#44` Sentry request_id tag | ✅ Done | — |
| `#45` messages.py adoption (12 routers) | ❌ TODO | Pick the top 3 most-duplicated strings and migrate them to `messages.py`. 1h. |
| `#46` "log + decide" canonical pattern | ❌ TODO | Document in `docs/operations/logging.md`. 30 min. |
| `#47` Inline-error UX component | ❌ TODO | Add `<ui-inline-error>` component. 2h. |
| `#48` `errors.html` 4xx template | Partially done | Check what's committed in `6bb21c7`. 30 min. |
| `#49` Sentry request_id + daily rotate | ❌ TODO | Add `logging.handlers.TimedRotatingFileHandler` to loguru. 30 min. |
| `#50` `/healthz/errors` proactive alert | See P3c | — |

The `4xx.html` template status needs verifying — `6bb21c7` is mentioned in `LOGGING_STATUS_2026-09-29.md` as "template landed but errors.py + main.py + tests were staged but not committed." Worth checking the staging area.

### Acceptance criteria

- [ ] `scripts/check_after_commit.py` exists and is wired in `.git/hooks/post-commit`
- [ ] `.gitignore` covers the 14 PNGs + the 4 debug scratch files
- [ ] `docs/operations/worktree-policy.md` exists and is referenced in AGENTS.md
- [ ] Schema version discipline decided + applied (Option A or B)
- [ ] `messages.py` adopted in at least 3 more routers
- [ ] `logging.md` canonical pattern doc exists

---

## Cross-cutting considerations & improvements

These came out of the analysis but aren't strictly required by the 4 sessions. Treat as future work.

### Architecture

- **Two-worktree pattern is fragile.** Consider: a single canonical worktree at `/opt/data/work/sazon-app`, with the scratch path becoming a symlink. The deploy script doesn't need its own path.
- **Schema-version tracking is broken.** Pick PRAGMA user_version OR schema_info and stick with it.
- **`<ui-combo>` has had 3 attribute changes** (endpoint → data-source alias, row-label param, src JSON). Consider freezing the API and version-stamping it.
- **`messages.py` is imported by 1/13 routers** — biggest consistency win is to finish the migration. Even 5 more routers would catch a class of typos.
- **`app/routers/insights.py` (new, untracked)** — verify it doesn't shadow `app/rms/insights.py`. The naming overlap is confusing.

### Operations

- **Deploy should be triggered automatically on push to main.** Use aiw-org's `aiw-cloudflare-deployment` pattern: GitHub Action runs on push, builds the Docker image, pushes to the VPS, runs the swarm update. Removes the "did I deploy?" question entirely.
- **Health checks should be richer.** Current `/healthz` returns 200 always; add `/healthz/db`, `/healthz/schema`, `/healthz/errors`. The middleware already exists; just expose them.
- **The audit log coverage test (`test_p0_audit_log_coverage.py`)** should run in CI on every PR. The 26 tests covering 16 destructive actions are exactly the regression net you need.
- **Long-running delegated work** (B7 subagent ran 670+ sec) needs progress signals. Use `delegate_task(heartbeat=120)` for jobs expected to take >2 min so the parent gets progress without polling.

### Testing

- **121 tests pass on scratch.** Production worktree's interrupted pytest never finished. Re-run it.
- **`test_performance.py` and `tests/browser/` are skipped** in the long runs. Investigate why and either fix or remove.
- **Coverage gate 80%** — verify it still passes after P2 commits. The new B7 + C4/C5 tests should raise coverage.
- **`tests/test_p1_route_coverage.py`** exists and covers 18 routers without dedicated test files. Run it.

### User-facing

- **/ventas/qa** requires cashier login. the operator might want it at `/qa` (no auth) for operator use, or with a separate `ops` role. Decide with the operator.
- **Audit page** still shows Panceta/Pan rallado even though auto-repair would clean them. Either:
  - **Hide rows that auto-repair would fix** (cleaner, hides problems)
  - **Show a "will fix on next audit rerun" pill** (transparent)
  - **Run auto-repair on every page load** (no UI action needed)
  The third is simplest and matches user expectation.
- **`feature/ui-master-menu`** has Spanish fix commits mixed with combo-attribute changes. Squash before merge.
- **The 14 PNG screenshots in `app/static/uploads/`** are today's test artifacts. They should be in `.scratch/` not in the repo's static assets.

### Data integrity

- **PRAGMA user_version=0 in live DB** is suspicious. If migrations have been running, user_version should match the count. This needs investigation.
- **The schema_version mechanism is split**: `app_meta` table exists, `schema_info` doesn't, `PRAGMA user_version=0`. Consolidate.
- **`Sale.tz` recorded but never queried** (IMPROVEMENT_BACKLOG #27) — easy win, useful for analytics.
- **Loyalty points dead** (IMPROVEMENT_BACKLOG #14) — operator chose "manual notes" tier per prelaunch roadmap, but the field is still in the schema. Either use it or drop it.

---

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Deploy breaks live | Medium | High | Verify image contents before `service update`; rollback uses last 3 images |
| Migration 062 fails on live DB | Low | High | Test on staging-equivalent first; have migration script in `db.py` be idempotent |
| Worktree rebase conflicts | Medium | Medium | The two trees' uncommitted work is in different files; rebase should be trivial. If conflict, resolve on smallest hunk |
| Production tree has tests that fail | Medium | Medium | Run pytest BEFORE merging the PR; CI catches it |
| B7 subagent work is broken | Medium | Low | The visual smoke-test step in P2a is the gate |
| Push breaks CI | Low | Medium | Squash merge keeps main linear; revert via `git revert` |

---

## Definition of done

All of these are true:

- [ ] Live `/inventario/auditoria-etiquetas` shows 0 ingredientes con problemas
- [ ] Live DB: Panceta #62, Pan rallado #66, Café #39, Jengibre #70 all match expected clean state
- [ ] `/ventas/qa` returns 200/401 (not 404)
- [ ] Both worktrees' `git status` is empty (except gitignored)
- [ ] `origin/main` is up to date with both worktrees
- [ ] `origin/feature/ui-master-menu` PR is merged or closed
- [ ] `pedido_publico.html` has a CSRF token; `test_p0_confirm_modal_csrf` passes
- [ ] `parse_money_gs` / `parse_gs` deduplicated
- [ ] `docs/operations/worktree-policy.md` exists and references in AGENTS.md
- [ ] `.gitignore` covers the 14 PNGs + the 4 debug files
- [ ] Memory updated with deploy-after-commit reminder

---

## Execution order — for Monday

If you want to execute this in one focused session, here's the order:

1. **15 min** — P0: rebuild + deploy + verify + push
2. **15 min** — P1: rebase feature branch + run pytest
3. **45 min** — P2: commit scratch uncommitted work, commit production uncommitted work (3 batches), open PR
4. **15 min** — P3: fix pedido_publico.html CSRF (5 min), deduplicate parse functions (10 min)
5. **30 min** — P4: write `.gitignore` rules + worktree-policy.md + post-commit hook (15 min), schema version decision (15 min)
6. **15 min** — merge PR, deploy, verify live

Total: ~2.5 hours. Spread across 2 evenings if you want review checkpoints after P0 and P2.

**Start now?** Tell me which pass to begin with. My default is **P0 → P1 → P2 → P3 → P4** in that order. If you want a different order, say which pass and I'll adjust.
