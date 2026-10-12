# 2026-10-10 Session Handoff — Sprint 2.1 closeout + WHAT_NEXT refresh

> Comprehensive end-of-session report. Covers everything shipped, touched, found, and 
> deferred in the 2026-10-10 ~18:00 → 19:45 UTC session window. Read this if you need to
> pick up where this session left off, or to audit what happened.
> 
> Companion: `WHAT_NEXT.md` (operator punchlist, post-this-session).

## TL;DR

Sprint 2.1 closed. **v2026.10.1 released** (commit `e54c4571`). 6 PRs shipped in this 
window. CI test wall-time dropped **12 min → 1.5 min** (the #126 conftest fix is the big 
win). Main is at `6a9d80a1` (this PR's commit after merge). 1 open PR from sibling (#135). 
0 open issues.

## What we shipped (6 PRs, all merged)

| # | PR | Commit | What it fixes | Lines |
|---|---|---|---|---|
| 1 | #125 | `f873651b` | void/dashboard/export: 5× `recorded_at`→`sold_at` rename, drop 7 duplicate `_write_*_sheet` (−142 lines), remove legacy "US 4.1 — restore packaging" block | +58 / −170 |
| 2 | #122 | `5e78e6a1` | PATCH plantilla: stop writing ` [REQUIRED]` / ` [OPTIONAL]` markers in headers; import side already had no stripper | +103 / −5 |
| 3 | #127 | `3b1cf90f` | WHAT_NEXT refresh after #123 + #125 | +249 / 0 |
| 4 | #129 | `9f9cead4` | deploy healthz: replace brittle `case` glob with `grep -q` | +94 / 0 |
| 5 | #126 | `e54c4571` | conftest: stub autouse chain for pure-Python tests via `request.fixturenames` | +139 / −121 |
| 6 | #132 | `6a9d80a1` | WHAT_NEXT refresh after #126 + #129 + #127 + #125 + #122; dedup #126 CHANGELOG entry that survived two rebase rounds | +243 / −61 |

### What each fix actually does

**#125 — the cleanup PR.** Combined three independent pre-existing failures that were all
on the same branch (PR #120's lineage). The dashboard.py rename was a `Sale.recorded_at`
typo (the column is `sold_at` post-#118). The export_xlsx.py deletion removed 142 lines of
duplicate `_write_*_sheet` functions — the original ones (lines 484-576 in the old file)
were exact duplicates of the canonical ones earlier in the file. The lifecycle.py packaging
block was a "US 4.1 — restore packaging" stub left over from a 2026-09 refactor; the
property assignment `stock_status = p.product.stock_status` was the actual fix.

**#122 — the import-export roundtrip fix.** When you PATCH-import a plantilla back, the
import side reads row.get("name") but the export side wrote "name [REQUIRED]" as the
header. So every row raised `KeyError: 'name'`. Fix: write clean column names in the
export; the template-render helper still annotates required/optional visually for the
operator (yellow background / red border on the form). 19/19 test_excel_patch tests pass.

**#126 — the CI wall-time fix.** This is the big one. The 7,997-test suite was timing out
at 12 minutes on every PR. Root cause: every single test paid ~7s for `from app.rms.main 
import app` (autouse `reset_app_state`) and ~8s for `init_db()` (autouse chain
`_close_leaked_sessions → session_factory → app_engine`) — even tests like
`test_daily_summary_dryrun` that shell out to a subprocess and never touch the DB.

The fix is `_fixture_tree_needs_app(request)`: it checks `request.fixturenames` against
the set of app-touching fixture names. The autouse chain short-circuits to a stub when
no app-touching fixture is in the test's tree. The v1 implementation used `sys.modules`
(incorrect — `session_factory` is built before `client` is instantiated, so the stub
was incorrectly used when `client` was actually requested, breaking 2 test files with
`RuntimeError: session_factory stubbed; requested attr 'kw'`). v2 uses
`request.fixturenames` (the correct signal: the test's full fixture tree is known before
any fixture body runs).

Result: pure-Python / CLI tests pay ~0s setup. App-touching tests behave unchanged.
CI wall-time: 12 min → 1.5 min. The 4-phase coverage push in `docs/plans/2026-08-31-rms-fase-1-dev-plan.md`
is now feasible.

**#129 — the deploy healthz grep fix.** `deploy.sh` was using a bash `case` glob to
parse the healthz response, and the case statement had drifted from what `/healthz` actually
returns. Replaced with `grep -q`. The transient `bws secret list 429` failures (seen on
#129's deploy-test) are NOT caused by this PR — they're a BWS API rate-limit hit when
deploy-dev and deploy-test run in parallel.

**#127, #132 — WHAT_NEXT cadence.** Two refreshes in one window because 5 PRs landed
between them. The first (#127) was after the cierre + pre-existing-failures merge; the
second (#132) was after the 5-PR blast that included the CI hang fix and the deploy 
healthz fix. Also deduped a #126 CHANGELOG entry that survived two rebase rounds (the
sibling's commit `2e4e987e` "fix(changelog): remove duplicate entry after rebase" was the
right intent; #132 finished the job).

### What we closed as superseded (3 PRs)

- **#120** (my own first attempt) — closed when #125 was the cleaner combined fix on 
  current main. The #120 branch is still in git for audit (`fix/pre-existing-test-failures-2026-10-10`).
- **#124, #128** — sibling re-authored these as #129 (and again as #135 for the release.sh
  array-args variant). The re-authoring pattern is correct: closed in favor of a clean
  rebase rather than force-push over an open conversation.

### Sibling PRs that landed in this window (not mine, but relevant)

- **#131** (`68d3a0f4`): release workflow `git checkout main` before deploy.sh. Caught 
  the v2026.10.1 release deploy failing on the detached-HEAD check.
- **#133**: per-invocation `REMOTE_DIR` + atomic staging to `final mv`. Addresses the 
  deploy race that #129 surfaced.

### Currently open

- **#135**: rebased #134 (release.sh args via bash array). MERGEABLE. Sibling owns. 

## What we looked at but did NOT do (the "remaining" list)

These are the items the user asked me to inventory. Each one has a clear owner and a
trigger condition. None of them are blocking.

### Operator tasks (deferred to Iván)

1. **VPS secrets rotation** (~30 min). `deploy-dev` / `deploy-test` need a working
   `BWS_ACCESS_TOKEN` + VPS SSH key. Until then, deploys land via VPS-side pulls (you do
   this manually). Once BWS is populated, both deploys should light up green and the 
   bws 429 race becomes moot (because the GitHub App rotation path takes over).
   - Trigger: when you have 30 minutes.
   - Risk: low. Pure ops task.

2. **Coverage gap analysis** (2-3h, Sprint 2.2 scope). Actual: 26.12%. Gate: 35%.
   CI does NOT enforce the gate (uses `--cov=app` without `--cov-fail-under`); the 
   gate is only in `pyproject.toml` addopts for local dev. Biggest gaps:
   - `app/services/template_render.py` (21% — entire module uncovered)
   - `app/services/import_xlsx.py` (mostly uncovered)
   - `app/rms/reports/*` (whole submodule thin)
   - `app/rms/production/*` (whole submodule thin)
   - Trigger: when Sprint 2.2 starts ("ship Saskia a usable product").
   - Risk: low. The 4-phase plan in `docs/plans/2026-08-31-rms-fase-1-dev-plan.md` 
     bumps the gate in stages; current 35% is the floor.

3. **Re-tag v2026.10.1 to trigger the now-fixed release deploy** (~5 min). PR #131 fixed
   the release workflow's `git checkout main` step. The v2026.10.1 tag is in git but the
   release deploy was skipped when #131 was open. Re-push the tag (or create v2026.10.2)
   to verify the release path now reaches the VPS.
   - Trigger: when you want to verify the v2026.10.1 actually lands on prod.
   - Risk: medium. This is the production deploy path.

### Backlog (no rush)

4. **SASKIA-210 — Supabase RLS + Storage**. Explicitly DEFERRED per the 2026-10-07
   per-client-instances decision (`docs/plans/SASKIA-210-supabase-rls-multitenant-onepager.md`).
   Do not pick up until Saskia is happy with the current product.
   - Trigger: Saskia signal.
   - Risk: high (multi-tenant data isolation).

5. **`feat/station-shell` (sibling in flight)**. Puesto cards UI. Carries a stale
   `app/CHANGELOG.md` that will conflict on merge — sibling should drop it before 
   merging.
   - Trigger: sibling signals ready.
   - Risk: low. Docs conflict only.

6. **ZAP promotion to high-only**. Currently runs full ZAP. Wants to skip low/medium.
   - Trigger: 2 consecutive clean weekly scans (calendar-bound, not work).
   - Risk: low. Just config.

7. **Ruff `# noqa: arch-rule` warnings (11 informational)**. The lint check itself 
   passes; the warnings are stderr noise. Two ways to silence would both break the 
   test contract in `tests/test_check_imports_rules.py` (which parses the string 
   literally). **Left as-is.**
   - Trigger: never. Documented decision.

### Not in this session's scope

- **PR #101 refactor (48-file complexity refactor)**. Closed. Still valuable, needs
  re-authoring on the post-#117 base with annotations from the start. If anyone wants
  to do this, file a new SASKIA ticket.
- **Tier 3 tools** (Semgrep CE, umbra-scan, prek). Per the WHAT_NEXT explicit-defer
  list.

## Findings (worth recording)

### Finding 1 — CI wall-time is the single biggest win
The #126 conftest fix dropped 7,997-test CI wall-time from 12 min to 1.5 min. That's
8× faster. Implications:
- The daily-boundary workflow (`.github/workflows/date-boundary.yml`, Mondays 03:00 UTC)
  now completes in budget on a 2,000-minute/month plan.
- PRs iterate faster. The PRs I shipped in this session all went green in 1-2 min instead
  of 10-12 min.
- Future coverage expansion (the 4-phase plan) is now feasible — adding 1,000 more tests
  costs ~12s per PR, not ~1.5 min.

### Finding 2 — bws 429 race on parallel deploys
When `deploy-dev` and `deploy-test` run in parallel (different PRs), they both call
`bws secret list` and one of them hits a 429. The fix in #133 (per-invocation REMOTE_DIR +
atomic staging) doesn't address this directly; the right fix is populating
`BWS_ACCESS_TOKEN` so the GitHub App rotation path takes over (one token, one rate-limit
budget, no contention).

### Finding 3 — Coverage gate is unenforced in CI
`pyproject.toml` sets `--cov-fail-under=35` in addopts, but `.github/workflows/ci.yml`
runs `uv run pytest -n 2 --dist=loadscope --cov=app --cov-report=term-missing -m 
"not (pg)"` — no `--cov-fail-under`. So the 35% gate is local-dev-only. Actual coverage
on the full suite is 26.12%. This is intentional (per the "current measured floor"
comment in pyproject) but worth knowing: the gate is a floor indicator, not a CI
enforcement. Sprint 2.2 should decide whether to enforce it.

### Finding 4 — Worktree hijack is real
During this session, both my session-started "canonical" worktrees (`/opt/data/work/saskia-app`
on `ivan/latest` and `/opt/data/work/saskia-app-ci` on `main`) were taken over by sibling
sessions who checked out their feature branches in those worktrees. The worktrees now
sit on sibling branches. I created `/opt/data/work/saskia-app-main` on origin/main
(detached) for my own use.

This isn't a bug — it's the documented `docs/operations/worktree-policy.md` behavior:
"don't share branches between sessions." But it does mean the worktree name
`saskia-app-ci` no longer tracks `main`. If a future session expects that worktree to
be on main, they'll be surprised. **Recommendation:** future sessions should create
their own worktree per session (e.g. `saskia-app-<session-tag>`).

### Finding 5 — Sibling rebases are common; close-and-reopen is the pattern
When a PR can't auto-merge because of a sibling landing on main, the sibling pattern
is: close the original PR and open a new one (often with a "-rebased" suffix). I saw
this with #128 → #129, and #134 → #135. The closed PR stays in git history for audit;
the new PR is the clean rebase. This is the right pattern for parallel sessions.

### Finding 6 — Deduped #126 CHANGELOG entry was a rebase-race casualty
The same #126 changelog entry was committed twice (lines 1 and 18 of CHANGELOG.md)
because two rebase rounds both picked up the same content. The sibling's commit
`2e4e987e` "fix(changelog): remove duplicate entry after rebase" was the right intent
but landed AFTER the second rebase. My #132 finished the dedup. **Lesson:** when
rebase lands the same file twice from different parents, always check
`git log --oneline -- <file>` for duplicate consecutive entries before committing.

## Cross-session context (from memory)

The `holographic memory` block at session start mentioned the **Paraguay CivicTech
fleet** (12 sites on *.paragu-ai.com, 8 live, 4 dead with no DNS). This is a 
**different workstream** from saskia-app. It lives in:
- `/opt/data/raw_datasets/` (502 files, ~570MB)
- `/opt/data/sites_data/` (253-article news DB, 10 conflicts)
- `/opt/data/PARAGUAY-CIVICTECH-RESTORE-KIT/` (deep analysis + 26 drafted reports unpublished)
- `/opt/data/build/monorepo-sparse` — DELETED, source recovery needed from Docker images

The restore priority order is:
1. Source recovery from Docker images (7 of 8 live sites have no source in git)
2. Wire-or-kill the 4 dead sites (economia-abierta, trabajo-empleo, ddhh-paraguay, 
   politica-exterior)
3. Publish datasets (42 reporting findings + 26 drafted reports)
4. Single flagship (lean corrupcion-cero)

This was **not worked on in this session** (the session was 100% saskia-app). It's
flagged here because the memory context put it on the table and it was acknowledged but
not picked up. Treat as a separate sprint.

## Verification on main (this commit)

```bash
# All key tests pass:
$ uv run pytest tests/test_excel_patch.py tests/test_dashboard_enrollment_kpi.py \
    tests/test_SASKIA-302_inicio.py tests/test_void_sale.py --no-cov
======================= 33 passed, 2 warnings in 16.07s ========================

# 5 required CI checks (ruleset #24802688) all green on every PR shipped in this window.
# deploy-dev green on all 6 PRs. deploy-test green on 5/6 (one transient bws 429 on #129).

# /healthz on the live envs:
$ curl -sS -o /dev/null -w '%{http_code}\n' https://saskia-dev.paragu-ai.com/healthz
200
$ curl -sS -o /dev/null -w '%{http_code}\n' https://saskia-test.paragu-ai.com/healthz
200
# sazon-vps.paragu-ai.com unreachable from this host (DNS issue, not code).
```

## Sprint 2.1 release notes (for the tag)

**v2026.10.1 — Sprint 2.1 — released 2026-10-10**

Commits since the prior tag:
- `20c592c6` #118 — fix(void/xlsx): void_sale deletes SalePayment rows + xlsx duplicate function
- `9105ff90` #111 — fix(ci): deploy workflows SSH key libcrypto error
- `e54c4571` #126 — fix(ci): skip conftest app-imports for pure-Python tests

Plus the dependency: #131 (release workflow `git checkout main`) needs to land for the
release deploy to actually work. v2026.10.1 was tagged at `e54c4571` but the release
deploy was skipped because the workflow bug was caught at that exact moment. Re-tag
or push v2026.10.2 once you've verified the release path.

## Artifacts produced this session

- 6 PRs (all in github.com/Ai-Whisperers/saskia-app)
- 2 worktrees created (`/tmp/whatnext` cleaned up; `/opt/data/work/saskia-app-main` kept)
- 6 stale worktrees removed (`/tmp/{whatnext,refresh2,deploy-healthz,baseline-6ffe16d3,wt-base,wt-wp}`,
  `/opt/data/profiles/ivan/cache/scratch/saskia-app-patch-fix`)
- 1 local-tracking branch removed (`docs/what-next-refresh-3-2026-10-10`)
- 1 symlink created+removed (`.venv` shortcut in saskia-app-main, no longer needed)
- This file (`docs/operations/2026-10-10-session-handoff.md`)

## Trigger conditions for the next session

If you (or a future session) come back to this, the entry points are:

1. **"What's the next thing?"** → read `WHAT_NEXT.md` (post-this-session, #1 = VPS secrets)
2. **"What did the last session do?"** → read this file
3. **"Why is the coverage gate unenforced?"** → Finding 3
4. **"Why is the saskia-app-ci worktree on the wrong branch?"** → Finding 4
5. **"Where did the Paraguay CivicTech work go?"** → Cross-session context section
6. **"What about the bws 429 errors?"** → Finding 2 + #135 (in flight)
7. **"What about the test_daily_summary hang?"** → Fixed in #126 (Finding 1)

---

**Generated:** 2026-10-10 ~19:50 UTC after the #132 merge, before the #135 sibling handoff.
**Author:** Hermes session, operator Iván.
**Commit:** this file lands in the next PR after this draft.
