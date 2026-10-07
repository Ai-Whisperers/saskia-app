# the operator · What Next? (refresh 2026-10-07b)

> **Supersedes** `WHAT_NEXT_2026-10-07-archived.md`. Older
> `IMPROVEMENT_BACKLOG.md`, `COMPLETE_*.md`, `PHASE2_*.md` are stale —
> use `git log` as ground truth: `git log --oneline --since="2026-10-01"`.

## 📊 Current State (2026-10-07)

| Knob | Value | Source |
|------|-------|--------|
| Schema | v110 | `app/rms/config.py:87` |
| Migrations on disk | 37 | `app/rms/migrations/_*.py` |
| Tests collected | 6,854 (129 deselected) | `pytest --collect-only` |
| Shopping tests | 14/14 ✅ | `test_P39_*`, `test_P19_*`, `test_shopping_*`, `test_shopping_from_plan` |
| Stale test paths | 0 | `test_shopping_benchmarks.py` paths fixed |
| Held-sale tests | 25/25 ✅ | `tests/test_held_sales*.py` |
| P40 tests | 13/13 ✅ | `tests/test_P40_*.py` |
| Open ruff findings | 0 (in P40 files + held_sale) | `ruff check` |

## ✅ Closed in the last week (since 2026-10-01, top items only)

- **Production Planner → Shopping List** — `eaaf6a12` + `bc9a76ff`
  + `8edaefd6` + `ff0ed55e`. Operator one-click: pick tomorrow's plan
  on `/produccion`, "Enviar faltantes a lista de compras" button
  posts to `/shopping-list/from-production-plan`, deduped by
  `(ingredient_id, unit)`, supplier-grouped, `wa.me` deep-link.
  14/14 tests pass.
- **C.6 sticky table headers on 5 long-table templates** — `6280c951`.
- **Perf: dashboard forecast N+1 → batched (SASKIA-202)** — `caf1cf19`.
  Per-product `forecast_sales()` calls collapsed to single batched
  SELECT. 21/21 dashboard tests pass.
- **Held-sale (B-7 port from Hao0321/pos-pro, MIT)** — `9aa32bef`.
- **P40: One-tap "Marcar comprado" on /reorder** — `f6f9aa72`.
- **P40: "Cargar plan desde plantilla semanal"** — `a64e64c9`.
- **P40: EOD view warms demand snapshot** — `0b46620e`.
- **C.1 Sentry→Telegram activation** — `aa0eb6cf` (operator needs to
  set `TG_BOT_TOKEN` + `TG_CHAT_ID` on VPS).
- **P41 CHECK constraint on sale.channel + pedido.channel** — `e64ad50f`.
- **P42 use Channel.X.value in all write paths** — `e586f47c`.
- **Per-client branding on /menu + /m/{slug}** — `d6bead2e`.
- **Pre-billing checklist (URY pattern)** — `4384423b`.
- **FloCafe stock ceiling + low-stock badge** — `36021585`.
- **FloCafe design tokens (CSS custom properties)** — `815f12f5`.
- **FloCafe receipt oracle (golden fixture)** — `15cf78a5`.
- **Date-boundary CI workflow + 60 tests** — `f26c191b` (port from
  OpenResto).
- **OWASP ZAP API scan (M-INFRA-001)** — `4683b025` (port from OpenResto).
- **Pre-migration backup + fail-closed on newer schema** — `3970bfda`.
- **Atomic DDL via SAVEPOINT for Postgres** — `18668813` + `50c35082`.
- **Menúes ejecutivos, venta por peso, pagos mixtos, propinas, arqueo
  X/Z, fiado ledger, LLM copiloto (fase 0)** — bulk of WP-1.x / Fase 2-4.

## 🎯 What's next? (3 picks, ranked)

### #1 — **Deploy the batch to VPS** — 30 min, real impact

P40 + held_sale + public-menu branding + C.1 Telegram wiring + SASKIA-202
N+1 fix + SASKIA-203 shopping-list button are sitting on `main`. None are
live. The 30-day "0 demand_snapshot rows" gap will only start healing
after VPS deployment, because /eod runs there.

```
ssh paragu-ai 'cd /opt/saskia && docker compose pull && docker compose up -d'
ssh paragu-ai 'curl https://sazon-vps.paragu-ai.com/healthz'
```

Risk: medium. Pre-migration backup runs first (AGENTS.md rule 17) and
`fail_closed_on_newer_schema()` aborts if anything is off.

### #2 — **Wire C.1 Telegram env on VPS** — 5 min, kills a noisy Sentry

C.1's code path (`aa0eb6cf`) is dormant until
`TG_BOT_TOKEN` + `TG_CHAT_ID` are set on the VPS. Without them, the
hook is a silent no-op (preserves test_sentry_lazy_import contract).

```
ssh paragu-ai 'cat > /opt/saskia/secrets/telegram.env <<EOF
TG_BOT_TOKEN=[REDACTED]
TG_CHAT_ID=[REDACTED]
EOF
chmod 600 /opt/saskia/secrets/telegram.env
docker compose --env-file /opt/saskia/secrets/telegram.env up -d'
```

Secrets live in BWS (`sazon-telegram`), not in the repo. Pull into the
container at runtime via `--env-file`.

### #3 — **Sale channel mismatch cleanup** — 2 hr, quick win

Extend `Sale.channel` enum with HEREBUS channels (Retail / Wholesale /
Distributor / Eventual); add the filter on `/ventas`; auto-classify from
VENTAS sheet's `Canal de Venta` column. 346 sales say `mostrador`, 6
`retail`, 3 `wholesale`. Wrong channels silently skew revenue reports.

Blocked by: the existing P41 CHECK constraint (only 6 values allowed).
Need migration 111 to ALTER the CHECK constraint. ~30 min for the
migration + re-classify script, the other 90 min is the UI filter.

## 🛠 Tooling & Plumbing

- **Stale docs**: prior `IMPROVEMENT_BACKLOG.md`, `COMPLETE_*.md`,
  `PHASE2_*.md` are superseded by this file. Don't re-edit them.
- **`WHAT_NEXT_2026-10-07-archived.md`** is the prior state — read for
  history, don't revive items from it without checking `git log`.
- **Backup discipline**: AGENTS.md rule 17 (pre-migration backup) is
  now enforced at `init_db()`.

## 💼 Business-Operational priorities (operator-visible)

- **Wishlist purchases don't trigger inventory** (#2 in old WHAT_NEXT).
  Still open.
- **Predictive restocking** (Poisson regression on sale_stock_move →
  "expected consumption next 3 days"). Depends on demand_snapshot,
  which now fills daily thanks to P40 part 3.
- **Forward-only migration rollback path**: still TODO (L effort).
- **Supabase RLS + Storage for multi-tenant readiness**: still TODO.
- **Snapshot price on ShoppingListItem**: see shopping-list audit, gap
  not yet created.

---

**Generated:** 2026-10-07b by SASKIA-203 shopping-list affordance PR.
**Update pattern:** when this falls out of date, run `git log --oneline
--since="<DATE>"` and rewrite the "Closed in the last week" section.
Archive the old version as `WHAT_NEXT_YYYY-MM-DD-archived.md` first.
Don't add to this file in-place — start a new dated file.