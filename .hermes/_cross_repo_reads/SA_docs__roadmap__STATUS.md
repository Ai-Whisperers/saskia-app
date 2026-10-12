# Saskia RMS — Current Status

**Last updated:** 2026-10-09 (reorg landed at e9b80533)
**Live URL:** https://sazon-vps.paragu-ai.com
**Branch:** `main` @ `640c21e5` (~1,500 commits, deployed, clean)
**Schema version:** 117 (migrations 113..117 — allergen/dietary tags, EOD alert templates, ingredient image_url)
**Python LOC (app/):** 96,306 lines across 116 modules
**Python LOC (tests/):** 124,258 lines (1.29× app code)
**Routers:** 53 files (30,494 lines)
**Templates:** 131 files (27,728 lines)
**Tests collected:** 7,961 (129 deselected)
**Working tree on `main`:** clean (refactor wave landed in 11+ commits between 14:30 and 15:50 UTC)

## Health check (assumed green — see VPS section)

| Endpoint | Expected | Notes |
|---|---|---|
| `https://sazon-vps.paragu-ai.com/healthz` | 200 OK | Last verified via deploy `deploy-20261009-140443` |
| `https://sazon-vps.paragu-ai.com/healthz/deps` | 200 OK | Probes Supabase + R2 + disk |
| `https://sazon-vps.paragu-ai.com/healthz/backup` | 200 OK | Reports backup age < 26h |

## Schema-version source (deliberate decision 2026-10-09)

- Source of truth: **`app_meta` table** (`key='schema_version'`), NOT `PRAGMA user_version`
- See `docs/operations/2026-10-09-schema-version-source.md` for rationale
- This supersedes AGENTS.md rule 18 which called for `PRAGMA user_version`

## Deployment state

- **Production stack:** `saskia-vps` on `paragu-ai` (ServaRica VPS), Docker Swarm + Traefik + Cloudflare DNS-01
- **Three-environment deploy infra:** staging + production + dev (commit `1ba379a1 feat(deploy): three-environment deploy infra` + `0f1ad5af fix(deploy): match live saskia-vps labels + per-env resource limits`)
- **Local dev:** `127.0.0.1:8765` (SQLite), `0.0.0.0` only in hosted mode (TLS terminated by Cloudflare)
- **CI gates:** ruff + ruff format + pyright + complexipy + deptry + dead-code (sensez) + arch (cycles + layered imports) + pytest + migration safety
- **Coverage floor:** **35%** (tracked, was 25.97% on `main` HEAD — see regression note below)

> ⚠️ **Coverage regression:** the 35% gate is currently flagged red at 25.97% on `main` HEAD. Likely cause: the +633 test surge in the last 24 hours added many low-coverage fixtures. Investigation pending.

## Open gaps (genuine, post-2026-10-08 lessons-book audit)

Source: `sazon_lessons_book_v2_20261008.md` (12 G-OPEN items) intersected with `git log --since=2026-10-08` (which closed several). Net remaining, ranked by signal/cost:

