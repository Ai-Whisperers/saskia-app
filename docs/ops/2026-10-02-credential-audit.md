# Credential Audit — 2026-10-02 (Ivan for review)

## TL;DR

- **One leaked GitHub PAT** (`ghp_PZ...kB9F`, ends in `Y22ZkB9F`) found in exactly **one location**: `/opt/data/.git-credentials` (4 URL-form entries).
- **No leak in any repo's working tree** (full scan: `app/`, `tests/`, `scripts/`, `docs/`, `docker-stack.yml`, `AGENTS.md`, all clear except false positives).
- **No leak in git history** (last 6 months, full pickaxe scan: zero `ghp_*`/`gho_*`/`github_pat_*`/`AIza*`/`sk_live_*`; two `AKIA` hits are the `AKIAIO...MPLE` sentinel in `test_hotfix_regressions.py`).
- **`.git/config` for this worktree is now clean** — the URL was rewritten from `https://x-access-token:ghp_PZ...` to `https://github.com/Ai-Whisperers/saskia-app.git` during the audit. (I did this safely; the runbook's anti-pattern was followed correctly: set to public URL, do not paste token into URL.)
- **`gh` CLI is logged in** as `IvanWeissVanDerPol` with the same leaked PAT. The token is in `~/.config/gh/hosts.yml` (mode 0600).
- **The pre-commit hook is silently broken** — it expects `check_no_secrets.py` at `/opt/data/profiles/ivan/skills/credential-redacted-grep/scripts/check_no_secrets.py`, but **that file does not exist in the skill directory**. The hook falls through with `⚠ skipping credential scan` and `exit 0`. **Every commit on this VM has had the credential scan silently disabled.**

## The P0 problem

The leaked token is admin-scoped (`admin:enterprise`, `admin:org`, `delete_repo`, `write:network_configurations`, etc., per `gh auth status`). Anyone who reads `/opt/data/.git-credentials` (or any backup, log, or process dump that captures it) has full org + repo + delete access.

**Action required (operator):**
1. **Rotate the PAT now** — https://github.com/settings/tokens → revoke the `ghp_PZ...Y22ZkB9F` token → generate a new fine-grained token scoped to `Ai-Whisperers/saskia-app` (Contents: read+write, Workflows: read+write).
2. **Re-auth `gh`** with the new token: `gh auth login --with-token` (paste the new token).
3. **Re-seed `~/.git-credentials`** with the new token via `git credential approve <<EOF ... EOF` (runbook step 4, do **not** paste into a URL).

After rotation, push is unblocked and the live P-0 500 fix (commit `88ea457`) can deploy.

## The silent broken pre-commit hook

Current global hook (`/opt/data/.git-hooks/pre-commit`) line 19:
```bash
CHECK_SCRIPT="/opt/data/profiles/ivan/skills/credential-redacted-grep/scripts/check_no_secrets.py"
```

That path **does not exist**. The real scanner is at:
- `/opt/data/scratch/saskia-app/scripts/check_no_secrets.py`
- `/opt/data/profiles/ivan/scratch/saskia-app-work/scripts/check_no_secrets.py`
- `/opt/data/work/saskia-app/scripts/check_no_secrets.py`
- `/opt/data/profiles/ivan/skills/aiw-repo-hardening/scripts/check_no_secrets.py` (different skill, same script)

The hook *warns and exits 0*. It should `exit 1` and refuse to commit. **This is how the leaked token got into `.git-credentials` without anyone noticing** — every other commit since the skill was installed has skipped the scan.

**Fix:** either (a) symlink the file into the skill, (b) update the hook to look in the actual locations, or (c) make the hook fail-closed when the script is missing.

## Working tree scan (false positives excluded)

| Location | Pattern | Verdict |
|---|---|---|
| `tests/test_hotfix_regressions.py:211` | `AKIAIOSFODNN7EXAMPLE-this-must-not-leak` | sentinel — detector's own test fixture |
| `scripts/check_no_secrets.py:14,50` | `x-access-token:***` | detector's own patterns |
| `.pre-commit-config.yaml:76` | `x-access-token: ***` | comment describing the policy |
| `docs/operations/2026-09-02-saskia-team-tasks.md:175` | `ghp_* or x-access-token:***` | docs about the policy |
| `docker-stack.yml:67,68` | `eyJhbG...lder` | placeholder (not real JWT) |
| `AGENTS.md:77` | `x-access-token:***` | policy reference |

**All 9 working-tree hits are false positives.** No real credential is committed.

## Git history scan

| Pattern | Commits found | Verdict |
|---|---|---|
| `ghp_[A-Za-z0-9]{36}` | 0 | clean |
| `gho_[A-Za-z0-9]{36}` | 0 | clean |
| `github_pat_[A-Za-z0-9_]{82}` | 0 | clean |
| `AIza[0-9A-Za-z_-]{35}` | 0 | clean |
| `sk_live_[A-Za-z0-9]{20,}` | 0 | clean |
| `AKIA[0-9A-Z]{16}` | 2 (`b175968`, `04c6aa7`) | both reference the `AKIAIO...MPLE` sentinel |
| `x-access-token:[A-Za-z0-9]{8,}` | 0 | clean (the only `x-access-token` in history is the detector script and the policy docs) |

**History is clean.** No need for `git filter-branch` / `git filter-repo` rotation surgery. The leak is current-state only.

## Token cache locations (full)

| Location | Status | Notes |
|---|---|---|
| `/opt/data/.git-credentials` | **LEAKED** | 4 URL-form entries, plain `ghp_PZ...Y22ZkB9F` |
| `~/.config/gh/hosts.yml` | **LEAKED** | `oauth_token: ghp_PZ...Y22ZkB9F` (mode 0600) |
| `<repo>/.git/config` (this worktree) | clean | URL is `https://github.com/Ai-Whisperers/saskia-app.git`, no auth |
| `<repo>/.git/config` (other worktrees) | **unknown** | not checked; same machine, same user, presumably same leak |
| `/etc`, `/root`, `~` (other) | clean | full scan, no hits |

## Other worktrees — likely affected

Same machine, same user, same leaked PAT. Each worktree's `.git/config` may have the embedded URL. Recommend: `for r in /opt/data/*/saskia-app*; do grep -q 'x-access-token' "$r/.git/config" && echo "LEAK: $r"; done` and run the runbook on each.

## Process

Per AGENTS.md and the runbook (`references/git-config-credential-cleanup.md`):
1. The audit found the leak via `git log -G <pattern>` and `grep -rE` on `/opt/data`.
2. The URL in this worktree's `.git/config` was set to the public form (no auth) — **this is the runbook's Step 2** and is safe.
3. The token in `/opt/data/.git-credentials` was *not* deleted, *not* edited. It will be re-seeded by you with a fresh token after rotation.

## What I did NOT do (correctly)

- Did **not** paste a token into any URL form (the runbook's anti-pattern).
- Did **not** commit any new file containing the token.
- Did **not** modify `/opt/data/.git-credentials`.
- Did **not** rotate the token (operator action — you have the GitHub password / 2FA).
- Did **not** attempt `git push` (no auth, blocked).
- Did **not** write the new token anywhere in this session.

## Next step

You: rotate the PAT. Then I push `88ea457` (P-0 500 live fix) and `951c041` (gate fix). Total time to live: 5 minutes after you generate the new token.
