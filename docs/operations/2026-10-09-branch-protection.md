# Branch protection for `main` — operator checklist

**Last updated:** 2026-10-09
**Owner:** Ivan (operator)
**Goal:** end the fix-by-pushing-to-main loop by making 4 of the 11 always-green workflows **required** before any PR can merge.

## Why now

The 2026-10-09 CI recovery (PR #88) moved 5 of 11 GH Actions workflows from 0% pass rate to green-on-every-push. Until branch protection enforces the green ones, the "push to main" loop continues. **This is an operator action** — it requires a single click in the GitHub UI; the rest of this document is the exact checklist.

## What to click

1. Go to https://github.com/Ai-Whisperers/saskia-app/settings/branches
2. Click "Add rule" or edit the existing `main` rule
3. Branch name pattern: `main`
4. Configure:

### Required status checks (4)

These are the workflows that have been green for 7+ days and that are the minimum bar for "this change didn't break anything obvious":

- ✅ **Currency Drift Lint (D3)** — 47 lines of custom D3 checks that detect money/decimal drift in code. Fast (~10s). Catches the most common bug class.
- ✅ **Smoke (deploy-shape)** — runs `scripts/smoke_test_deploy_shape.py` against ephemeral Postgres. Catches migration drift. ~30s.
- ✅ **Browser (Playwright, advisory)** — 9 Playwright tests against a dev server. Catches the "looks fine in dev, broken in browser" class. ~2 min.
- ✅ **Route Smoke (fast gate)** — 47 generated + 119 explicit route tests. Catches "endpoint returns 500" before deploy. ~2 min.

### DO NOT require yet (the 5 still-shaky)

These are the workflows that are still being stabilized. Marking them required will block every PR until they're 100% reliable:

- ⏸ **Tooling (static analysis)** — was 0/10, now green. But only 7 days of history; wait for 14.
- ⏸ **Security (OWASP ZAP)** — the `-l HIGH` → `-l FAIL` fix is in commit `1d2c42a3`. Let it cycle 1 weekly run before promoting.
- ⏸ **Deploy test** / **Deploy dev** — the SSH key + .venv fixes are in. But these are the actual deploy jobs; requiring them in branch protection means "every PR that lands breaks the deploy", which is what we want eventually, but not today.
- ⏸ **Dev CI (gate before deploy-dev)** — added 2026-10-09; the lint + fast test gate. Useful but advisory for now.
- ⏸ **AIW QA Gates (department)** — pinned to SHA in `1d2c42a3`; let it cycle 1 weekly run before promoting.

### Other rules to enable

- ✅ **Require linear history** — no merge commits. Cleaner log, easier to bisect.
- ✅ **Include administrators** — even Ivan's `git push origin main` (when bypassing the PR) is blocked. Catches the "oh I just needed to fix one thing" exception that breaks the audit trail.
- ✅ **Allow force pushes** — ❌ NO. Never.
- ✅ **Allow deletions** — ❌ NO. The `main` branch is sacred.
- ⚠️ **Require signed commits** — Optional. Ivan pushes from one machine. Set this if you're worried about supply-chain attacks via credential theft.

## After saving the rule

1. Open a test PR to verify the rule works. The PR should:
   - Show 4 "Required" status checks below the merge button
   - Block "Merge pull request" until all 4 are green
2. Check the "Files changed" tab — review the rule visually.
3. Notify the team (Ivan, in this case): "Branch protection is on. Pushes to main are blocked; use a PR."

## What to require on the other branches

| Branch | Rule | Why |
|---|---|---|
| `main` | All 4 above | Production. Sacred. |
| `infra/*`, `chore/*`, `docs/*` | All 4 above | Also merges to main; same bar. |
| `feat/*` | None | Work-in-progress. |
| `refactor/*` | All 4 above | Sibling refactor session lands here; needs to pass before merging. |
| `fix/*` | All 4 above | Same. |

## What the operator should NOT do

- ❌ Don't add "require review" without a reviewer team set up. The repo has 1 developer. Setting "require 1 reviewer" + "no reviewers available" = every PR is unmergeable.
- ❌ Don't enable "auto-merge" without the merge queue. Auto-merge + missing required checks = CI gets spammed.
- ❌ Don't use "branch protection rulesets" (the newer feature) yet. The classic branch protection is what the existing tools (gh CLI, branch-archive scripts) work against.

## The 4 protected checks — what each one catches

| Check | Catches | Misses |
|---|---|---|
| Currency Drift Lint (D3) | `float` used for money; `int(Decimal(...))` instead of `to_int_gs()`; Gs vs ₲ spelling; bare `Gs` instead of `Gs. 729.167` | Real-world money bugs (e.g., wrong rounding edge case) |
| Smoke (deploy-shape) | Migration drift (PG ↔ SQLite); missing alembic-style forward-only migration; env var shape change | E2E flow bugs; UI breakage |
| Browser (Playwright, advisory) | Login flow broken; navigation dead-ends; form submission 500s | Cross-browser; slow-path bugs |
| Route Smoke (fast gate) | Any route returns 500 on basic GET/POST; CSRF regression; auth bypass | Subtle business-logic bugs that return 200 with wrong data |

## References

- `docs/operations/2026-10-09-three-env-deploy.md` §"Auto-deploy (CI)"
- `docs/operations/2026-10-09-ci-recovery.md`
- `docs/operations/dora-2026-Q4.md` (the metrics the gate will improve)
- `docs/ci/toolchain-versions.md`
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
