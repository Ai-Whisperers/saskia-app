# Saskia/Sazón sessions audit — Oct 8, 2026

Scanned Hermes `state.db` for the last 7 days (cutoff Oct 1, 2026, 06:19 UTC).
71 user sessions touch the sazon/saskia keyword surface in that window;
8 are titled and operationally relevant. Below: what was actually worked on,
which repos / branches / worktrees were involved, and where the live work has
diverged so the next session can pick up cleanly.

---

## 1. Repos involved (ranked by session mention count)

Only one canonical code repo exists — everything else is a worktree, scratch
clone, or separate artifacts-repo reference.

| Repo | Where it lives | GitHub | Sessions touching it |
|---|---|---|---|
| **`Ai-Whisperers/sazon-app`** | `/opt/data/work/saskia-app` (canonical) | https://github.com/Ai-Whisperers/sazon-app | 8 titled SASKIA sessions + all 21 successful SASKIA ticket waves since SASKIA-201 |
| **`research-repos/saskia/`** (separate OPSEC-clean context repo) | referenced from AGENTS.md; lives outside `/opt/data/work/` | private | indirectly via the build brief, not coded |
| Workspace scratch clones | `/opt/data/profiles/ivan/scratch/saskia-app-work`, `saskia-app-merge`, `saskia-app-clean`, `saskia-app-saskia-204`, `saskia-app-phase3m1-wave1` | n/a | 6 of 8 titled sessions used one or more of these |
| Migration plan workspace | `/opt/data/profiles/ivan/cache/scratch/sazon_migration/` | n/a | all sessions reference `PLAN_INDEX.md`, `IDEATION_PLAN.md`, `MASTER_PLAN.md` |

There is **no** `saskia-rms` or `sazon-rms` standalone repo. The skill
catalog and your earlier sessions reference `saskia-rms*` as a *family of
skills* (`saskia-rms-development`, `saskia-rms-development-pitfalls`,
`saskia-rms-deploy-flow`, `saskia-rms-design`, `saskia-rms-quick`,
`saskia-app-auth-management`, `saskia-app-backend-patterns`, etc.), not a
separate code repo.

The frequent `/opt/data/profiles/ivan/scratch/saskia-app-work/...` path is
your long-lived Claude-Code worktree of `sazon-app` checked out at commit
`d9362c17` (HEAD of `main`-tracked work that's a few commits ahead of the
canonical `/opt/data/work/saskia-app`, which is currently in detached HEAD at
`f92fd589`).

---

## 2. Branches touched (live state)

Current state of `/opt/data/work/saskia-app`:

- HEAD detached at `f92fd589` — the wave-1 ruff format commit
- `main` (origin/main) at `f92fd589` — same commit; both the canonical clone
  and origin's main are aligned on this sha
