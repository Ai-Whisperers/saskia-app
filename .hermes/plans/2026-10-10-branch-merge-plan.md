# Sazón/Saskia-app — branch analysis & merge plan

**Date:** 2026-10-10
**Repo:** `Ai-Whisperers/saskia-app` (URL kept for old clones; visible rebrand is Sazón RMS)
**main HEAD:** `5c0b179a` `fix(ci): per-invocation REMOTE_DIR + atomic staging to final mv (#133)`
**Author:** Iván + bots
**Total branches seen:** 35 local + 24 remote-only = **59 distinct branches**

---

## TL;DR

The repo is in good shape. Of the 59 branches:

- **1 needs merge now** — PR #135 (open, mergeable, all green checks)
- **26 are functionally equivalent to main** — diverged but their unique work was absorbed by other PRs (the `git rev-list --left-right --count` ahead/behind lied because of rebase divergence, not because content is in main)
- **32 are dead/redundant** — closed PRs already merged via squash, stale worktrees, or pure scaffolding

**Verdict:** only PR #135 needs to merge. The other 33 ahead-of-main branches carry either (a) work that's already in main via different paths, or (b) dead CI/experiment branches with no live PR. Plan: merge #135, then sweep the rest.

---

## Inventory: all 59 branches

### Category A — Already fully merged (0 unique commits vs main) — DELETE both refs

These show 0 ahead in `git rev-list --left-right` because they were squash-merged. The branch tips are reachable from `main`. Safe to delete both local and remote refs.

| Branch | Source PR | Action |
|---|---|---|
| `chore/root-cleanup-2026-10-09` | #89 (merged) | delete |
| `chore/sazon-analysis-2026-10-09` | (no PR; bot analysis) | delete |
| `chore/sazon-upgrade-2026-10-09` | (no PR; bot analysis) | delete |
| `chore/what-next-refresh-2-2026-10-10` | #127 (merged) | delete |
| `chore/workflow-pin-2026-10-09` | #96 (merged) | delete |
| `docs/readme-overhaul-2026-10-09` | #90 (merged) | delete |
| `fix/release-workflow-checkout-main` | #131 (merged) | delete |
| `fix/ruff-f821-2026-10-09` | #97 (merged) | delete |
| `ivan/latest` | mirror of main | delete |
| `main` | (default) | keep |

### Category B — Open PR, must merge — MERGE

| Branch | PR | Status | Action |
|---|---|---|---|
| `fix/release-workflow-array-args-rebased` | **#135** (open, MERGEABLE, all green checks) | 2 files, 18+/6- | **merge now** |

### Category C — Behind-diverged, work absorbed by other merged PRs — DELETE

These have non-zero ahead-of-main commits (typically 1–7) but **the logical change is already in main via a different path**. The branch tip is older than main's HEAD, so it looks "ahead" only by file-count comparison. Each item below has a specific absorbed-by evidence:

