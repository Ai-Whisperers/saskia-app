# ⚠️ This repository has moved

**The `Ai-Whisperers/saskia-app` repository is archived and no longer maintained.**

The project continues at:

> **[`Ai-Whisperers/sazon-restaurant-management-system`](https://github.com/Ai-Whisperers/sazon-restaurant-management-system)** (canonical, private)

This URL is what `https://saskia-vps.paragu-ai.com` deploys from (Docker Swarm / Cloudflare / `sazon-restaurant-management-system.git`). **Any new work — issues, branches, PRs, commits, releases — must be made there.**

## Why two repos existed

In August 2026 the La Vaquita Feliz (Saskia's bakery) RMS codebase was split out of `Ai-Whisperers/saskia` into this public repo. In October 2026 (`SASKIA-220` plan) a parallel private repo `Ai-Whisperers/sazon-restaurant-management-system` was created, growing the multi-tenant direction (URL-based routing, per-tenant Supabase, seasonal catalog, HEREBUS seeder). The two repos diverged for ~36 hours before this archive.

On **2026-10-13**, a consolidation pass cherry-picked 40 origin-only commits (the S1–S5 robustness campaign) onto `sazon-restaurant-management-system/main`, fast-forwarded `saskia-app/main` to match, and re-tagged `sazon-restaurant-management-system` as the canonical. The live VPS at `https://saskia-vps.paragu-ai.com` already deploys from there.

This file is the **last write** to this repo. After it merges, the repo will be set to **archived (read-only)** on GitHub.

## Where things live now

| Concern | URL |
|---|---|
| Source code (canonical) | https://github.com/Ai-Whisperers/sazon-restaurant-management-system |
| Live deployment | https://saskia-vps.paragu-ai.com |
| Staging deployment | https://saskia-test.paragu-ai.com |
| Dev deployment | https://saskia-dev.paragu-ai.com |
| Issue tracker | (move issues here on request) |

## For local clones

```bash
# Switch your local checkout to track the canonical remote:
cd /path/to/saskia-app
git remote set-url origin git@github.com:Ai-Whisperers/sazon-restaurant-management-system.git
git fetch origin main
git reset --hard origin/main   # deploy worktree only — main worktrees should `git pull --rebase`
```

## Done, but not archived yet

The archive-flag flip on the GitHub settings page is a manual operator step (requires admin auth). It is queued in `docs/operations/2026-10-13-repo-consolidation.md` under "Step 6 — Archive `Ai-Whisperers/saskia-app`".
