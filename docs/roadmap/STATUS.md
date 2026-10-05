# Saskia RMS — Current Status

**Last updated:** 2026-10-05
**Live URL:** https://saskia-vps.paragu-ai.com
**Branch:** `main` @ `4214cc0` (clean, deployed, 949 commits)
**Schema version:** 97 (migrations 093–097 from Sprint 4.6 backend-overhaul)
**Working tree:** clean (no uncommitted changes; only ignored PNGs in `app/static/uploads/`)

## Health check (verified 2026-10-05)

```
GET  https://saskia-vps.paragu-ai.com/healthz                 → 200 OK
GET  /api/smoke/waste-source-mix                              → 404  (not in main; in feat/prod-quick-merma)
GET  /api/smoke/prod-loop                                     → 404  (not in main; in feat/prod-quick-merma)
GET  /merma (auth-protected)                                  → 401
GET  /auditoria?source=… (auth-protected)                     → 401
```

## Deployment state

- **Production stack:** `saskia-vps` on `paragu-ai` (ServaRica VPS), Docker Swarm + Traefik + Cloudflare DNS-01
- **Legacy URL:** `saskia-rms.paragu-ai.com` (Render) — **SUSPENDED** (returns 503)
- **Local dev:** `127.0.0.1:8765` (SQLite), `0.0.0.0` only in hosted mode (TLS terminated by Cloudflare)
- **Test gate:** coverage floor **35%** (grew 30 → 35 on 2026-10-02; aspirational 80%)
- **CI:** ruff + ruff format + pytest + typer + aiw-saskia migrate smoke + CHANGELOG discipline

## Backlog summary (40 tracked items)

| Tier | Total | ✅ Done | 🔶 In Progress | ❌ TODO |
|---|---:|---:|---:|---:|
| Tier 1: P0 Critical correctness | 6 | 4 | 2 (#1, #4) | 0 |
| Tier 2: P0 Security / data integrity | 6 | 5 | 0 | 1 (#12) |
| Tier 3: P1 Quality / refactoring | 8 | 8 | 0 | 0 |
| Tier 4: P1 Performance | 5 | 5 | 0 | 0 |
| Tier 5: P2 Analytics | 6 | 6 | 0 | 0 |
| Tier 6: P2 Predictive / ML | 5 | 3 | 0 | 2 (#32, #33 already done but #32 still TODO) |
| Tier 7: P3 Supabase / infra | 4 | 2 | 0 | 2 (#37 done in HEAD, #38) |
| **Total** | **40** | **33** | **2** | **5** |

> **Note:** the IMPROVEMENT_BACKLOG numbers 32 (#32 Poisson) is the only remaining
> genuinely-TODO item in Tier 6; #33 is now ✅ Done via `/produccion/accuracy`.

## Epic plan (25 epics, 6 phases) — coarse status

Source: [`epics/00-EPIC-PLAN-EXTRACT.md`](epics/00-EPIC-PLAN-EXTRACT.md)

| Phase | Epics | Status |
|---|---|---|
| P0 Close-out (E1–E5) | 5 | ~95% done — only E2.S2 (PG testcontainers) and E3.S4 (healthz/db runbook) explicitly open |
| P1 Data + insights (E6–E8) | 3 | 100% done |
| P2 Operator UX (E9–E12) | 4 | 95% done — tags, filtering, etc. all shipped |
| P3 Customer + retention (E13–E14) | 2 | mostly done — Fase 2 features |
| P4 Scale + multi-tenant (E15–E16) | 2 | partially open (multi-tenant is intentionally deferred per Saskia-single-user scope) |
| P5 Polish + future-facing (E17–E25) | 9 | mostly aspirational / future |

## Branches (local)

| Branch | Commits ahead of main | Status | Deployed? |
|---|---:|---|---|
| `feat/prod-quick-merma` | 15 | Open PROD-MERMA-2 batch (merma dashboard, source-mix chips, smoke endpoints) | **No** — 404s in prod |
| `sprint-2-2-tagging` | 1 | Open cosmetic refactor | No |
| `archive/stash-*` (11) | 3–12 each | WIP stashes; **all work already in main** | n/a |
| `backup/before-rebase-*` | 0 | Pre-rebase backup, redundant | n/a |
| `archive/eng-2026-10-02-backend-overhaul` | 0 ahead / 14 behind | Already merged into main via `00db931` | n/a |

## Recently shipped (last 10 days)

- **Sprint 4.6 backend-overhaul** (migrations 093–097) — Expense, Closure, SoftDelete, Audit, AvgCost
- **Sprint 4.4 StockMovement consolidation** — `cf73ecb` rewrote `void_sale()` to query `StockMovement` after prod crash
- **Sprint 4.5 atomic migrations** — `atomic_ddl_block` SAVEPOINT helper + 085–089 converted
- **Sprint 4.7 backup healthz** — `GET /healthz/backup` + `POST /admin/backup`
- **Sprint 4.6 healthz/deps** — Supabase + R2 + disk probes
- **Sprint 4.8 ventas-hora heatmap** — `/reportes/ventas-hora` 7×24 grid
- **Sprint 4.9 customer reorder rate** — `/ops/status` surfaces rate
- **Sprint 4.10 waste ROI** — `/reportes/mermas-cost` leaderboard
- **Sprint 4.11 supplier volatility** — `/suppliers/volatility` leaderboard
- **Sprint 4.1 ventas detail** — `GET /ventas/{id}` standalone view
- **Sprint 4.2 RecipeLine.qty Numeric** — Float → Numeric(12,4)
- **Reorder redesign** (Phase 1–4) — supplier lock/unlock, CRUD, CSV upload, Superseis scraper
- **Phase 14 hygiene pass** — 5 stale TODOs closed, `request._json`/`request._form` sweep
- **HEAD `4214cc0` 2026-10-02** — `feat(storage): Supabase Storage for /productos/upload-image` (BACKLOG #37)

## Outstanding work (open)

| # | Item | Source | Notes |
|---|---|---|---|
| BACKLOG #1 | SaleStockMove + StockMovement full consolidation | IMPROVEMENT_BACKLOG | Documented dual-write; needs refactor session |
| BACKLOG #4 | Atomic DDL across all 90 migrations | IMPROVEMENT_BACKLOG | Helper ships; 83 migrations still need conversion |
| BACKLOG #12 | Forward-only migration rollback paths | IMPROVEMENT_BACKLOG | Intentional design, future |
| BACKLOG #32 | Poisson regression restocking | IMPROVEMENT_BACKLOG | ML project, scoped for later |
| BACKLOG #38 | Supabase RLS multi-tenant | IMPROVEMENT_BACKLOG | Future |
| Canonical A.1 | Confirm modals on destructive actions | canonical-roadmap | Cerrar-puertas P0 |
| Canonical A.2 | CSRF tokens on all forms (~30 missing) | canonical-roadmap | Cerrar-puertas P0 |
| Canonical A.3 | Audit log on 12 actions (12 missing) | canonical-roadmap | Cerrar-puertas P0 |
| Canonical A.4 | Rate limit on /login (5/min) | canonical-roadmap | Cerrar-puertas P0 (XS) |
| Canonical A.5 | `void_sale` after-cierre bug | canonical-roadmap | Cerrar-puertas P0 |
| Canonical A.6 | Loading skeletons on dashboard/ventas/productos/reportes | canonical-roadmap | Cerrar-puertas P0 |
| Canonical B.1 | Venta Express `/v/quick` | canonical-roadmap | P1 #1 — `-45s/venta` |
| Canonical B.2 | Forecast enchufado in `/produccion/manana` | canonical-roadmap | P1 #2 — `-30% desperdicio` |
| Canonical B.3 | Pedido web upload comprobante (`/p/{slug}`) | canonical-roadmap | P1 #3 |
| Canonical B.4 | Customer merge | canonical-roadmap | P1 |
| Canonical B.5 | Suscripciones sin cron | canonical-roadmap | P1 |
| Canonical B.6 | Cmd+K + atajos POS | canonical-roadmap | P1 |
| Canonical B.7 | 3 insights accionables (60+d, margen<30%, stock N días) | canonical-roadmap | P1 |
| Canonical B.8 | Backup local AES-256 + cron diario | canonical-roadmap | P1 — `auto_backup.py` exists, hook to EOD close |
| Canonical B.9 | `/suppliers/{id}/precios` price comparison | canonical-roadmap | P1 — Gs. 4.3M/año |
| `feat/prod-quick-merma` | 15 commits PROD-MERMA-2 batch | branch | Needs PR + merge + deploy |
| `sprint-2-2-tagging` | 1 cosmetic refactor | branch | Needs PR + merge |
