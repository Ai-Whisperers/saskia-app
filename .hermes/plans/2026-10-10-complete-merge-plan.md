# Sazón-app — Complete Merge Plan (2026-10-10 v3)

**Goal:** Merge ALL salvageable branches and PRs into `main`, delete the dead ones, leave the repo clean.

**Current state verified at 2026-10-10 22:30 UTC.**

---

## Branches by merge disposition

### Group A — In main, label only, DELETE both refs

| Branch | HEAD | Action |
|---|---|---|
| `audit/clean-main-test-state-2026-10-10` | `0205f885` (in main) | DELETE local + remote |
| `docs/v2026.10.2-changelog` | `654dc477` (in main) | DELETE local + remote |
| `fix/refactor-restoration-2026-10-09` | `78828464` (in main) | DELETE local + remote |
| `main-local` | `78828464` (in main) | DELETE local |
| `origin/audit/test-failures-2026-10-10` | (saskia-refactor worktree's primary branch) | KEEP — this is the audit branch's ref to the worktree, can't delete without breaking saskia-refactor |

### Group B — Has unique work, MERGE then delete

| Branch | HEAD | Unique commits | Action |
|---|---|---|---|
| `audit/test-failures-2026-10-10` | `aab18259` | 2 (audit doc) | MERGE the audit doc commit to main via PR |
| `fix/p0-bugs-2026-10-10` | `aab18259` | same as above (duplicate of audit branch) | DELETE — duplicate of audit branch |
| `salvage/7d5fabac-style-cleanup` | `7d5fabac` | 1 (orphan root commit) | Already on remote as backup — DO NOT MERGE (it's a historical snapshot), keep as backup branch |

### Group C — Already in main via PR #146

| Branch | Status |
|---|---|
| `fix/real-bugs-on-clean-main-2026-10-10` (PR #138, closed) | Work landed via PR #146; branch was already deleted in last session |

### Group D — Closed-not-merged PRs (already absorbed)

All 6 closed-not-merged PRs (#138, #134, #130, #128, #124, #120) have their work in main via other PRs:
- #138 → merged as #146
- #134 → reopened/merged as #135
- #130 → reopened/merged as #132
- #128 → reopened/merged as #129
- #124 → reopened/merged as #129 (same fix)
- #120 → reopened/merged as #125

No action needed.

---

## Plan steps

1. **Create branch `merge/audit-into-main-2026-10-10`** from main
2. **Cherry-pick the 2 audit commits** (the audit doc) onto the branch
3. **Add CHANGELOG.md entry** for the audit merge
4. **Push + open PR** (e.g., #147)
5. **Wait for Fast lint + test to pass**
6. **Merge with --admin** (deploy gate is advisory)
7. **Delete the local branches in Group A + the duplicate `fix/p0-bugs-2026-10-10`**
8. **Prune the 9 zombie worktrees** (after spot-check that none has uncommitted work)
9. **Drop the 2 stash entries** (both superseded)
10. **Verify final state**: main up-to-date, no dead refs

---

## Worktree zombies to prune

All 9 have HEAD=0000... (no actual working tree on disk for them, OR the directory is gone but the registration persists). Safe to `git worktree prune`.

| Worktree path | Branch |
|---|---|
| `saskia-app-docs-quality` | `docs/quality-audit-2026-10-09` |
| `saskia-app-f821` | `fix/ruff-f821-2026-10-09` |
| `saskia-app-readme` | `docs/readme-overhaul-2026-10-09` |
| `saskia-app-root-cleanup` | `chore/root-cleanup-2026-10-09` |
| `saskia-app-tooling-adopt` | `tooling/adopt-tier2-2026-10-09` |
| `saskia-app-tooling-research` | `docs/tooling-research-2026-10-09` |
| `saskia-app-workflow-pin` | `chore/workflow-pin-2026-10-09` |
| `saskia-settings-fix` | `chore/sazon-upgrade-2026-10-09` |
| `sazon-analysis-clean` | `chore/sazon-analysis-2026-10-09` |

But: each of these branches IS in main (the PRs merged). So pruning the worktree DOES delete the branch ref. Need to verify the branches exist elsewhere first.

---

## Verification plan

After all operations:
- `git branch` should show only: `main`, `salvage/7d5fabac-style-cleanup`
- `git branch -r` should show: `origin/main`, `origin/salvage/7d5fabac-style-cleanup`
- `git worktree list` should show only: `/opt/data/work/saskia-app`, `/opt/data/work/saskia-app-main`, `/opt/data/work/saskia-app-ci`, `/opt/data/work/saskia-refactor`
- `git stash list` should be empty
- 0 open PRs