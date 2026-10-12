# HERMES-ORIENTATION — first 5 minutes in `saskia-app`

**Audience:** A fresh Hermes desktop session (profile `ivan`) opening on `/opt/data/work/saskia-app`.
**Goal:** orient without writing anything. ~5 min probe sequence.

---

## Step 0 — confirm the worktree

```bash
pwd                                # must be /opt/data/work/saskia-app
git status -sb                     # branch + any sibling dirty files
git log --oneline -10              # last 10 commits; check who wrote them
git worktree list                  # shows sibling worktrees on this checkout
```

**Hard stops:**
- If `pwd` is `/opt/hermes` or `/opt/data/scratch/saskia-app` (the older git history), `cd /opt/data/work/saskia-app` first.
- If `git status -sb` shows files you didn't touch as `M`, **stop and read** `.hermes/sibling-flush-note.md` (if present) before doing anything.

---

## Step 1 — read the rules

In this order, ~5 min total:

1. **`AGENTS.md`** (root, ~25 KB) — at minimum the `## Personas`, `## Hard rules`, `## Anti-rules`, `## Tech stack`, and `## Decision framework` sections.
2. **`.hermes/HERMES-ORIENTATION.md`** (this file).
3. **`.hermes/KNOWN-BYPASSES.md`** — if doing code work.
4. **`.hermes/SIBLING-COORDINATION-NOTE.md`** — if `git status` showed any sibling dirty files.

---

## Step 2 — confirm the live state

```bash
grep CURRENT_SCHEMA_VERSION app/rms/config.py    # expect 119 (or higher after migration lands)
git rev-parse --abbrev-ref HEAD                  # confirm the branch
git log --since='24 hours ago' --oneline         # see what shipped today
```

**Cross-check before believing anything in AGENTS.md.** If a number there disagrees with the live state (e.g. "117 migrations" but `CURRENT_SCHEMA_VERSION = 119`), the live state wins. AGENTS.md drifts; the repo is the source of truth.

---

## Step 3 — if you'll write code

```bash
# Pre-flight: ensure the test suite still runs baseline-green
uv run pytest tests/test_smoke.py -x --no-header -q 2>&1 | tail -10
```

If baseline is red on a fresh branch off main: **stop and tell Iván**, don't paper over.

**Load the right skill(s):**

| If the work is about... | Load skill |
|---|---|
| General saskia work | `saskia-rms-development` (auto-loads on cwd match) |
| Sprint / visual audit / deploy / derived-intelligence | `saskia-rms-procedures` (companion) |
| Bug matching a Sentry trace or known pitfall | `saskia-rms-development-pitfalls` |
| Deploying to VPS | `saskia-rms-deploy-flow` |
| Sprint refactor or quick batch work | `saskia-rms-quick` |

---

## Step 4 — write a session log

Per AGENTS.md §"How to work a session", append a one-liner to `session_logs/YYYY-MM-DD.md` in the workspace (path: `/opt/data/profiles/ivan/cache/scratch/sazon_migration/session_logs/`). If the workspace is stale/missing, write to `.hermes/session_logs/YYYY-MM-DD.md` in the worktree instead — **do not create new directory trees in `/opt/data/`** without operator OK.

---

## Step 5 — done. Don't over-discover.

A fresh session wastes ~15 min when it tries to "fully understand the codebase" before doing anything. Don't. Do the task, log it, end the session. The next session will pick up where you left off.

---

## What I do NOT load by default (and why)

- `tests/_lib/*.py` (7 files, ~5 KB) — only relevant when writing tests
- `docs/operations/*` (50+ files) — load on demand per topic
- `app/rms/AGENTS.md` (6 KB) — module-specific rules, only relevant for `app/rms/` work
- The 9 prior session transcripts under `/opt/data/profiles/ivan/sessions/` — only when explicitly asked to "look at recent sessions"

If you find yourself loading 50+ KB of docs to start, you're over-discovering. Pick the smallest doc that answers the question.