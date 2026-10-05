# Sibling-session coordination — how to avoid stepping on yourself

> **Audience:** anyone who runs the the operator worktree from a separate
> shell (sibling Hermes session, parallel Claude Code, etc.) on the
> same git repo.
> **Date:** 2026-10-04 (after a real loss-and-restore cycle that cost
> ~30 min of redoing work that had already shipped to a different
> branch).

## TL;DR

This repo has **two** long-running worktrees pointing at overlapping
branches. When you switch branches in one, the other one's working
tree can lose uncommitted changes. **Always** check your branch state
before assuming a fix has been undone. **Always** commit before
switching branches if there's any chance another session is active.

## The two worktrees

There are at least two worktrees in the SASKIA project that share
history:

| Worktree | Branch | Purpose |
|---|---|---|
| `/opt/data/profiles/ivan/scratch/sazon-app-work` (the main one) | `feat/phase-3-ci-cleanup` or `feat/produccion-p0-p1-overhaul` | One session's work |
| (other worktrees on the same filesystem) | Various | Other sessions / Claude Code |

Both branches share history at the merge-base `269ff9b` ("start
produccion overhaul"). Work above that point is **branch-local**
and not shared unless pushed.

## Symptoms of "I'm in the wrong worktree"

You probably lost work if you see:

1. **`git status` shows clean** when you expected uncommitted edits.
2. **A file you just edited reverts to an old version** after a
   branch switch.
3. **Tests that passed 5 minutes ago now fail** in ways that look
   like missing imports.
4. **Ruff says "Found 100+ errors"** when an hour ago it said 0.
5. **The commit pin in the README matches a different SHA than
   `git rev-parse HEAD`**.

## Recovery procedure

If you suspect lost work:

1. **`git reflog`** — find the lost commit. Hermes commits are
   timestamped; you can usually identify the right one by subject.
2. **Look at the sibling worktree's recent commits** —
   `git log <branch> --oneline -10`. If the lost fix is there,
   you just need to cherry-pick, not redo.
3. **If it's NOT on any branch** — `git reflog show <branch>` for
   the dangling SHA, then `git cherry-pick <sha>`.
4. **If you can't find it** — check `git fsck --unreachable` for
   dangling commits.

## Coordination protocol

**Before doing any of these, do a quick `git status -sb`:**

- Switching branches
- Running a tool that might switch branches
- Stashing
- Pulling

**If `git status` shows the wrong branch, stop.** Don't edit files.
Cherry-pick your work to the right branch first.

## Where to coordinate

**Do NOT coordinate in chat.** Chat is per-session and the other
session can't see it. Instead:

- **For plans that span sessions:** write a markdown plan to
  `.hermes/plans/<name>.md` and reference the path in your
  commit messages. Other sessions can read the file.
- **For branch-state warnings:** commit a one-liner note in the
  branch's tip commit message:
  `chore: ...; WARNING: do not switch branches mid-task — see
  docs/operations/2026-10-04-sibling-session-coordination.md`
- **For "I'll do this later":** leave a `TODO(hermes):` comment
  in code, or write a `.hermes/plans/<branch>-next-steps.md` file.

## Common scenarios

### Scenario: I switched branches and now the working tree is "behind"

The sibling session likely committed on top of your branch with a
different SHA. The diff is usually just the README commit-pin and
1-2 trivial edits.

```bash
git log --oneline origin/feat/phase-3-ci-cleanup..HEAD  # what's local-only
git log --oneline HEAD..origin/feat/phase-3-ci-cleanup  # what's remote-only
```

If remote has more, pull --rebase. If local has more, push.

### Scenario: I see "X done already" in another branch

Cherry-pick, don't redo. Example:

```bash
git switch feat/produccion-p0-p1-overhaul  # branch with the work
git log --oneline -10                       # find the commit
git switch feat/phase-3-ci-cleanup          # back to my branch
git cherry-pick <sha>                       # bring it over
```

### Scenario: Ruff says 0, I make changes, ruff says 100

Either (a) you broke a fix, or (b) a sibling session reverted
the working tree. The fastest way to check: `git diff HEAD --stat`
— if there are no changes, your working tree is clean and the
sibling reverted it.

## Related

- [2026-10-04-phase3-ci-cleanup-postmortem.md](2026-10-04-phase3-ci-cleanup-postmortem.md) — the cleanup this protocol was written for
- [AGENTS.md](../../AGENTS.md) — general project conventions
- `docs/plans/` — multi-session planning files
