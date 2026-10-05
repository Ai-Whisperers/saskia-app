# PR #46 Deep Analysis — 2026-10-05

**Branch:** `feat/phase-3-ci-cleanup`
**PR:** #46 (open) — 105 commits, +30,291/-12,782 lines, 782 files
**Goal:** "Mass-fix the pre-existing 1910 ruff errors and 12 currency-drift violations"

## Reality vs. stated goal

The PR's stated goal is **lint cleanup** but it bundles 4 distinct kinds of work:

### Bucket A — Mechanical lint fixes (the stated goal)
- Ruff auto-fixes (999 safe + 146 unsafe)
- DTZ fixes (159 date.now() / utcnow() rewrites)
- ANN fixes (78 type annotations)
- PERF401 (list comprehensions, 2 cases)
- E701/E702 (multi-statement splits)
- E741 (rename `l` → `line`)
- F811 (12 redefinitions)
- B904 (10 `raise from err` cases)
- F401/F841/S110/RUF100/RUF043 (noqa for defensive defaults)
- Ruff config: relax _smoke/, scripts/, migrations/, tests
- 2 small bug fixes in migration 3 + migration 31/32

**Scope:** Mechanical, low-risk, ~88% reduction in ruff errors (1910 → 218).

### Bucket B — Real features folded in (NOT stated in PR title)
The branch grew to include 5 production features:

1. **T-2026-10-04 (Tier 5-K): 2-cook edit detection** + migration 099 (`production_completion.updated_at`)
2. **T-2026-10-04 (B.6): HACCP freezer temperature log** + migration 100 (`freezer_temperature_log`) — Paraguay MSPBS compliance, prevents 200-500k Gs/año fine
3. **T-2026-10-05 (B.3): masa madre fermentation** + migration 101 (`recipe.fermentation_minutes`)
4. **T-2026-10-04 (P0:D.2-D.4): produccion print + worksheet + batch-size awareness**
5. **/reportes/demand route** (B-tier work)

**Models added:** `FreezerTemperatureLog`, `ProductionClosedDay` (on the branch; my 098 on main is the same).

### Bucket C — Smoke test pre-provision workaround
- `scripts/smoke_test_deploy_shape.py` — Base.metadata.create_all() + parse head version from MIGRATIONS dict + seed `app_meta.schema_version` to head
- Tactical workaround for SQLite-first migrations on Postgres
- Strategic fix (dialect-aware migration rewrite) is 4-day project, scoped in `docs/operations/2026-10-04-migration-cross-dialect-rewrite.md`

### Bucket D — Docs (3 commits, 5 files)
- `2026-10-04-phase3-ci-cleanup-postmortem.md`
- `2026-10-04-sibling-session-coordination.md`
- `2026-10-04-architecture-overview.md`
- 10 new screenshots in `docs/user-guide/screenshots/`
- Sections 17-20 of user-guide (lista-compras, suscripciones, analisis, kpis-mensuales)

## Conflicts with main (24+)

My work on main since branch fork touched the same files the branch did:

| File | Conflict reason |
|---|---|
| `app/rms/costing.py` | I cherry-picked Sprint 2.3 split (789 → 54 lines). Branch has whitespace-only changes to the old monolith. |
| `app/rms/settings.py` | DELETED on main (Sprint 2.1, -813 lines). Branch still has the dead file. |
| `app/rms/settings_original.py` | DELETED on main. Same. |
| `app/rms/tag_algebra.py` | I added it as a back-compat shim (Sprint 2.2). Branch has different content. |
| `app/rms/tagging/__init__.py` | I merged Sprint 2.2. Branch has different tagging. |
| `app/rms/tagging/filters.py` | I changed during Sprint 2.2. Branch has different changes. |
| `app/rms/config.py` | Branch wants 97 → 101. Main is at 98. |
| `app/rms/db.py` | Both branches add migrations. Branch has 3 more (099, 100, 101). Main has 1 (098). |
| `app/rms/eod_closed.py` | Both branches touched clock helpers. |
| `app/rms/migrations/_098_production_closed_day.py` | Add/add. Mine (recovered) and branch's. **Same logic, different comments.** |
| `app/routers/customers.py`, `eod.py`, `health.py`, `pedidos.py`, `recipes.py`, `reportes.py`, `settings_runtime.py` | I touched some (PR #45 merge added P0-P6 + Tier 8 obs). Branch has its own changes. |
| `app/templates/cliente_detalle.html` | Both branches add m.gs_full() calls. |
| `docs/user-guide/README.md` | I added /guia/glosario. Branch added 4 new sections. |
| `pyproject.toml` | Both branches bump versions. |
| `tests/test_help_route.py` | I added 18 glossary tests. Branch has different content. |
| `tests/test_settings.py` | DELETED on main (Sprint 2.1). Branch has tests for it. |
| `tests/test_tag_algebra_normalization_2026_09_29.py` | Both branches touched. |
| `tests/test_migration_090/091/092_*.py` | Both branches touched. |

## Two paths forward

### Path 1: Surgical rebase — extract Bucket B (the real work) only

**What's salvageable without massive merge work:**
1. **Migration 099** (production_completion.updated_at) — T-2026-10-04 Tier 5-K
2. **Migration 100** (freezer_temperature_log) — T-2026-10-04 B.6 HACCP
3. **Migration 101** (recipe.fermentation_minutes) — T-2026-10-05 B.3
4. **Models** `FreezerTemperatureLog`, `ProductionClosedDay`
5. **/reportes/demand** route

These 5 items have minimal conflict with main. I could cherry-pick them as 5 small commits in ~30 min.

**What's NOT salvageable from this PR:**
- Lint cleanup (Bucket A) — 1910 → 218 ruff errors. Can re-run on main instead.
- Smoke test pre-provision (Bucket C) — conflict with main's db.py
- Docs additions (Bucket D) — 5 files, mostly low-stakes, but conflict with my /guia/glosario
- Produccion print + worksheet (Bucket B items 4-5) — 1057 lines of template changes, conflicts with my PR #45 work

### Path 2: Force-merge the entire PR

**Cost:** 1-2 hours of conflict resolution. ~30 conflict files, many with semantic content (not just whitespace).

**Risk:** Some conflicts will need human judgment. The branch has 105 commits over 2 days from a sibling session; the merge could introduce subtle issues.

**Benefit:** All 105 commits land. Lint cleanup is real, the 5 features are real, the docs are real.

## My recommendation

**Path 1 (cherry-pick Bucket B's 5 items)** — because:
- The 5 items are **real, isolated, valuable work** that the user explicitly asked for ("don't lose any work")
- The lint cleanup is **mechanical and re-runnable** — I can re-run `ruff check --fix` on main after the cherry-picks
- The merge cost (1-2h) is not justified by the value of the lint cleanup alone
- The conflict risk is real (24+ conflict files, including db.py which is 1313 lines of changes)
- The sibling session's design choices may not match mine (different version pins, different schema, different config)

**Implementation plan (if approved):**
1. Cherry-pick the 5 migration files + their models as a single commit (~5 min)
2. Cherry-pick the /reportes/demand route as a separate commit (~5 min)
3. Cherry-pick the 5 + /reportes/demand tests as another commit (~5 min)
4. Verify migrations run cleanly on prod (need to bump schema 98 → 101)
5. Run lint cleanup on main separately (re-run `ruff check --fix` ~30 min)
6. Close PR #46 with a comment explaining the cherry-pick extraction
