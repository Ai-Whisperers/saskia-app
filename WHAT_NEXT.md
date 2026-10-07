# the operator · What Next? (refresh 2026-10-07)

> **Supersedes** the prior 2026-10-05 state. Older `IMPROVEMENT_BACKLOG.md`,
> `COMPLETE_*.md`, `PHASE2_*.md` are stale — use `git log` as ground truth:
> `git log --oneline --since="2026-10-01"`.

## 📊 Current State (2026-10-07)

| Knob | Value | Source |
|------|-------|--------|
| Schema | v110 | `app/rms/config.py:87` |
| Migrations on disk | 37 | `app/rms/migrations/_*.py` |
| Tests collected | 6,770 (129 deselected) | `pytest --collect-only` |
| P40 tests | 13/13 ✅ | `tests/test_P40_*.py` |
| Held-sale tests | 25/25 ✅ | `tests/test_held_sales*.py` |
| Open ruff findings | 0 (in P40 files + held_sale) | `ruff check` |

## ✅ Closed in the last week (since 2026-10-01, top items only)

- **Held-sale (B-7 port from Hao0321/pos-pro, MIT)** — `9aa32bef`.
  POS pause/resume carts. Migration 110.
- **P40: One-tap "Marcar comprado" on /reorder** — `f6f9aa72`. Closes
  the 30-day "0 purchases logged" gap. Per-row + bulk button.
- **P40: "Cargar plan desde plantilla semanal"** — `a64e64c9`. Closes
  the "21 template rows, 0 used" gap. CTA on `/produccion`.
- **P40: EOD view warms demand snapshot** — `0b46620e`. Closes the
  30-day empty `production_demand_snapshot`. Side-effect of opening /eod.
- **Held-sale ruff cleanup** — `a23908a2`. Closed 4 findings (I001, W292,
  ANN202, S608).
- **Per-client branding on /menu + /m/{slug}** — `d6bead2e`.
- **Pre-billing checklist (URY pattern)** — `4384423b`.
- **Multi-line preflight + ventas.html** — `28087bc4`.
- **FloCafe stock ceiling + low-stock badge** — `36021585`.
- **FloCafe design tokens (CSS custom properties)** — `815f12f5`.
- **FloCafe receipt oracle (golden fixture)** — `15cf78a5`.
- **Date-boundary CI workflow + 60 tests** — `f26c191b` (port from
  OpenResto).
- **Pre-migration backup + fail-closed on newer schema** — `3970bfda`.
- **Atomic DDL via SAVEPOINT for Postgres** — `18668813` + `50c35082`.
- **Menús ejecutivos, venta por peso, pagos mixtos, propinas, arqueo
  X/Z, fiado ledger, LLM copiloto (fase 0)** — bulk of WP-1.x / Fase 2-4.

## 🎯 What's next? (3 picks, ranked)

### #1 — **Deploy the batch to VPS** — 30 min, real impact

P40 + held_sale + public-menu branding + FloCafe reports are sitting on
`main`. None are live. The 30-day "0 demand_snapshot rows" gap will only
start healing after VPS deployment, because /eod runs there.

```
ssh paragu-ai 'cd /opt/saskia && docker compose pull && docker compose up -d'
ssh paragu-ai 'curl https://sazon-vps.paragu-ai.com/healthz'
```

Risk: medium. Pre-migration backup runs first (AGENTS.md rule 17) and
`fail_closed_on_newer_schema()` aborts if anything is off.

### #2 — **Production Planner → Shopping List** — 3 hr, killer feature

`POST /plan/shopping-list` that materializes production-plan shortfalls
into `ShoppingListItem`. The operator has all data already; this single
endpoint closes the "ingredient need → buy list" loop. Plus a
`/shopping-list` view.

P40 already made the template loader a 1-click action; this is the
second half of that flow.

### #3 — **Sale channel mismatch** — 2 hr, quick win

Extend `Sale.channel` enum with HEREBUS channels (Retail / Wholesale /
Distributor / Eventual); add the filter on `/ventas`; auto-classify from
VENTAS sheet's `Canal de Venta` column. 346 sales say `mostrador`, 6
`retail`, 3 `wholesale`. Wrong channels silently skew revenue reports.

## 🛠 Tooling & Plumbing

- **Held_sale ruff**: closed.
- **Stale docs**: prior `IMPROVEMENT_BACKLOG.md`, `COMPLETE_*.md`,
  `PHASE2_*.md` are superseded by this file. Don't re-edit them.
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

---

**Generated:** 2026-10-07 by post-P40 session.
**Update pattern:** when this falls out of date, run `git log --oneline
--since="<DATE>"` and rewrite the "Closed in the last week" section.
Don't add to this file — start a new dated file.