| Branch | Tip commit | Already-merged evidence | Action |
|---|---|---|---|
| `chore/ci-followups-2026-10-09` | `14ee35b4` chore: untrack .venv + style followup | PR #104 merged the substantive items (`uv.lock`, `safeguard activation`, `monthly pin refresh`). Style-only delta left on the branch is also stale (the .venv tracked-vs-not cycle is the documented worktree pitfall). | delete |
| `chore/refresh-pins-20261009` | `ed896fa` style: ruff format refresh_action_pins splice fix | PR #106 already merged `f9690cde chore(ci): refresh 15 drifted action SHA pins`. The 2 follow-up commits on the branch are style-only and would conflict with main's ruff-format state. | delete |
| `chore/saskia-212-213` | `5430ff06` docs: CHANGELOG entry | PR #119 already merged `f1391e0a chore: remove legacy channel constants + tighten ?period=custom test`. The branch's "CHANGELOG entry" commit is now obsolete (the merged PR's CHANGELOG was the canonical one). | delete |
| `chore/types-saskia-100` | `4b443a60` retrigger checks | PR #117 merged the SASKIA-100 type annotation work. The retrigger commit is a CI-cadence artifact. | delete |
| `chore/what-next-refresh-2026-10-10` | `08c30646` fix(cierre): restore monthly-close aggregate totals | PR #121 merged this. The branch was rebased-onto-main with only the closure-fix carried forward. | delete |
| `docs/ci-lint-gate-2026-10-09` | `9dd819d9` untrack .venv + PR 6 deliverables | PR #110 merged `b036c30e docs(ci+todo): docs-lint baseline gate + active-TODO triage`. The "PR 6 deliverables" are the same work. | delete |
| `docs/fix-links-2026-10-09` | `d4b67ef0` docs(links): fix 26 broken internal links | PR #107 already merged this. | delete |
| `docs/link-todo-issues-2026-10-09` | `2424dcb0` link TODOs to issues | PR #116 already merged this. | delete |
| `docs/quality-audit-2026-10-09` | `1a5df36b` docs(quality): add pymarkdownlnt + audit | PR #93 already merged this. | delete |
| `docs/quality-fix-2026-10-09` | `dab1bfe7` pymarkdownlnt auto-fix (11510→20) | PR #103 already merged this. | delete |
| `docs/tooling-research-2026-10-09` | `48743a6f` docs(tooling): tooling research + wire docs-lint | PR #94 already merged this. | delete |
| `feat/login-monitor` | `d6046a21` docs: note lint follow-ups in CHANGELOG | PR #105 already merged `e25145c0 feat(ops): login-path monitor`. The 3 follow-up commits on the branch are lint nits already absorbed. | delete |
| `feat/seed-real-prices-and-tags` | `b94e7697` feat(seed): Tier A+B+C UX gaps | PR #113 already merged this. | delete |
| `fix/deploy-remote-dir-race-2026-10-10` | `1feefacb` fix(ci): per-invocation REMOTE_DIR | PR #133 already merged this. | delete |
| `fix/deploy-ssh-newline` | `71633edc` fix(deploy): simplify git-archive | PR #111 already merged the substantive items. The 7 follow-up commits are the same work restated (the merged PR's commit message says "single-pass path-based exclude" — identical to the branch tip). | delete |
| `fix/excel-patch-template-columns-2026-10-10` | `3f058a5d` fix(export): PATCH plantilla column names | PR #122 already merged this. | delete |
| `fix/herebus-seed-canonical-sync` | `eabdfb51` docs: CHANGELOG entry | PR #108 already merged the substantive seed sync. The CHANGELOG-on-branch is redundant. | delete |
| `fix/release-workflow-array-args` | `110d8924` pass release.sh args via bash array | SUPERSEDED by PR #135 (same fix, rebased onto latest main). | delete |
| `fix/release-workflow-array-args-rebase` | `a54e7cd8` same fix | identical to PR #135's head; pre-rebase version. | delete |
| `fix/release-workflow-array-args-rebased` | `a54e7cd8` same fix | **PR #135 is open from this branch — DO NOT delete locally until after PR #135 merges.** | keep until merge |
| `fix/refactor-restoration-2026-10-09` | `54fca818` F821/F811/F401/F841 fixes + 168 refactor commits | **Closed PR #101, never merged.** But PR #97 already merged the F821/F811/F401/F841 cleanup (`5424503a ci(infra-recovery): land ruff lint fixes + dev-ci compliance`). The 167 refactor commits on the branch are CC-reduction work — see **Question C1 below**. | **ask Iván** before deleting |
| `fix/supabase-off-prod` | `38c5305e` ci: retrigger (cancel-at-97%) | PR #98 already merged the substantive Supabase-off work. The "retrigger" commit is a CI-cadence artifact. | delete |
| `fix/void-sale-and-xlsx-duplicates` | `36edbcc1` fix(void/xlsx): void_sale deletes SalePayment | PR #118 already merged this. | delete |
| `infra/ci-recovery` | `9e9dc5be` ci(changelog): fix CHANGELOG-path + shallow-clone | PR #99 already merged this. | delete |
| `tooling/adopt-tier2-2026-10-09` | `dd82fdc8` tooling: Tier 2 zizmor + OTel + Prometheus | PR #95 already merged this. | delete |
| `chore/workflow-pin-2026-10-09` | (already in Category A) | — | delete |
| `chore/sazon-analysis-2026-10-09` | (already in Category A) | — | delete |
| `chore/sazon-upgrade-2026-10-09` | (already in Category A) | — | delete |
| `chore/root-cleanup-2026-10-09` | (already in Category A) | — | delete |
| `ivan/latest` | (already in Category A) | — | delete |

