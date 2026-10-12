# SIBLING-COORDINATION-NOTE — parallel-session protocol for `saskia-app`

**Why this exists:** multiple Hermes sessions (and Claude Code, and Codex) work this repo in parallel. The cost of stepping on toes is high. The cost of *not* working in parallel is even higher.

---

## 0. The 30-second summary

1. **One checkout per session, one branch per checkout.** Use git worktrees.
2. **Commit early, commit often.** Never have uncommitted work sitting in the worktree for >30 min.
3. **Stage only YOUR files.** Never `git add -u` or `git add .` on a shared worktree.
4. **Read `.hermes/sibling-flush-note.md` first** (if present) when you arrive. It explains what other sessions were doing.

---

## 1. Worktree policy (canonical)

Canonical worktree for Iván is `/opt/data/work/saskia-app`. All other saskia worktrees should be off `main` (or off a feature branch), not off another session's feature branch.

| Worktree | Branch | Owner |
|---|---|---|
| `/opt/data/work/saskia-app` | varies (currently `SASKIA-212-recipe-instructions-editor`) | sibling(s) — read .hermes/sibling-flush-note.md |
| `/opt/data/work/saskia-app-abstraction-gates` | `main` | this / previous session (211d/211e PRs) |
| `/opt/data/work/saskia-app-vaquita` | `SASKIA-213-vaquita-seed-data-update` | sibling |
| `/opt/data/scratch/saskia-app` | `main` | **DO NOT TOUCH** — old git history, separate project state |

**To create a new one:** `git -C /opt/data/work/saskia-app worktree add /opt/data/work/saskia-app-<name> -b <branch> main`. Then `cd` into it for all your work.

---

## 2. Branch discipline

| Action | Allowed? | Why |
|---|---|---|
| `git checkout -b feat/SASKIA-NNN` from `main` | ✅ yes | standard feature work |
| `git checkout feat/SASKIA-NNN-other-session` to "help" | ❌ no | stomps their work; use a separate branch |
| `git rebase main` while sibling has unmerged commits | ⚠️ careful | sibling's commits stay on `main` after rebase; just verify with `git log main..HEAD --oneline` |
| `git push origin main` from a feature branch | ❌ no | pushes nothing useful; use `git push origin <branch>` |
| `git commit --author=...` to attribute someone else's work | ⚠️ only when salvaging their WIP with their explicit OK | otherwise mis-attribution |

---

## 4. Stage only your files

When sibling sessions have uncommitted dirty files in the same worktree:

```bash
# RIGHT: stage only your exact paths
git add app/routers/inventory.py tests/test_inventory.py
git diff --cached --stat  # verify the file list is exactly what you intend

# WRONG: sweeps in sibling's unrelated changes
git add -u
git add .
```

If `git status -s` shows files you didn't touch as `M`, **leave them alone**. They belong to another session. Commit your own files separately.

---

## 5. The orphan-branch rescue pattern

Sometimes a sibling session's commit was reverted by an automated cleanup (the canonical example: `git reset --hard origin/main` discarding their WIP). The recovery is:

```bash
# 1. Did their work survive as a ref anywhere?
git reflog --all | grep -i "<their-commit-message>"
git fsck --no-reflogs --lost-found 2>/dev/null

# 2. If not, and you have a similar ref:
git branch backup-<descriptive-name> <sha>
git checkout <their-original-branch>
git reset --hard <their-sha>     # only if you have their sha

# 3. If neither works, ask the sibling before re-doing the work.
```

---

## 6. Sibling-flush-note convention

When a session ends, it should append to `.hermes/sibling-flush-note.md`:

```markdown
## Update YYYY-MM-DD HH:MM UTC — <one-line description>

**Action taken:** <what I did this session>
**Where:** <which worktree, which branch, which commits>
**What to NOT touch:** <any files I deliberately left for sibling>
**Coordination note:** <anything the next session needs to know>
```

The next session reads the latest update before doing anything. This is the equivalent of leaving a sticky note on the fridge.

---

## 7. Cost of stepping on toes (real examples from `saskia-app`)

- **2026-10-08 session** lost 4 of 6 mechanical refactors to silent `git checkout` by sibling. 30 min wasted.
- **2026-10-12 session** shipped migration 119 as a sibling-salvage (the other session had written the file but not committed). 15 min saved by reading the sibling-flush-note first.
- **Multi-commit collisions** on `pyproject.toml` (duplicate `per-file-ignores` keys) — would have shipped but ruff caught it. Always run `uv run ruff check .` after merge.

---

## 8. When to escalate to Iván

- Two sessions need to merge to `main` at the same time and there's a conflict.
- A sibling session appears stuck / has been silent for >24 hr with uncommitted WIP that you'd be stepping on.
- The worktree shows files `M` that no sibling claims (orphan dirty state from a crashed session).
- Any commit message / attribution question — don't rewrite history unilaterally.