- **`feat/workbook-seed-reconciliation`** at `d6e11459` — the most active
  non-main branch, working on AI image-gen pipeline + HEREBUS workbook
  reconciliation for La Vaquita Feliz. **Not merged to main** yet (latest
  feat/* commits: image pipeline, product images, recipe reconciliation)
- `feature/station-shell`, `fix/saskia-317-parallel-isolation`,
  `fix/saskia-320-station-flash-asserts` — present on origin, untouched in
  the last 7 days

Worktree `saskia-app-work` is at `d9362c17` which is **11 commits ahead** of
the canonical `/opt/data/work/saskia-app`'s HEAD — meaning your sibling
sessions in Claude Code / parallel worktrees have shipped PRs (#76 ruff
import-order fix, P44 dead-file removal, migration 076-082 atomic_ddl_block
conversion, the backfill-080 inline-ts fix, etc.) that **haven't been pulled
into the canonical checkout**.

`WHAT_NEXT.md`-style plans in `.hermes/plans/` (uncommitted) include:
- `2026-10-08_010000-WHAT_NEXT-execute.md` (3.0K)
- `2026-10-08_034500-SAZON-UI-MIGRATION-FROM-COMPETITORS.md` (21.9K — big)
- `2026-10-07_225617-SASKIA-309-310-final-phases.md` (5.7K)

---

## 3. SASKIA tickets worked in the last week (from git log on main)

Pulled directly from `git log` on the canonical clone:

| Commit | Ticket | What shipped |
|---|---|---|
| `f92fd589` | (ruff format) | format 8 SASKIA-3XX files + extend-exclude `.hermes/plans` (lint gate) |
| `388cbe3a` | D3 | `m.gs`/`m.gs_full` currency formatter in `eod_print` + `receta_detalle` |
| `b1534b8f` | **SASKIA-308** | settings + EOD + auditoria + ops regression locks (Phase 7) |
| `e08dcda2` | **SASKIA-302** | login + inicio + prod-manana (Phase 1) |
| `0fd22438` | **SASKIA-301** | currency, register, severity labels standardization (Phase 0) |
| `cfea5dfe` | 209/210 one-pagers | migration rollback doc + Supabase RLS/multitenant scoping |
| `ede316a3` | **SASKIA-208** | Poisson weekday restocking forecast |
| `2c25639d` | Sprint 2.1 | settings test fixes; Sprint 2.1 file-invariants locked |
| `a599fd81` | **SASKIA-207** | `stock_ledger.apply_stock_delta` + `qty_to_stock_unit` helper |
| `c4dbb9e6` | **SASKIA-206** | ShoppingListItem.unit_price_snapshot_gs (migration 113) |

(Also from memory: **SASKIA-205** shipped earlier as `741a149a` —
shopping-list/wishlist mark-purchased stock landings. **SASKIA-209** shipped
as `dc26df1f` — `sazon rollback` command. **SASKIA-210** is the
*Supabase/multitenant scoping decision* — DEFERRED per your 2026-10-07
decision.)

The phases 0/1/7 of the copy/UX hardening program were closed in PR #59
(commit `430b7a4f`). Phases 8/9/10 (SASKIA-309/310) are planned but not
shipped.

---

## 4. The 8 titled sessions (chronological)

| # | Date | session_id | mc/tt* | What it did | Outcome |
|---|---|---|---|---|---|
| 1 | Oct 02 09:13 | `20261002_131749_*`  | 492/241 | "Verify recent sessions and deployment status" | Healthcheck + status snapshot |
| 2 | Oct 02 10:17 | `20261002_131723_*`  | 279/135 | "Analyze website and backend for frontend tasks" | Frontend task discovery |
| 3 | Oct 03 19:18 | `20261003_231749_77f6a4` | 472/233 | "Analyze Saskia production tracking system" | Production-flow audit; referenced `saskia-vps.paragu-ai.com/produccion` heavily; opened 20+ improvement tickets (`saskia-page-flow-completion`, `saskia-combo`, `saskia-rms-quick`) |
| 4 | Oct 03 14:22 | `20261003_182233_*`  | 702/346 | "Analyze improvements by page" | Big page-by-page UX review — produced the 290+ issue UX fix list (`cb2f761d` in git log) |
| 5 | Oct 05 09:29 | `20261005_132958_66fb52` | 300/144 | "Analyze Saskia app repo local work" | Repo orientation; **discovered the missing `Worktree Policy` doc**; everything eventually merged cleanly |
| 6 | Oct 05 10:01 | `20261005_140148_9273fc` | 208/100 | "Analyze Saskia app production definitions" | Production-flow deep dive; produced `Sprint 2.1 SPEC`, scoped `feat/phase-3-ci-cleanup` branch |
| 7 | Oct 05 11:00 | `20261005_150026_747a68` | 134/66  | "Analyze Saskia app repository documentation" | README/AGENTS review; identified 50+ doc gaps; result = `2026-10-04-comprehensive-documentation-refresh` skill + 7 doc rewrites |
| 8 | Oct 05 17:13 | `20261005_211356_c7aa80` | 526/256 | "Analyze Saskia app sessions and pass credentials" | **The credentials-handoff session.** Result: `AIW_SASKIA_DB_PATH` env var fix (skills `saskia-rms-db-path-mismatch`); VPS login recovery; `saskia-vps.paragu-ai.com` brought back up after auth blocker |
| 9 | Oct 07 17:19 | `20261007_211929_138682` | 302/148 | "Analyze saskia app repo for hardcoded values" | Hardcoded-value audit (the one that fed SASKIA-301/302/308 + `SAZON_PREFLIGHT_MAX_DISCOUNT_PCT` + `AIW_SASKIA_*` env-var extraction) |

*`mc/tt` = message count / tool-call count.

Plus the current one (Oct 8 19:46 — yours) and one earlier-of-record:
Oct 1 sessions (`20261001_201522`, `20261001_164134`) that produced the
deployment work for `sazon-vps.paragu-ai.com` going live.

---

## 5. Branches with active work that the next session should know about

- **`feat/phase-3-ci-cleanup`** (sessions 6, 7) — anti-rules grep enforcement in CI, ruff cleanup. The 13-of-20 anti-rule grep gates are already merged; full 20 likely covers SASKIA-301/302/308 follow-ups.
- **`feat/workbook-seed-reconciliation`** (canonical saskia-app) — image-gen pipeline + HEREBUS workbook seed reconcile. **10 commits ahead of main**, untouched in title-sessions but live.
- **`feat/sazon-rebrand-seed`** — referenced in session 7 only; rebrand seed pipeline.
- **`feat/produccion-v3-ux-overhaul`** / **`feat/produccion-p0-p1-overhaul`** — surfaced in production-flow sessions, partly merged.
- **`fix/ble001-defensive-excepts`** — defensive exception handling.
- **`fix/saskia-319-import-order-and-format`** — already merged via PR #76 + #77.

---

## 6. Operational repo + VPS state

- **Live app URL:** https://sazon-vps.paragu-ai.com (not the obsolete Render URL — Render is DEPRECATED per `docs/operations/2026-09-24-deployment.md`).
- **VPS infra:** ServaRica Docker Swarm + Traefik + Cloudflare DNS-01. Active stack at `/opt/data/work/saskia-app/docker-stack.yml`.
- **Two deployments verified live:** `AIW_SASKIA_*` env vars now drive runtime config (PROD=110). Last known deploy commit: `e146aea` (white-on-white audit fix).
- **DB path env var:** `AIW_RMS_DB_PATH` (skills `saskia-rms-db-path-mismatch`). Do NOT hardcode `/tmp/...` or `/opt/...` — VPS uses `/home/sazon/app.db`.
- **Cron fleet:** `saskia-anclas-mensual`, `STROBE MENSUAL DE ANCLAS SASKIA`, `aiw-research-tracker-6h` — all scheduled, last_status OK in last 7d.

---

## 7. What to act on (priority-ordered)

1. **Reconcile `/opt/data/work/saskia-app` (detached HEAD `f92fd589`) with `saskia-app-work` (HEAD `d9362c17`, 11 ahead).** The canonical clone hasn't been `git pull`ed since P44/P45/SP1.1 — sibling sessions shipped commits you don't see locally. Quick `git checkout main && git pull --ff-only` from canonical, or just `cd scratch/saskia-app-work` and work there.
2. **Decide on `feat/workbook-seed-reconciliation`.** It's been sitting at 10 commits since Oct 7 — La Vaquita Feliz image pipeline is functional but unmerged. The defer-Saskia-per-clients decision (memory: SASKIA-210) means this branch should be checked against whether La Vaquita Holandesa's operator needs it now.
3. **Uncommitted `.hermes/plans/` 4 files in canonical clone** (operator docs refresh, WHAT_NEXT, SASKIA-309/310 plan, SAZON-UI-MIGRATION-FROM-COMPETITORS). These are plans only — not staged. Either commit, link from WHAT_NEXT.md, or clean.
4. **Memory says SASKIA-209 (`sazon rollback`) is shipped + SASKIA-210 is the deferred multitenant decision** — so when SASKIA-309/310 plan is open, confirm it doesn't reopen 210.
5. **No urgent VPS action.** Health, backup, auth, observability tier-8 all green as of 2026-10-07 (memory).

---

## 8. What's NOT broken (skip re-investigating)

- VPS deployment, auth, healthz, backup, Sentry, Resend, CI ruff/pytest gates, CHANGELOG discipline, anti-rule grep gates, money-math property tests, sale→StockMovement delegation (locked by 3 tests in `tests/test_sale_create_writes_stock_movement.py`).
- Migrations 0→114 atomic and forward-only; no gaps.
- `sazon rollback` ships and the rollback log persists in `app_meta`.
- Sprint 2.1 (settings unification) is green — `settings.py` and `settings_original.py` are deleted.

---

## Artifact

This file: `/opt/data/profiles/ivan/cache/scratch/sazon_sessions_audit_20261008.md`