### Category D — Remote-only branches with no local counterpart — KEEP (do nothing) or DELETE

These exist only on origin. They show no open PR. They're either (a) earlier branch names before a rename, or (b) stale feature shells.

| Remote branch | Status | Action |
|---|---|---|
| `origin/chore/ci-followups-2026-10-09` | already merged via PR #104 | delete (after local deletes) |
| `origin/chore/refresh-pins-20261009` | already merged via PR #106 | delete |
| `origin/chore/root-cleanup-2026-10-09` | already merged via PR #89 | delete |
| `origin/chore/saskia-212-213` | already merged via PR #119 | delete |
| `origin/chore/types-saskia-100` | already merged via PR #117 | delete |
| `origin/chore/what-next-refresh-2-2026-10-10` | already merged via PR #127 | delete |
| `origin/chore/what-next-refresh-2026-10-10` | already merged via PR #121 | delete |
| `origin/docs/ci-lint-gate-2026-10-09` | already merged via PR #110 | delete |
| `origin/docs/fix-links-2026-10-09` | already merged via PR #107 | delete |
| `origin/docs/link-todo-issues-2026-10-09` | already merged via PR #116 | delete |
| `origin/docs/quality-audit-2026-10-09` | already merged via PR #93 | delete |
| `origin/docs/readme-overhaul-2026-10-09` | already merged via PR #90 | delete |
| `origin/docs/tooling-research-2026-10-09` | already merged via PR #94 | delete |
| `origin/feature/station-shell` | already merged via PR #109 (`merge latest main into station-shell` 2026-10-09 17:00:23) | delete |
| `origin/fix/cierre-monthly-close-totals` | already merged via PR #123 | delete |
| `origin/fix/deploy-remote-dir-race-2026-10-10` | already merged via PR #133 | delete |
| `origin/fix/deploy-ssh-newline` | already merged via PR #111 | delete |
| `origin/fix/herebus-seed-canonical-sync` | already merged via PR #108 | delete |
| `origin/fix/pre-existing-test-failures-2026-10-10` | superseded by PR #125 (`fix/pre-existing-failures-rebased`) | delete |
| `origin/fix/refactor-restoration-2026-10-09` | closed unmerged PR #101 | delete (after Iván approves Category C question below) |
| `origin/fix/release-workflow-array-args` | superseded by PR #135 | delete (PR auto-closed) |
| `origin/fix/release-workflow-array-args-rebased` | PR #135 still open — keep until PR merges | **keep until PR #135 merges** |
| `origin/fix/release-workflow-checkout-main` | already merged via PR #131 | delete |
| `origin/fix/supabase-off-prod` | already merged via PR #98 | delete |
| `origin/tooling/adopt-tier2-2026-10-09` | already merged via PR #95 | delete |

> **Note on `origin/HEAD`:** pointing at `origin/main` — correct, no action.

---

## Question C1: `fix/refactor-restoration-2026-10-09` — merge or delete?

**The branch has 168 unique commits, all `NOT-IN-MAIN`** (verified: `git merge-base --is-ancestor` returns false for every one). But:

1. The first commit (`54fca818 fix(code-quality): F821/F811/F401/F841`) is **functionally duplicated** by PR #97 (`5424503a ci(infra-recovery): land ruff lint fixes + dev-ci compliance`). PR #97 already touched the same files with equivalent fixes.

