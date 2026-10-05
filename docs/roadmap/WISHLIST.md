# Saskia RMS — Wishlist Index

> **Last updated:** 2026-10-05
> **Source:** `docs/wishlist/` (append-only bucket for ideas; see
> [`docs/wishlist/README.md`](../../wishlist/README.md) for the contract).

## Totals

| Bucket | Count |
|---|---:|
| **Raw** (untriaged) | 1 |
| **Triaged** (accepted into future sprint) | 16 |
| **Rejected** (out of scope) | 4 |
| **Total** | **21** |

## Raw (1)

| File | Title | Date |
|---|---|---|
| `2026-09-04-whatsapp-bot-daily-summary.md` | WhatsApp bot for daily sales summary | 2026-09-04 |

## Triaged (16)

| File | Title | Date | Overlap with backlog |
|---|---|---|---|
| `2026-09-04-auto-reorder-based-on-stockout.md` | Auto-reorder based on stockout report | 2026-09-04 | — (canonical C.1 area) |
| `2026-09-04-barcode-scanner-integration.md` | Barcode scanner integration for inventory receive | 2026-09-04 | Epic 23 (E23) |
| `2026-09-04-ci-smoke-against-deploy-shape-env.md` | CI smoke test against deploy-shape env | 2026-09-04 | — |
| `2026-09-04-codeowners-routing.md` | CODEOWNERS for review routing | 2026-09-04 | E24.S3 |
| `2026-09-04-contributing-md.md` | CONTRIBUTING.md | 2026-09-04 | E24.S2 (✅ shipped) |
| `2026-09-04-csrf-tokens-on-state-changing-forms.md` | CSRF token on all POST forms | 2026-09-04 | **Canonical A.2 (P0)** |
| `2026-09-04-customer-directory-loyalty.md` | Customer directory / loyalty | 2026-09-04 | Epic 13 (E13) + BACKLOG #14 ✅ |
| `2026-09-04-dependabot-renovate-pinning.md` | Dependabot / Renovate for runtime + dev deps | 2026-09-04 | E24.S4 (✅ 3 dependabot PRs open) |
| `2026-09-04-docker-compose-dev-postgres.md` | docker-compose.dev.yml (PG + app) for local dev | 2026-09-04 | E24.S5 |
| `2026-09-04-makefile-entry-points.md` | Makefile with setup / test / lint / run | 2026-09-04 | E24.S1 (✅ shipped) |
| `2026-09-04-merma-waste-tracking.md` | Merma / waste tracking | 2026-09-04 | Epic 22 (E22 ✅ shipped) + canonical `feat/prod-quick-merma` |
| `2026-09-04-per-user-audit-log.md` | Per-user audit log of CRUD on inventory/recipes/sales | 2026-09-04 | **Canonical A.3 (P0)** |
| `2026-09-04-produccion-del-dia-worksheet.md` | Producción del día worksheet | 2026-09-04 | Epic 21 + canonical B.2 |
| `2026-09-04-rate-limit-on-endpoints.md` | Rate-limit on auth + write endpoints | 2026-09-04 | BACKLOG #10 ✅ /login + reads |
| `2026-09-04-real-drive-shape-import-fixture.md` | Real Drive-shape fixture for Excel import test | 2026-09-04 | Epic 7 (E7 ✅ shipped) |
| `2026-09-04-timezone-groupby-sales.md` | Time-zone field on Sale + groupby timezone | 2026-09-04 | BACKLOG #27 ✅ |

## Rejected (4)

| File | Title | Reason (in file) |
|---|---|---|
| `2026-09-04-multi-tenant-restaurants.md` | Multi-tenant (multiple restaurants under one deploy) | Saskia is single-tenant. See Epic 15 (also deferred). |
| `2026-09-04-multi-user-roles-rbac.md` | Multi-user roles (admin vs cashier) | Saskia is single-user. |
| `2026-09-04-r2-backup-retention-policy.md` | R2 backup retention policy | Backups go to local + cron, not R2 |
| `2026-09-04-saskia-rebuild-of-run-sh-for-mac.md` | installer/run.sh — Mac launch script | Windows-first per Fase 1 dev plan; Mac deferred to Task 9 |

## Key insight

**3 wishlist items are P0 (canonical "cerrar puertas"):**
- `2026-09-04-csrf-tokens-on-state-changing-forms.md` → Canonical A.2
- `2026-09-04-per-user-audit-log.md` → Canonical A.3
- (and `2026-09-04-rate-limit-on-endpoints.md` is mostly done — `/login` rate limit shipped BACKLOG-equivalent; read-side rate limits shipped BACKLOG #10)

**8 wishlist items are now ✅ Done** (mapped above in the Overlap column).
**10 wishlist items are still open** as future work.
