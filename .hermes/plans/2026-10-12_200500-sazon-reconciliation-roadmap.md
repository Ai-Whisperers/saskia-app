# Sazón RMS — Reconciliation & Roadmap Plan (2026-10-12)

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task. Read Phases in order; do not skip Phase 0/1 sequencing.

**Goal:** Reconcile the 3 open PRs + stranded local branch, restore main's broken CI, redeploy prod with everything, salvage the 2 pieces of genuinely-lost work from closed PRs, and sequence the remaining SASKIA roadmap.

**Architecture:** Single-developer multi-agent repo (Ai-Whisperers/saskia-app). Docker Swarm prod at saskia-vps.paragu-ai.com, test at saskia-test.paragu-ai.com (live, /healthz 200), dev at saskia-dev.paragu-ai.com (**currently 404 — broken**). Schema v121 on prod = main. 106 settings. 402 seasonal events seeded.

---

## Findings (verified this session, with evidence)

### F1 — CRITICAL: ci.yml on main has invalid YAML since PR #112
- `git show origin/main:.github/workflows/ci.yml` + `yaml.safe_load` → **FAILS** at line 354: unquoted `: ` in step name `Docs link check (strict: 0 broken relative refs)`.
- Consequence: every push to main fails ci.yml with "workflow file issue" (0s) → **the full pytest suite has silently not run on main since #112**. This is the 0s failure we saw on every branch push today.
- PR #156 fixes exactly this (quoted step name, `yaml.safe_load` passes) + turns the 3 RED abstraction-gate tests green (they were invisible-red since #153).

### F2 — Three open PRs, three different states
| PR | Title | State | Notes |
|---|---|---|---|
| #156 | SASKIA-211a: abstraction gates green + ci.yml YAML fix | MERGEABLE/UNSTABLE (test job pending at last check) | **Highest value.** Fixes F1. 38 files. |
| #158 | SASKIA-220: URL-based tenant routing (opt-in middleware) | MERGEABLE/BLOCKED (checks pending) | 6 files: `app/rms/tenant.py`, `main.py`, `tenants/example.yaml`. Opt-in (no behavior change until a tenants/ file exists). Depends on nothing. |
| #155 | docs(agents): drift-fix pass | **CONFLICTING** | 100 files, docs-heavy. Conflicts with #157 (my CHANGELOG/nav edits). Needs rebase. |

### F3 — Stranded local branch `sibling-main-20261012`
- 23 local-only commits: local merge commits of #155 + #156 + #157 + #158 (tip 51058375) that were never pushed (non-fast-forward vs origin/main because origin got squash-merges instead).
- Content = the 3 open PRs; nothing unique is at risk, but the branch must not be force-pushed. Delete only after all 3 PRs merge.

### F4 — Closed-unmerged PRs: salvage audit (from previous analysis)
- 8 of 10 fully superseded (content verifiably in main). **Do not merge any as-is.**
- Genuinely missing, worth salvaging:
  1. **#151** → `tests/concurrency/test_concurrency_deep.py` (152 lines: concurrent `init_db` safety, session contention). Never landed; main's `tests/concurrency/` has only `test_concurrent_writes.py`.
  2. **#149** → curated subset of 52 test files: keep route-level tests (`test_customers_routes.py`, `test_cotizador_routes.py`, `test_analisis_routes.py`, `test_copiloto_routes.py`); **discard** the auto-coverage machines (`test_auto_coverage*.py`, `test_*_modules_coverage.py`, `.cache-scripts/` scratch). Coverage goal already met (43% > 41% target); take only tests that still pass on current main.
  - **#101** complexity refactors: deliberately rejected (would break ANN gate). Only revisit if `make cognitive` flags those functions again — re-author with type hints, per the close rationale.

### F5 — Shipped but not verified visually
- SASKIA-217 `/api/admin/seasonal-calendar` is live on prod (401 auth wall = healthy) but **nobody has eyeballed the rendered page**. Test env (saskia-test) auto-deploys PRs → after Phase 0 merges, use it for browser verification with operator creds from BWS (`SASKIA_TEST_USER`/`SASKIA_TEST_USER_PASSWORD`).

### F6 — Environment drift
- `saskia-dev.paragu-ai.com` → **404** (no Traefik router / stack gone). Test is fine. Either restore dev env or remove it from docs/deploy scripts (decision needed from operator — low priority).

