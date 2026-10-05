# PR #13 carryover cleanup — pre-merge branch surgery

**Date:** 2026-09-24
**Author:** Iván (operator)
**Status:** DRAFT — pending Kiki
**Tickets:** SASKIA-OPS-042 (proposed)

---

## TL;DR

`feat/sazon-r2-recipe-filters` (PR #13) bundles **two user stories that already exist on their own fix branches**:

- **US 1.1** (image rendering carryover) → already the entire point of `fix/sazon-r2-ui-spanish-images` (PR #19)
- **US 2.1** (href copy carryover) → already the entire point of `fix/sazon-r2-small-href-copy` (PR #18)

If we merge in the natural dependency order (#16 → #14 → #13 → #17 → #15 → #18 → #19), then **#18 and #19 will either no-op merge against an already-merged #13, or trigger a conflict** that requires re-rebasing the fix branches on the post-#13 main.

Cleaner path: rebase #13 to drop the carryover now. Fix branches then merge cleanly after the feat branches.

---

## Why this happened

Likely Kiki picked up the image/href carryover while working on the recipe-filters branch and bundled it rather than splitting it out. Not a bug — just an artifact of working across R1 → R2 transition. The two carryover items are tiny (`image_url` exposure + a copy string change) and would be invisible in a normal diff, but in a 7-PR wiring exercise they create a merge-order trap.

---

## Action plan

### Step 1 — rebase #13 to drop US 1.1 + US 2.1 carryover

```
cd /path/to/sazon-app-work
git fetch origin
git checkout feat/sazon-r2-recipe-filters
git rebase -i origin/main
# Identify the commit(s) that touch US 1.1 / US 2.1
# Either drop those commits, or `git rebase --edit-todo` and reword them as fix-branch tip-offs.

# Or, simpler for Kiki: use git revert
git log --oneline origin/main..HEAD
# Find the offending commit hash, then:
# git revert <commit> --no-commit
# git checkout main -- app/path/to/carryover_files
# git commit -m "feat(sazon-r2): recipe filters + sub-recipe visual (US 3.1, US 3.2)"
```

### Step 2 — force-push #13

```
git push --force-with-lease origin feat/sazon-r2-recipe-filters
```

PR #13's diff title changes from *"recipe filters + sub-recipe visual (US 3.1, US 3.2) + image/href carryover (US 1.1, US 2.1)"* → *"recipe filters + sub-recipe visual (US 3.1, US 3.2)"*. Reviewer scope goes back to "just the R2 work."

### Step 3 — leave #18 and #19 alone

PRs `fix/sazon-r2-small-href-copy` and `fix/sazon-r2-ui-spanish-images` already carry US 2.1 and US 1.1 respectively. They merge cleanly after #16, #14, #13, #17, #15 land.

### Step 4 — when CI budget unlocks

Merge order becomes:
```
#16  feat/sazon-r2-data-models        → US 2.2, 2.3, 3.3   (foundation)
#14  feat/sazon-r2-pos-split          → US 4.2, 4.3
#13  feat/sazon-r2-recipe-filters     → US 3.1, 3.2  (carryover dropped)
#17  feat/sazon-r2-sale-packaging     → US 4.1
#15  feat/sazon-r2-encargos-cancel    → US 4.4, CIE-01
#18  fix/sazon-r2-small-href-copy     → MER-03, DATA-01
#19  fix/sazon-r2-ui-spanish-images   → US 1.1
```

Between each: rebase the next on `main`, wait for CI green, merge.

---

## Acceptance

- [ ] PR #13's diff title no longer mentions US 1.1 or US 2.1
- [ ] PR #13's file changes touch only recipe-filter + sub-recipe-visual concerns
- [ ] PRs #18 and #19 still carry their respective US stories
- [ ] When CI is green, all 7 PRs merge in order without no-op or conflict
- [ ] No `x-access-token` / `ghp_*` leakage in the force-push (pre-commit `check-no-secrets` should catch it; rerun manually)


---

## Addendum (2026-09-24, post-audit session): stack topology discovery

Rebasing #13 alone is **not sufficient** — the branches are fully stacked, not independent:

```
9831ea4 (old main)
  └─ cf01fd6 (US 1.1 carryover)
      ├─ 926867f → #19 fix/sazon-r2-ui-spanish-images (tip)
      ├─ 0121e8a → #18 fix/sazon-r2-small-href-copy (tip)
      └─ a293bfb (US 2.1 carryover) → f0db4cd → #13 tip
            └─ 0bc1341 → #14 tip
                  └─ d8c237e → #15 tip
                        ├─ cb36eec → e49cbae → #17 tip
                        └─ 7a54f3b → #16 tip
```

The three carryover commits (cf01fd6, 926867f, a293bfb) sit at the **bottom of the entire stack**. Dropping them from #13 requires rebasing #14, #15, #16, #17 on top (5 force-pushes total), and #18/#19 then need rebasing onto new-main instead of merging after it.

**Revised recommendation:** since every branch descends from the carryover commits, the cheapest clean path is a single `git rebase --onto` cascade (or merge the stack bottom-up and let #18/#19 no-op — a no-op merge is harmless if GitHub is told to merge anyway). Decide with Kiki before touching history: the current plan's Step 1-2 alone would leave the stack inconsistent.

Status remains DRAFT — pending Kiki.
