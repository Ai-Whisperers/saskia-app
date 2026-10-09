# Branch protection for `main` — operator checklist

**Last updated:** 2026-10-09 (ruleset live; UI flow below for when the
"branch protection has been disabled on this repository" error needs
to be resolved).
**Owner:** Ivan (operator)
**Goal:** end the fix-by-pushing-to-main loop by making 5 of the
always-green workflows **required** before any PR can merge.

## Status: ACTIVE (ruleset 24802688)

Branch protection for `main` is enforced via a **ruleset** (the
modern GH API; the classic `PUT /branches/main/protection` returns
404 for this repo — branch protection is **disabled at the legacy
endpoint** but rulesets work). The ruleset was created on 2026-10-09
and is live. Do not remove it.

Verify:
```bash
gh api repos/Ai-Whisperers/saskia-app/rulesets/24802688 \
  -q '{name, enforcement, rules: .rules[].type}'
```

## Why now

The 2026-10-09 CI recovery (PR #88) moved 5 of 11 GH Actions workflows
from 0% pass rate to green-on-every-push. Until branch protection
enforces the green ones, the "push to main" loop continues.

## What the ruleset enforces

| Rule | Value | Effect |
|---|---|---|
| `deletion` | active | Cannot delete `main` |
| `non_fast_forward` | active | No force-push |
| `required_linear_history` | active | No merge commits |
| `pull_request` | 0 required reviews, dismiss stale, resolve threads | PR must exist to merge to `main` |
| `required_status_checks` | 5 checks (below), strict | All 5 must be green |

### Required status checks (5)

These are the workflows that have been green for 7+ days and that
are the minimum bar for "this change didn't break anything obvious":

- ✅ **smoke** (job in `smoke.yml`) — runs `scripts/smoke_test_deploy_shape.py` against ephemeral Postgres. Catches migration drift. ~40s.
- ✅ **route-smoke** (job in `route-smoke.yml`) — 47 generated + 119 explicit route tests. ~2 min.
- ✅ **currency-drift** (job in `currency-drift.yml`) — D3 custom checks; money/decimal drift. ~8s.
- ✅ **browser** (job in `browser.yml`) — 9 Playwright tests. ~2 min. Daily cron also runs it.
- ✅ **Static analysis (lightweight)** (job in `ci.yml`) — ruff + check_imports. ~32s.

### NOT required (intentionally)

These are still being stabilized. Marking them required will block
every PR until they're 100% reliable:

- ⏸ **test** (job in `ci.yml`) — was failing on main at 2026-10-09
  due to a sibling-session lint issue. Now the dev-ci gate catches
  it on PR, so it's not required at merge time.
- ⏸ **deploy-test** — was failing on main at 2026-10-09 because
  the workflow references `VPS_KEY` (a name we don't have; only
  `SASKIA_VPS_SSH_KEY`). The deploy still succeeds when manually
  triggered via `workflow_dispatch`; required-on-merge would block
  every PR.
- ⏸ **deploy-dev** — runs on non-main branch pushes only. Cannot
  be required on main (the check never runs).
- ⏸ **dev-ci (gate before deploy-dev)** — currently the de-facto
  blocker for landing broken code, but its name doesn't appear in
  branch protection's required checks list (it's a push-to-non-main
  workflow).
- ⏸ **OWASP ZAP API scan** — the `-l HIGH` → `-l FAIL` fix is in
  commit `1d2c42a3`. Let it cycle 1 weekly run before promoting.
- ⏸ **AIW QA Gates (department)** — pinned to SHA in `1d2c42a3`;
  let it cycle 1 weekly run before promoting.

## Why a ruleset, not classic branch protection

GH's classic `PUT /branches/main/protection` returns **404** for
this repo with the message "Branch protection has been disabled
on this repository." This is a **repo-level admin setting** that
cannot be flipped by the ruleset API; it has to be done in the
GH UI at `https://github.com/Ai-Whisperers/saskia-app/settings/branches`
under "Allow branch protection rules" (or whatever the current
label is). The ruleset is the modern replacement and it does the
same thing.

If the classic branch protection is re-enabled later, the
recommended approach is to **delete the ruleset** and re-create
the same rules as classic branch protection. The two don't
stack; the ruleset will take precedence.

## After the ruleset is live (already done)

Open a test PR to verify the ruleset works. The PR should:
- Show 5 "Required" status checks below the merge button
- Block "Merge pull request" until all 5 are green

If the check-runs that exist on the latest main commit don't
match the 5 names above, the ruleset's `strict` mode will fail
with a message like "Required status check ... was not set by
any commit". Verify the names by:
```bash
gh api repos/Ai-Whisperers/saskia-app/commits/main/check-runs \
  -q '.check_runs[].name'
```

## What to require on the other branches

| Branch | Rule | Why |
|---|---|---|
| `main` | All 5 above | Production. Sacred. |
| `infra/*`, `chore/*`, `docs/*` | All 5 above | Also merges to main; same bar. |
| `feat/*` | None | Work-in-progress. |
| `refactor/*` | All 5 above | Sibling refactor session lands here; needs to pass before merging. |
| `fix/*` | All 5 above | Same. |

## What the operator should NOT do

- ❌ Don't add "require review" without a reviewer team set up. The
  repo has 1 developer. Setting "require 1 reviewer" + "no reviewers
  available" = every PR is unmergeable. (The ruleset has 0 required
  reviews, which is the right default for 1-dev repos.)
- ❌ Don't enable "auto-merge" without the merge queue. Auto-merge
  + missing required checks = CI gets spammed.
- ❌ Don't add bypass actors. The ruleset's `current_user_can_bypass
  = "never"` is intentional.

## The 5 protected checks — what each one catches

| Check | Catches | Misses |
|---|---|---|
| currency-drift | `float` used for money; `int(Decimal(...))` instead of `to_int_gs()`; Gs vs ₲ spelling; bare `Gs` instead of `Gs. 729.167` | Real-world money bugs (e.g., wrong rounding edge case) |
| smoke | Migration drift (PG ↔ SQLite); missing alembic-style forward-only migration; env var shape change | E2E flow bugs; UI breakage |
| route-smoke | Any route returns 500 on basic GET/POST; CSRF regression; auth bypass | Subtle business-logic bugs that return 200 with wrong data |
| browser | Login flow broken; navigation dead-ends; form submission 500s | Cross-browser; slow-path bugs |
| Static analysis (lightweight) | Ruff lint + import-order violations; W293 trailing whitespace; undefined names | Type errors (mypy is advisory only) |

## References

- `docs/operations/2026-10-09-three-env-deploy.md` §"Auto-deploy (CI)"
- `docs/operations/2026-10-09-ci-recovery.md`
- `docs/operations/dora-2026-Q4.md` (the metrics the gate will improve)
- `docs/ci/toolchain-versions.md`
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets
