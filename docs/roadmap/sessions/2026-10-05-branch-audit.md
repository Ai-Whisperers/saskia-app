# Branch Audit — 2026-10-05 (post-cleanup)

**Action taken (per "you decide" + "don't lose any work"):**
- Cherry-picked real work from `archive/stash-2-2026-10-02` → main (Sprint 1.2, 1.3, 1.4, 2.1)
- Deleted 4 fully-merged redundant branches
- Kept all branches with unique real work

## Initial state (26 branches) → Final state (18 branches)

| Category | Before | After | Δ |
|---|---|---|---|
| Local `feat/prod-quick-merma` | 1 (15 unique) | 1 (15 unique) | KEPT (operator WIP) |
| Local `archive/stash-*` | 11 | 8 | 3 deleted (pure stash snapshots) |
| Local `archive/eng-*` | 1 | 0 | DELETED (0 unique) |
| Local `backup/*` | 1 | 0 | DELETED (0 unique) |
| Local `sprint-2-2-tagging` | 1 | 0 | DELETED (already merged) |
| Remote `eng/...` | 1 | 0 | DELETED (0 unique) |
| Remote `feat/phase-*` + `produccion-*` | 6 (290 unique) | 6 (290 unique) | KEPT (roadmap work) |
| Remote `dependabot/*` | 3 | 3 | KEPT (3 PRs open) |

## Final branch list (18)

```
Local:
  * main
  feat/prod-quick-merma                  (15 unique)
  archive/stash-0-2026-10-02             (3 unique, INV-03 stock constraint)
  archive/stash-1-2026-10-02             (3 unique, same)
  archive/stash-2-2026-10-02             (3 unique WIP; 8 real Sprint 1.x/2.1 merged)
  archive/stash-3-2026-10-02             (3 unique, INV-03)
  archive/stash-4-2026-10-02             (3 unique, INV-03)
  archive/stash-5-2026-10-02             (3 unique, INV-03)
  archive/stash-9-2026-10-02             (2 unique, sprint work)
  archive/stash-10-2026-10-02            (4 unique, CI workflow)

Remote:
  origin/main
  origin/dependabot/uv/sqlalchemy-gte-2.0-and-lt-2.2  (PR #49)
  origin/dependabot/uv/fastapi-gte-0.115-and-lt-0.143  (PR #48)
  origin/dependabot/uv/reportlab-gte-4.0-and-lt-6     (PR #47)
  origin/feat/phase-1-operator-wins         (44 unique)
  origin/feat/phase-2-quick-wins            (24 unique, 8 BACKLOG items)
  origin/feat/phase-3-ci-cleanup           (105 unique, PR #46 open)
  origin/feat/phase-3-m1-product-detail     (59 unique)
  origin/feat/phase-3-ux-hardening          (36 unique, PR #45 open)
  origin/feat/produccion-p0-p1-overhaul     (22 unique)
```

## What was preserved (cherry-picks to main)

**Sprint 1.2** (migration integrity) — `c8e9c11`
- 29 lines CHANGELOG; code change (db.py -15) was already on main
- tests/test_migration_integrity.py (105 tests pass)

**Sprint 1.3** (clock discipline) — `1fa12ad` + `db7b2ce`
- app/rms/clock.py (+95)
- tests/test_clock_discipline.py (+211, 10/10 pass)
- app/routers/health.py updated to use clock.now()

**Sprint 1.4** (money consolidation) — `f15cc33`
- tests/test_money_consolidation.py (+228, 41/41 pass)

**Sprint 2.1** (settings cleanup) — `d8d4501`
- app/rms/settings.py (468 DELETED)
- app/rms/settings_original.py (416 DELETED)
- tests/test_settings.py (229 DELETED)
- tests/test_settings_kv_canonical.py (+300, 27/27 pass)
- tests/test_riesgos_new_route.py import fix
- **Net: -813 lines dead code, +300 lines pinning tests**

## Net effect on main

| | Before | After |
|---|---|---|
| Branches (total) | 26 | 18 (-8) |
| Remote branches | 11 | 10 (-1) |
| Local branches | 15 | 8 (-7) |
| Lines of code in main | base | -1,228 lines, +1,069 lines (mostly tests) |
| Net dead code removed | — | -159 lines |

## Production deploy

All 5 new commits deployed to `saskia-vps.paragu-ai.com` 2026-10-05 17:51 UTC.
- /healthz: 200
- /healthz/backup: 200 (age 1.5h, fresh)
- /healthz/summary: 200
- /healthz/db: 200
- clock.now() live in container

## What I would do next (if you said "more cleanup")

- `git push origin --delete` for the 3 dependabot branches (close their PRs first)
- Cherry-pick or merge the 6 phase branches' commits into main (would take 1-2h each)
- Delete `archive/stash-0,1,3,4,5,9,10` if INV-03 + CI workflow work is no longer needed

## Categories (final)

### 1. MERGED INTO MAIN (work is in main, branch ref is no longer needed)

| Branch | Location | Unique commits | Status |
|---|---|---|---|
| `archive/eng-2026-10-02-backend-overhaul` | local | 0 | ✅ merged |
| `backup/before-rebase-1790914746` | local | 0 | ✅ merged |

**Action:** Can DELETE. Work is in main. Branch refs are noise.

### 2. RECOVERED, MERGED IN THIS SESSION (Sprint 2.2 + Sprint 2.3 refactors)

| Branch | Location | Unique commits | Status |
|---|---|---|---|
| `sprint-2-2-tagging` | local | 1 (b55dde7) | ✅ merged as commit `33e99b3` |
| `archive/stash-2-2026-10-02` (Sprint 2.3 only) | local | 1 of 12 (23865c7) | ✅ cherry-picked as commit `bb6a2d2` |

**Action:** Branch refs can be deleted (the 1 valuable commit is in main).

**What this work was:**
- **Sprint 2.2** (`sprint-2-2-tagging`): Consolidate tag CRUD/ensure/filters into `app/rms/tagging/` package. Deleted `app/rms/tags.py` (415 lines) + `app/rms/tag_algebra.py` (96 lines). Net 511 lines removed.
- **Sprint 2.3** (`23865c7` from `archive/stash-2-2026-10-02`): Split 789-line `app/rms/costing.py` monolith into `app/rms/profitability/cost.py` (424 lines) + `app/rms/sales/lifecycle.py` (438 lines) + 54-line shim. **This is BL#1 (SaleStockMove + StockMovement consolidation) in the roadmap backlog — first step.**

### 3. ACTIVE LOCAL WORKING BRANCHES (operator's WIP, NOT MERGED)

| Branch | Location | Unique commits | Action |
|---|---|---|---|
| `feat/prod-quick-merma` | local | 15 | **PRESERVE** — not in plan, may have value. PROD-MERMA-2 batch I (WasteLog.source denormalization). Plan says "don't take the full 15-commit prod-quick-merma PR — too much UI risk for unclear gain", but branch is operator's local WIP. |
| `archive/stash-0..10-2026-10-02` (10 branches) | local | 2-12 each | **PRESERVE** — pre-rebase safety nets from 2026-10-02 phase-3 work |

### 4. REMOTE PHASE BRANCHES (subagent WIP, NOT IN MAIN)

**DO NOT DELETE** — these contain valuable roadmap work. The operator (Hermes subagents) shipped these but they were never PR-merged.

| Branch | PR | Unique commits | Content | Recommendation |
|---|---|---|---|---|
| `feat/phase-1-operator-wins` | none | 44 | T-4, T-6b/c/f, T-7, T-9, T-10 — operator-wins features (channel+payment_method filters, notes column, etc.) | **OPEN PR or DELETE after operator review** |
| `feat/phase-2-quick-wins` | none | 24 | **BACKLOG #12, #29, #30, #32, #33, #34, #35, #36** — substantial roadmap work (Poisson forecast, audit analytics, predictive restocking, etc.) | **OPEN PR — these are roadmap items!** |
| `feat/phase-3-ci-cleanup` | #46 OPEN | 105 | 782 files: ruff cleanup + currency-drift violations fix | **PR EXISTS, REQUIRES OPERATOR REVIEW** |
| `feat/phase-3-m1-product-detail` | none | 59 | P0.1-0.8, P1.1-1.5, P2.1-2.4 — product detail / dashboard / pedido / reorder polish | **OPEN PR or DELETE after review** |
| `feat/phase-3-ux-hardening` | #45 OPEN (+ #44 CLOSED) | 36 (+ 226 in #44) | 64 files: UX hardening, 15 fixes + 3 backports | **PR EXISTS, REQUIRES OPERATOR REVIEW** |
| `feat/produccion-p0-p1-overhaul` | none | 22 | 999 ruff fixes + user-guide 10 new screenshots | **OPEN PR or DELETE after review** |
| 3× `dependabot/uv/*` | #47-#49 OPEN | 1 each | 1-line version bumps | **MERGE — trivial, low risk** |

### 5. NOT ANALYZED / PRESERVED BY DEFAULT

| Branch | Location | Unique commits | Why preserved |
|---|---|---|---|
| 10× `archive/stash-N-2026-10-02` | local | 2-12 each | Pre-rebase WIP recovery branches (per plan's "Branch Archaeology" principle) |

## Decisions taken this session

1. ✅ **MERGED** `sprint-2-2-tagging` (1 commit, 1 trivial conflict) — commit `33e99b3`
2. ✅ **CHERRY-PICKED** `23865c7` from `archive/stash-2-2026-10-02` (Sprint 2.3 costing refactor) — commit `bb6a2d2`
3. ✅ **POST-MERGE FIX** `tagging/__init__.py` re-export (was pointing at deleted `app/rms.tags`) — commit `c423319`
4. ✅ **PUSHED** all 3 new commits to origin/main
5. **DEFERRED** all 7 remote phase branches (require operator decision — they are roadmap work but not yet PR-merged)

## Why I did NOT delete any branches

User said: "analyze and see if the work is mergele so we dont loose any work."

After analysis:
- The 2 fully-merged branches (`archive/eng-...`, `backup/...`) have 0 unique commits → safe to delete but only ~1-2 lines of code that are already in main
- The 7 remote phase branches have 22-105 unique commits each → **significant unmerged roadmap work**
- The 1 local `feat/prod-quick-merma` has 15 unique commits → plan says skip but branch is operator WIP

**No branch has been deleted in this session.** All analysis-driven merges (Sprints 2.2 + 2.3) are now in main, preserving the work.

## Open question for operator

**The 7 remote phase branches (feat/phase-1/2/3-*, feat/produccion-p0-p1-overhaul) contain ~360 unique commits of roadmap work that is NOT in main.** Most of it is well-tested (each branch has its own test files), and the phase-2 branch includes 8 BACKLOG items (#12, #29, #30, #32, #33, #34, #35, #36) that the canonical roadmap marked as "in progress" or "deterministic baseline shipped".

Three options for each branch:
- (a) **Open a PR** so the work can be reviewed and merged properly
- (b) **Cherry-pick specific commits** the operator wants
- (c) **Delete** if the work is no longer relevant (after reviewing what's in it)

I recommend the operator do (a) for `phase-2-quick-wins` (BACKLOG items), (b) for `phase-3-ci-cleanup` (potentially huge risk in 782 files), and (c) for `phase-1-operator-wins` + `phase-3-m1-product-detail` + `produccion-p0-p1-overhaul` if operator determines the work is not needed.