### F7 — Remaining SASKIA roadmap (docs on main, post-217/220)
- **SASKIA-222** — per-tenant settings: country + pack + relevance_tags per tenant (4-6h). Natural next step after #158's tenant middleware merges; they complete each other (222 = data, 158 = routing).
- **SASKIA-219** — `scripts/refresh_seasonal_events.py` annual roll-forward cron (1d). Prevents the catalog going stale in 2029 (last baked year 2028).
- **SASKIA-218** — `TenantSeasonalEventOverride` per-tenant visibility/impact overrides (1d). Only after 222.
- **SASKIA-217b (gap)** — the calendar page is not in any dashboard widget; the seasonal.py `upcoming_calendar_json` dashboard hook still reads the OLD workflow dataclass, not the new table. Small wiring task (~2h).

---

## Phase 0 — Merge queue reconciliation (blocks everything)

Order matters: #156 first (CI integrity), then #158 (independent), then #155 (needs rebase against the other two).

### Task 0.1: Merge #156 (ci.yml fix + abstraction gates)
1. `gh pr checks 156` — wait for all green (it was pending; the branch's Dev CI already passed).
2. If any check red: read logs, fix on branch `SASKIA-211a-utcnow-and-apply-sale-imports`, push, re-wait.
3. `gh pr merge 156 --squash --delete-branch=false`
4. **Verify within 5 min:** a new ci.yml run starts on main for the merge commit and it is NOT a 0s "workflow file issue" — `gh run list --branch main --limit 3`. This proves F1 is fixed.

### Task 0.2: Merge #158 (tenant routing middleware)
1. Wait for checks; merge squash.
2. Verify: `curl -s https://saskia-vps.paragu-ai.com/healthz` still 200 after next deploy (middleware is opt-in; no tenants/ file exists → zero behavior change).

### Task 0.3: Rebase + merge #155 (docs drift-fix)
1. `gh pr view 155` → conflicts vs main (my #157 + 0.1/0.2 changes).
2. On a fresh worktree: `git fetch origin pr/155/head && git rebase origin/main` → resolve conflicts in AGENTS.md / CHANGELOG.md / WHAT_NEXT.md (prefer the incoming drift-fixed numbers, re-verify each numeric claim against the post-merge repo — that's the PR's whole point).
3. Force-push the branch, wait green, squash-merge.
4. Delete `sibling-main-20261012` (`git branch -D`) — all its content is now merged via squash PRs.

### Task 0.4: Post-merge full-suite run on main (proves the CI fix end-to-end)
1. Trigger: push any trivial docs commit, or `gh workflow run ci.yml` if it has workflow_dispatch.
2. Expect: full pytest (7,900+ tests) actually executes on main for the first time since #112.
3. **If tests fail on main** (they were invisible for days): triage each failure — they are pre-existing, not regressions from today. Fix forward on a branch; do NOT merge anything else until main's suite is green.

---

## Phase 1 — Prod redeploy with reconciled main + visual verification

### Task 1.1: Deploy
1. `git fetch && git checkout main && git pull` in the deploy worktree.
2. Pre-flight: live schema check (`docker exec ... app_meta schema_version`) — expect 121, code 121, no sibling race.
3. `bash scripts/deploy.sh --env=prod`
4. Verification ladder (skill: saskia-rms-deploy-flow): fresh task, healthz 200, `/api/admin/seasonal-calendar` 401, container log scan, schema still 121.

### Task 1.2: Browser-verify the seasonal calendar (closes F5)
1. Test env auto-deployed the merges — `https://saskia-test.paragu-ai.com`.
2. Fetch test creds from BWS (`SASKIA_TEST_USER` / `SASKIA_TEST_USER_PASSWORD`) via the BWS SDK (never print).
3. `browser_exec`: login → navigate Sistema → Calendario estacional → screenshot.
4. Check: table renders with real events (Navidad 25/12, San Juan Ára), lead-window callout, impact badges, dark theme contrast (empty-state recipe from deploy skill: `--color-info-soft` + border-left).
5. Any visual defect → small fix PR (template-only, fast lane).

### Task 1.3: Wire the dashboard widget to the new table (SASKIA-217b, ~2h)
1. `app/rms/seasonal.py::upcoming_calendar_json` currently reads `workflow.SEASONAL_CALENDAR_2026` — switch to `get_calendar_events()` (the DB table) with fallback to the static calendar when the table is empty.
2. TDD: extend `tests/test_saskia217_seasonal_calendar.py` — seed table, assert widget returns DB events; empty table → static fallback.
3. PR → merge → include in next deploy.

---

## Phase 2 — Salvage pass from closed PRs (~1 day total)

### Task 2.1: Rescue #151's concurrency test (30 min)
1. `git show pr-151:tests/concurrency/test_concurrency_deep.py > tests/concurrency/test_concurrency_deep.py` (branch `salvage/concurrency-deep`).
2. Run it: `pytest tests/concurrency/test_concurrency_deep.py -v`. It was authored pre-121; fix any API drift (e.g. `make_engine(f"sqlite:///{db_path}")` signature).
3. Green → CHANGELOG entry → PR → merge. Reference #151 in the PR body.

### Task 2.2: Curated rescue from #149 (2-4h)
1. Branch `salvage/route-tests`. For each of `test_customers_routes.py`, `test_cotizador_routes.py`, `test_analisis_routes.py`, `test_copiloto_routes.py`, `test_backup_live_db.py`:
   - Extract from pr-149, run against current main.
   - Keep only files that pass as-is or with <30 min of deconflicting; drop the rest with a note in the PR body.
2. Explicitly DO NOT take: `test_auto_coverage*.py`, `test_*_modules_coverage.py`, `.cache-scripts/*`, anything touching `PATCH_*_COLS` (that API changed after #120/#122).
3. One PR, CHANGELOG entry, reference #149.

---

## Phase 3 — Remaining roadmap (post-reconciliation)

### Task 3.1: SASKIA-222 — per-tenant settings (4-6h, after #158)
- Add `tenant.country`, `tenant.pack_slug`, `tenant.relevance_tags` read path; `operator_relevance_tags()` in seasonal.py reads from tenant context when set, falls back to the settings registry (current behavior).
- TDD against `tests/test_saskia217_seasonal_calendar.py` extension: tenant with `pack_slug=heladeria` sees heladería events.

### Task 3.2: SASKIA-219 — annual roll-forward cron (1d)
- `scripts/refresh_seasonal_events.py`: for year N+1, extend fixed-date events (mechanical), re-compute Easter-anchored events, flag movable-by-decree events for operator review (they change by decree).
- Test with frozen clock fixtures (existing `test_date_boundary.py` pattern). Schedule via VPS cron after deploy — NOT Hermes cron (deliver must target a real channel; and it's a VPS-local job).

### Task 3.3: SASKIA-218 — per-tenant overrides (1d, after 222)
- `TenantSeasonalEventOverride` table (migration 122): per-tenant impact_score multiplier, hide/show, custom lead days.
- Only build what La Vaquita needs now: hide/show + lead override.

### Task 3.4 (operator decision): saskia-dev environment
- 404 today. Options: (a) restore the stack (one `deploy.sh --env=dev`), (b) retire it from envs.yaml + docs. Ask Ivan — 5-min decision, low stakes.

---

## Explicitly NOT doing (with reasons)
- **Merging any closed-unmerged PR as-is** — stale bases would regress #117's ANN gate, re-add stale WHAT_NEXT, conflict with PATCH_*_COLS.
- **#101 complexity refactors** — deliberately rejected; re-author only if `make cognitive` flags those functions.
- **SASKIA-224 multi-tenant big-bang** — superseded by #158's opt-in middleware + 222's incremental settings. Do not open a new epic.
- **Force-pushing sibling-main-20261012** — squash-merge the PRs instead; the local branch is deleted in Task 0.3.

## Risks / open questions
1. **Main's full suite may be red** once ci.yml is fixed (Task 0.4) — days of unverified merges. Budget a half-day of triage; failures are pre-existing by definition.
2. **#155's 100-file rebase** may surface more conflicts than expected; if >1h of conflict resolution, consider asking the sibling session (author) to do it — it has the context.
3. **Tenant routing (#158) + 222 interplay** — 158 routes by URL, 222 stores per-tenant prefs; confirm the middleware reads the same settings keys 222 writes before building 222 (read `app/rms/tenant.py` first).

## Verification checklist (definition of done for this plan)
- [ ] ci.yml runs the full suite on main and is green
- [ ] PRs 155/156/158 merged; `git status` clean; sibling-main branch deleted
- [ ] prod on reconciled main; healthz 200; schema 121
- [ ] seasonal calendar screenshot-reviewed on test env
- [ ] concurrency-deep + curated route tests merged (or documented as dropped)
- [ ] SASKIA-222 shipped or explicitly deferred by Ivan