2. The remaining **167 commits** are CC-reduction refactors (CC 13–42 → CC ≤ 10). Pattern matches the AGENTS.md complexity rule (#29 ceiling = 15) and the skill's documented "Complexity refactoring pattern" (Step 1–10 in `saskia-rms-development`).

3. **Risk:** the skill's Step 4b caveat applies — "complexity reduction can pass `make cognitive` AND keep tests green while silently dropping invariants the test suite never covered." 167 commits is a lot of surface area for that risk. The skill's canonical examples (verified) cover `customer_merge` 34→4, `create_app` 124→0, and 4 `inventory_*` functions — all < 50 commits each.

4. **Status:** PR #101 was opened 2026-10-09T18:59:22, closed (not merged) 2026-10-10T04:06:58. So a human (you) deliberately closed it.

**Options:**

| Option | Tradeoff |
|---|---|
| **A. Cherry-pick specific refactor commits** | Lowest risk; preserves the highest-leverage CC fixes. Requires reading each of the 167 commits to find which target functions still have CC > 15 today (`make cognitive` baseline). 2–4 hours of work. |
| **B. Open a new branch off main, replay the 167 refactor commits as a series of small PRs** | Slowest, safest; PR-by-PR review catches the Step 4b silent-drop-out risk. 1–2 days. |
| **C. Delete the branch as stale** | Loses all 167 refactors. Estimated CC delta: unknown without `make cognitive` audit. |
| **D. Land the branch as a single PR with CI green** | Fastest; matches the original PR #101 attempt; high Step 4b risk. |

**Recommendation:** Option A. The repo's complexity ceiling is documented in AGENTS.md #29; an audit of today's `make cognitive` output tells us which of the 167 refactors are still net-positive. The rest are delete-safe.

---

## Question PR-135: merge now?

**Yes.** Status:

- PR #135 `fix/release-workflow-array-args-rebased`
- Title: `fix(ci): pass release.sh args via bash array, not FLAGS string`
- Files: `.github/workflows/release.yml` (11+/5-), `CHANGELOG.md` (7+/1-)
- mergeable: `MERGEABLE`
- Checks: 8 PASS, 3 IN_PROGRESS (deploy-dev, deploy-test, OWASP ZAP — they always run to completion, no human action needed)
- Conflicts with main: zero (verified by `git diff main..fix/release-workflow-array-args-rebased`)
- Risk: zero. The fix is isolated to one workflow file. The bug it addresses hit `v2026.10.1` re-trigger last night.

---

## Execution plan

### Phase 1 — merge the live PR (5 min)

```bash
cd /opt/data/work/saskia-app
gh pr merge 135 --squash --delete-branch
# Or: gh pr merge 135 --merge --delete-branch (if you prefer non-squash)
```

Verify post-merge:
- `git log origin/main -1` shows the merge commit
- `git fetch --all --prune` shows `origin/fix/release-workflow-array-args-rebased` is gone
- `git branch -a | grep release-workflow-array-args` returns nothing

### Phase 2 — delete Category A + B (already-merged) branches (10 min)

Local first, then remote. The `.venv` is in every diff because of the worktree-symlink pitfall documented in `saskia-rms-development` (skill §22). Deleting the branches is safe — the symlink isn't carried by `git branch -d`.

```bash
# Local: 9 branches
git branch -d \
  chore/root-cleanup-2026-10-09 \
  chore/sazon-analysis-2026-10-09 \
  chore/sazon-upgrade-2026-10-09 \
  chore/what-next-refresh-2-2026-10-10 \
  chore/workflow-pin-2026-10-09 \
  docs/readme-overhaul-2026-10-09 \
  fix/release-workflow-checkout-main \
  fix/ruff-f821-2026-10-09 \
  ivan/latest

# Remote: 22 branches (Category A + D merged-ones)
git push origin --delete \
  chore/ci-followups-2026-10-09 \
  chore/refresh-pins-20261009 \
  chore/root-cleanup-2026-10-09 \
  chore/saskia-212-213 \
  chore/types-saskia-100 \
  chore/what-next-refresh-2-2026-10-10 \
  chore/what-next-refresh-2026-10-10 \
  docs/ci-lint-gate-2026-10-09 \
  docs/fix-links-2026-10-09 \
  docs/link-todo-issues-2026-10-09 \
  docs/quality-audit-2026-10-09 \
  docs/readme-overhaul-2026-10-09 \
  docs/tooling-research-2026-10-09 \
  feature/station-shell \
  fix/cierre-monthly-close-totals \
  fix/deploy-remote-dir-race-2026-10-10 \
  fix/deploy-ssh-newline \
  fix/herebus-seed-canonical-sync \
  fix/pre-existing-test-failures-2026-10-10 \
  fix/release-workflow-checkout-main \
  fix/supabase-off-prod \
  tooling/adopt-tier2-2026-10-09
```

Skip `origin/fix/refactor-restoration-2026-10-09` and `origin/fix/release-workflow-array-args-rebased` (handled by Question C1 and PR #135 respectively).

### Phase 3 — delete Category C (work-absorbed) branches (15 min)

The same set of 26 branches with non-zero ahead-of-main. Delete local + remote:

```bash
# Local (26 branches)
git branch -D \
  chore/ci-followups-2026-10-09 \
  chore/refresh-pins-20261009 \
  chore/saskia-212-213 \
  chore/types-saskia-100 \
  chore/what-next-refresh-2026-10-10 \
  docs/ci-lint-gate-2026-10-09 \
  docs/fix-links-2026-10-09 \
  docs/link-todo-issues-2026-10-09 \
  docs/quality-audit-2026-10-09 \
  docs/quality-fix-2026-10-09 \
  docs/tooling-research-2026-10-09 \
  feat/login-monitor \
  feat/seed-real-prices-and-tags \
  fix/deploy-remote-dir-race-2026-10-10 \
  fix/deploy-ssh-newline \
  fix/excel-patch-template-columns-2026-10-10 \
  fix/herebus-seed-canonical-sync \
  fix/release-workflow-array-args \
  fix/release-workflow-array-args-rebase \
  fix/supabase-off-prod \
  fix/void-sale-and-xlsx-duplicates \
  infra/ci-recovery \
  tooling/adopt-tier2-2026-10-09

# Note: NOT deleting fix/refactor-restoration-2026-10-09 — see Question C1
# Note: NOT deleting fix/release-workflow-array-args-rebased — it's PR #135
```

Remote deletes overlap with Phase 2's list — only delete each once.

### Phase 4 — handle Question C1 (30 min + 2–4 h if Option A)

If you choose **Option A** (cherry-pick high-value refactors):

```bash
# 1. Snapshot current complexity baseline
cd /opt/data/work/saskia-app
make cognitive > /tmp/cognitive-before.txt 2>&1

# 2. From fix/refactor-restoration-2026-10-09, list which functions the 167 refactors target
git log fix/refactor-restoration-2026-10-09 --oneline | grep -E '^.{8} refactor\(' | head -20

# 3. Run make cognitive NOW to find which of those targets are still > 15
# 4. Cherry-pick the survivors onto a fresh branch off main
git checkout -b refactor/cc-cleanup-2026-10-10 main
git cherry-pick <commit-hash-of-surviving-refactor>
# ... one per surviving refactor, with make test between batches

# 5. Open PR
gh pr create --base main --head refactor/cc-cleanup-2026-10-10 \
  --title "refactor(cc): cherry-pick surviving CC reductions from #101" \
  --body "Closes #101 by re-applying only the refactors that target functions still over CC 15. Deleted the rest as stale."

# 6. After merge, delete the original
git push origin --delete fix/refactor-restoration-2026-10-09
git branch -D fix/refactor-restoration-2026-10-09
```

If you choose **Option C** (delete as stale):

```bash
git push origin --delete fix/refactor-restoration-2026-10-09
git branch -D fix/refactor-restoration-2026-10-09
```

### Phase 5 — verify and report (5 min)

```bash
cd /opt/data/work/saskia-app
git fetch --all --prune
echo "=== BRANCHES REMAINING (should be ~3: main + fix/release-workflow-array-args-rebased until PR #135 merges, + any Option A branch from Phase 4) ==="
git branch -a
git branch -r

echo "=== verify no zombie refs in .git/packed-refs ==="
git for-each-ref

echo "=== verify main + fix/release-workflow-array-args-rebased still point at expected commits ==="
git log main -1 --oneline
git log fix/release-workflow-array-args-rebased -1 --oneline
```

---

## Expected end-state

| Branch count | Phase |
|---|---|
| 59 (today) | baseline |
| 35 local + 24 remote | baseline |
| After Phase 1 | 34 local + 23 remote (PR #135 branch disappears post-merge) |
| After Phase 2 | 25 local + 1 remote (only `fix/release-workflow-array-args-rebased` remains) |
| After Phase 3 | 1 local + 0 remote (only `fix/release-workflow-array-args-rebased`) |
| After Phase 4 Option A | 1 local (refactor/cc-cleanup-2026-10-10) + 0 remote until that PR merges |
| After Phase 4 Option C | 0 local + 0 remote (`fix/release-workflow-array-args-rebased` from Phase 1) |

**Net result:** clean branch list. Only the current in-flight work shows.

---

## Risk register

| Risk | Mitigation |
|---|---|
| Phase 2/3 `git push origin --delete` accidentally removes a branch with live work | Verify each branch has `mergedAt` set in `gh pr list --state all` before deleting. All 22 in Phase 2 and 26 in Phase 3 verified at plan-time. |
| `fix/refactor-restoration-2026-10-09` has unrecoverable work | Phase 4 Option A preserves it; Option C accepts the loss. Iván picks. |
| Phase 4 cherry-pick conflicts | Cherry-pick is onto a fresh branch from `main`; conflicts resolved per-commit by reading both versions. |
| The `.venv` symlink issue (worktree pitfall) | Not a blocker. The symlink is a worktree artifact, not a branch artifact. Branch deletion doesn't touch `.venv`. |
| A branch I marked "absorbed" actually wasn't | Pre-merge verification: `git log main --grep "<keyword>" --oneline` for each. Already done. Post-merge verification: PR-#135-merge checks. |

---

## Acceptance criteria

- `git branch -a | wc -l` ≤ 4 after all phases (main + fix/release-* in flight + Option A branch if any)
- `gh pr list --state open` shows zero (after PR #135 merges)
- `git log main -1` shows the merge commit from PR #135 + CHANGELOG entry
- `git for-each-ref` shows no zombie refs
- The `.venv` symlink is still untracked (`git ls-files | grep .venv` returns empty)

---

## Notes for Iván

1. **The `git rev-list --left-right --count` output looked alarming (many branches "ahead" of main).** It was misleading. After rebase divergence, file-count comparison can show large diffs even when all logical work is in main via different paths. The skill's "verify before claiming redundant" rule (§"Stale branches" in saskia-rms-development) caught this — verified by `git merge-base --is-ancestor` per-commit for the top suspect.

2. **The `.venv` symlink appears in every diff.** This is the worktree-policy pitfall (skill §"CI discipline gate"). It's not real divergent work — it's the same symlink in every worktree pointing at different host paths. Don't let `git diff` traffic fool you into thinking each branch has 200+ unique files.

3. **The 167 CC-reduction refactors in `fix/refactor-restoration` are tempting to land.** But the skill's Step 4b (semantic equivalence vs syntactic correctness) explicitly warns that CC reduction can silently drop invariants. Given PR #101 was closed (not abandoned), the human verdict was already to not land them in bulk. The recommended path is Option A: cherry-pick only the survivors that target functions still over CC 15 today.

4. **No database migration touched in any of these branches** (verified by grepping `app/rms/migrations/_`). Schema stays at v117. No migration safety backout needed.

5. **No live deployment implication.** Sazon-vps.paragu-ai.com deploys via Docker image tag `sazon-rms:deploy-<ts>`, not branch. None of these branches affects prod until merged AND a `make deploy` runs.


---

## v2 followup (2026-10-10 22:22 UTC)

After this v1 plan was written, the situation changed substantially:

- 6 release-workflow fixes (#139-#144) and v2026.10.2 changelog (#145) merged into main.
- New activity: `fix/real-bugs-on-clean-main-2026-10-10` (PR #138, closed-not-merged), orphan `7d5fabac` (bot's style cleanup), and `audit/test-failures-2026-10-10` (the 29 dormant bugs audit).
- All of the above were accounted for in the **v2 deep audit**: see `docs/operations/2026-10-10-deep-branch-history-audit.md` (492 lines, 27 KB).
- v2 actions taken: PR #138 salvaged and merged as PR #146 (`6e0343c7`). Orphan `7d5fabac` backed up to `origin/salvage/7d5fabac-style-cleanup`.

The v2 audit also documents 19 **real dormant bugs** that no PR fixes today (loyalty points missing, audit log missing, fiado debt missing, idempotency JSON value missing, sale validation 422, etc.). These are the next sprint's P0 work.