| # | Gap | Source | Status |
|---|---|---|---|
| 1 | Daily P&L rollup (G-OPEN-1) | lessons book | ⏳ still open |
| 2 | Confidence badge on grilla (G-OPEN-5) | lessons book | ⏳ 1-line CSS render |
| 3 | KOT error log (G-OPEN-3 / L-KDS-V2-1) | URY port pending | ⏳ ~4h |
| 4 | Maintenance middleware (G-OPEN-7 / L-OPS-V2-4) | FloCafe port pending | ⏳ ~4.5h |
| 5 | plan_accuracy → forecast_sales feedback loop (G-OPEN-6) | lessons book | ⏳ ~6.5h |
| 6 | Reimprimir KOT (L-KDS-V2-2) | UX | ⏳ ~2.5h |
| 7 | Seasonal calendar → settings_kv (G-OPEN-4) | settings_kv ships, migration pending | ⏳ ~4h |
| 8 | P95 stockout badge on /inventario (L-STOCK-V2-4) | Poisson output exists, not surfaced | ⏳ ~3h |
| 9 | Per-category food-cost variance bands (L-RPT-V2-4) | industry pattern, no impl | ⏳ ~8.5h |
| 10 | pedido_status_audit (G-OPEN-11) | apply audit-module pattern | ⏳ ~1d |
| 11 | Real PG testcontainers (E1.S2 / v3 epics) | AGENTS.md rule 26 (ASK in body) | ⏳ ~4h |
| 12 | Barcode scanner integration | wishlist raw | ⏳ small |
| 13 | Use-first ingredient email cron (G-OPEN-12) | lessons book | ⏳ ~0.5h |
| 14 | Production worksheet cron (deliverable per `docs/wishlist/triaged/2026-09-04-produccion-del-dia-worksheet.md`) | wishlist triaged | ⏳ ~1d |
| 15 | **Supabase RLS multi-tenant (BACKLOG #38)** | **Deferred per SASKIA-210** | 🚫 parked |
| 16 | Supabase Storage (`docs/plans/SUPABASE-RLS-STORAGE-DECISION-2026-10-08.md`) | Decision doc landed | 🟡 partially shipped |
| 17 | Sentry→Telegram activation (env-gated) | Operator rule 1 | 🚫 parked until 30 customers |
| 18 | Auto-reorder based on stockout | wishlist triaged; partial via SASKIA-205 | ⏳ |
| 19 | React/Vue/Tailwind SPA build step | explicitly forbidden | 🚫 parked |
| 20 | Multi-tenant single-DB | explicitly deferred until Saskia happy | 🚫 parked (SASKIA-210) |

## Recently shipped (last 14 days, by area)

### Hardening / tooling (waves 4–7)

- **complexipy + pyright + deptry + sensez** wired into `make cognitive / pyright / dead-code`
- **Architecture-imports allow-list** pinned by 8 regression tests; 8 known-allows + 3 known-cycles marked in source (commit `2f85d8c3`)
- **7 cognitive-CC refactors** of inventory/products/recipes/sales routes (CC 198 → 3 etc.)
- **3 import-cycle breaks**: db ↔ backup (`5f89c3c7`), settings ↔ registry (`c27b1a5d`), tagging ↔ ingredient_intel (`9af06e7c`)
- **Tagging system consolidated**: removed 7 duplicate functions, `TagKind` enum, `STARTER_TAGS` fold-in (`38f27c7b`)
- **Sprint 2.1 type-checking** surfaced and fixed **5 production runtime bugs** (`93d5f16e`)
- **Schema-source decision doc**: `5e56980c docs(schema): document app_meta vs PRAGMA user_version decision`
- **Migration 117**: `8e07b43d Ingredient.image_url` (for La Vaquita Feliz image pipeline)
- **Migrations 113–116**: shopping_price_snapshot, settings_kv_consolidation, allergen_dietary_tags, eod_alert_templates

### Refactor wave (CC reductions)

- **`f65e61dd`** `sale_create_multi` 168→3
- **`0bea7ed1`** style: ruff format post-SeedContext-refactor
- **`251fbc34`** + **`c51c9c95`** **`seed_sazon` 232→1** via SeedContext pattern
- **`8f3533c3`** `ensure_customer` 48→11
- **`64f3c62b`** `recipe_create` 42→3
- **`889f9d39`** `recipe_update` 36→3
- **`67fc5a58`** `products_list` 35→4
- **`bc710dfb`** `recipe_edit` 33→1
- **`b1f074dd`** `forecast_demand` 35→4
- **`a04d3928`** `compute_customer_defaults` 39→2
- **`a466dc03`** `_build_recipe_breakdown` 48→3
- **`32832439`** `validate_cart_intent` (pre_sale_check_cart) 48→2 (in-progress on working tree)
- Multiple `inventory_*` route refactors (CC 198→3, etc.)

### Image pipeline + La Vaquita Feliz

- `0846a792` `feat(seed): reconcile sazon seed with HEREBUS workbook (94 ingredients)`
- `d8fadabf` `feat(images): research-backed descriptions for all 22 products`
- `74c9df7b` `feat(images): ship 22 product images + 9 variants`
- `d6e11459` `feat(images): thumbnail-friendly ingredient prompts`
- **NB:** these are on `feat/workbook-seed-reconciliation` (47 commits ahead of origin/main), NOT yet on `main`. Also `docs/operations/2026-10-08-workbook-seed-reconciliation.md` documents the work.

### Security

- `7e2bd8d9` ZAP promote-to-HIGH (sibling branch — needs merge)
- `36021585` Stock ceiling (port from URY)
- `4683b025` OWASP ZAP CI gate
- `4384423b` Pre-billing checklist (URY port — partially landed in `validate_cart_intent`)
- `f26c191b` Date-boundary CI
- `815f12f5` Design tokens
- `15cf78a5` Receipt oracle

### Other

- `88288f4f` Architecture regression tests + CI workflow
- `881963c9` `create_app()` factory pattern
- `5f22decb` `sensez` dead-code detector
- `69445818` complexipy + pyright in lightweight CI gate
- `6ce98890` (commit chain) v3 + v4 data-intelligence plan executed
- `b573596b` bot cleanup + lint exceptions
- `0bea7ed1` ruff format post-refactor


### Refactor wave (continued -- landed 14:30-15:50 UTC)

- **`17020926`** `validate_sale_intent` (pre_sale_check) 58->3
- **`e9a08fbd`** `consolidate_open_items` (shopping) 32->4
- **`c8946a4a`** `to_file` (export) 32->0
- **`7f672f36`** `pedidos_detail` 32->1
- **`08deb09b`** `dashboard_index` 32->0
- **`78e75c15`** `product_cost_freshness` 32->11
- **`56f2b77e`** `fix(sales)`: restore single-method payment row + create_at for split payments
- **`ef24eb51`** `fix(deploy)`: test/dev use local-bcrypt auth (no Supabase)
- **`91f047a8`** `fix(deploy)`: use legacy Supabase JWT keys (ANON_KEY/SERVICE_ROLE_KEY)
- **`0f1ad5af`** `fix(deploy)`: match live saskia-vps labels + per-env resource limits
- **`640c21e5`** `fix(ci)`: use existing VPS_KEY secret instead of missing SASKIA_VPS_SSH_KEY
- **`fffe7c7f`** `fix(ci)`: use throwaway venv for pyyaml install in deploy workflows
- **`5e3f53e2`** `fix(ci)`: use --break-system-packages for uv pip install in deploy workflows
- **`5c140b1f`** `chore(lint)`: restore ruff clean after bot's complexity refactors

## Coverage regression (active issue)

- `pytest --cov=app` returns **25.97%**, **below the 35% CI floor**
- Likely caused by the +633 test surge from the Oct 9 hardening wave (lots of fixture/trivial tests, not impl-coverage tests)
- **Action pending:** add coverage-enforcing tests for the new CC-refactored functions, or relax the gate consciously

## Cross-references

- [`EXECUTION-PLAN.md`](EXECUTION-PLAN.md) — what to ship next
- [`BACKLOG.md`](BACKLOG.md) — merged source-of-truth backlog
- [`WISHLIST.md`](WISHLIST.md) — wishlist index
- [`epics/`](epics/) — long-form epic stories
- [`decisions/`](decisions/) — ADRs and alignment decisions
- [`audits/`](audits/) — periodic audits
- [`sessions/`](sessions/) — multi-session coordination plans
- [`historical-plans/`](historical-plans/) — original planning docs (read-only)

## See also

- [`../analysis/2026-10-08/`](https://example.invalid/placeholder) — Oct 8 codebase audit
- [`../user-guide/00-quickstart.md`](../user-guide/00-quickstart.md) — operator quickstart
