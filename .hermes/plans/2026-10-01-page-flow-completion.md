# Saskia RMS — Page-Level Flow Coverage Audit (2026-10-01)

## Sources

- 83 commits Sep 30 → Oct 1, 2026 (Ivan + sibling agents)
- 9 phases / tiers shipped: E4.S1, E4.S2, E4.S4, E5.S2, Tier 1-3 (loyalty), Tier 4.1/4.2 (loyalty package + picker split), Tier 5.2/5.4 (EOD idempotency + TZ breakdown), Phase 1-10 (pedidos + clientes + inicio)
- 4198 tests collected; per-area: ventas=5, cliente=8, pedido=23, eod=6, inicio=2, merma=4, inventario=6
- Live SHA d331b819..., schema 76/76

## What was shipped (recap by page)

| Page | Shipped this window |
|---|---|
| `/ventas` | Picker split (Tier 4.2), inline saskia-combo + new-customer form, customer info card with tier/allergen/dietary, loyalty redeem form (auto + manual), auto-suggestions (cumple/volvé pronto/puntos dormidos), "Cliente sin asociar" nudge, receipt footer with points |
| `/clientes` (list) | Tier pill, points column, n_sales column, lifetime spend column, tier filter, search |
| `/clientes/{id}` | Tier badge, loyalty ledger (last 20 movements), Sale.tz breakdown (Tier 5.4), Suscripción badge + one-click "Crear pedido desde suscripción" (Phase 9) |
| `/pedidos/nuevo` | Smart autofill from `?customer_id=`, address picker when 2+ addresses (Phase 7), loyalty banner (Phase 8), new-customer inline form |
| `/pedidos/{id}` | Pedido history timeline (Phase 4), "Pedir de nuevo" CTA (Phase 4) |
| `/pedidos` (list) | Customer name + status pills |
| `/inicio` | 6 KPI cards, DOW-aware forecast, Stock LED, enrollment KPI (Tier 3.2), Stock low avisos, Coffee regulars card with +Pedido CTA (Phase 10) |
| `/eod` | 10-item checklist, notes for next shift, idempotency on save (Tier 5.2), backup on all-done |
| `/recibo` | Footer with points earned (Tier 2) |

## Gaps by page (what's still missing)

### /inicio (Dashboard)

| Gap | Impact | Cost |
|---|---|---|
| Enrollment chart (enrollment_pct over time) | Operators see today's % but not the trend | M — query + small SVG |
| Suggestion telemetry surfaced | Tier 3.2 ships the log, dashboard only sees enrollment KPI | S — read log table |
| Upcoming birthdays / lapsed customers | Operator sees weekly retention opportunities | M — query + UI |
| Mobile-tuned KPI row | Phase E4.S4 added mobile.css but inicio doesn't use a grid that reflows | S — wrapper |

### /ventas (POS)

| Gap | Impact | Cost |
|---|---|---|
| Suscripción badge in customer card | Operator misses "this customer has a subscription" signal during sale | XS — pass active_subs to customer card |
| "Convertir venta → pedido" button | Operator can't escalate a sale into a pedido from POS (delivery/pickup later) | L — flows |
| "Repetir compra" CTA on customer card | Operator can't replicate customer's recent purchase as a new sale | M — query + button |
| Loyalty balance history tooltip on customer card | Operator sees count but not last 5 movements | XS — tooltip popover |

### /clientes (list)

| Gap | Impact | Cost |
|---|---|---|
| One-click "Crear pedido" in row actions | Operator has to open detail → create pedido from suscrip | XS — link |
| Suscripción indicator column | Operator sees who has active subscriptions without opening each | XS — boolean column |
| Last-purchase-time column | Retention outreach visibility | XS — formatted_date |

### /clientes/{id} (detail)

| Gap | Impact | Cost |
|---|---|---|
| Pedido history timeline | Operator has to open pedidos/{id} to see pedidos for this customer | M — reuse pedido_detalle timeline partial |
| "Pedir de nuevo" CTA from a recent pedido | Operator can re-order a past pedido directly | S — link with from= |
| "Aplicar sugerencia" button | Suggestions only on POS; can't apply from cliente detail | M — suggestion endpoint reuse |
| Recent product mix | Operator sees spending but not WHAT they buy | S — aggregate top 5 products |

### /pedidos/nuevo

| Gap | Impact | Cost |
|---|---|---|
| Tier display inline | Operator doesn't see customer's tier while creating pedido | XS — pass tier to template |
| Suscripción-driven prefill | If customer has active suscrip, prefill product_summary | M — backfill + UI |
| Product-suggestion-from-history | "Este cliente siempre pide 2 chipas + 1 jugo" | M — aggregation query |

### /pedidos/{id}

| Gap | Impact | Cost |
|---|---|---|
| Linked sales list (migration 076) | Operator sees only fulfilled_sale_id (legacy); can't see multi-line sales | S — read pedido.sales |
| Loyalty impact visualization | "Este pedido le sumó X puntos" | XS — query ledger + render |
| Link to customer detail | Currently only shows name + phone | XS — `/clientes/{customer_id}` link |

### /eod (cierre diario)

| Gap | Impact | Cost |
|---|---|---|
| Weekend-batch range | Phase 11 ships migration 077 (pedido_event) but template doesn't render batch-mode UI yet | M — UI |
| KPI summary inline | Operator sees sales/cost of the day BEFORE ticking all-done | S — embed kpi-row |

### /recibo

| Gap | Impact | Cost |
|---|---|---|
| Pedido fulfillment link | If sale came from a pedido, link both directions | S — read sale.linked_pedido_id |

### /pedidos (list)

| Gap | Impact | Cost |
|---|---|---|
| Loyalty points indicator | Operator sees pedido summary but not impact on customer points | XS |

## Pre-existing failures (baseline)

| Test | Why failing | Action |
|---|---|---|
| `test_supplier_delete_audited` | Audit row missing on supplier delete | Fix audit hook (small) |
| `test_nav_02_ops_mounted_by_default_in_production_mode` | Nav not showing /ops link in prod | Fix nav config (small) |
| `test_d17_merma_uses_saskia_combo_for_recipe_and_ingredient` | Merma combo still legacy | Replace (medium) |
| `test_currency_drift_lint` | Hardcoded currency strings in templates | Replace with fmt helper (medium) |
| `test_kyrian_loyalty_balance_matches_ledger` | Order-dep: loyalty balance ≠ ledger sum | Skip / fix isolation |

## Proposed upgrade plan (Tiers 6-7)

### Tier 6 — "Complete the page" (4 flows)

Small, independent gaps. Each is XS-S effort. Goal: every recent flow is visible from every page it logically belongs on.

| Tier | Page | Flow | Effort |
|---|---|---|---|
| 6.1 | `/clientes` list | "Crear pedido" row action + Suscripción column + last-purchase column | XS |
| 6.2 | `/clientes/{id}` detail | Pedido timeline + "Pedir de nuevo" CTA + recent product mix | M |
| 6.3 | `/pedidos/{id}` | Linked sales list (migration 076) + loyalty impact + customer link | S |
| 6.4 | `/pedidos/nuevo` | Tier display + suscrip prefill | S |

### Tier 7 — "Cross-page glue" (4 flows)

Each bridges two pages that already have half the flow. Goal: operator can complete multi-page tasks without retyping.

| Tier | Flow | Pages | Effort |
|---|---|---|---|
| 7.1 | "Convertir venta → pedido" button | /ventas → /pedidos/nuevo | L |
| 7.2 | Sugerencias on cliente detail (click-to-apply) | /clientes/{id} → /ventas | M |
| 7.3 | Loyalty impact visualization | /pedidos/{id} + /recibo | XS |
| 7.4 | Birthday/upcoming lapsed card | /inicio | M |

### Tier 8 — "Observability + UX polish" (open from earlier)

| Tier | Item | Effort |
|---|---|---|
| 8.1 | Sentry SDK + DSN | M |
| 8.2 | Weekly email digest | L |
| 8.3 | Enrollment chart on /inicio | M |
| 8.4 | Mobile-tuned KPI row | S |
| 8.5 | /eod KPI summary inline | S |
| 8.6 | Weekend-batch EOD range UI | M |

### Tier 9 — "Fix baseline" (the 5 pre-existing failures)

| Test | Effort |
|---|---|
| `test_supplier_delete_audited` | XS |
| `test_nav_02_ops_mounted_by_default_in_production_mode` | XS |
| `test_d17_merma_uses_saskia_combo_for_recipe_and_ingredient` | M |
| `test_currency_drift_lint` | M |
| `test_kyrian_loyalty_balance_matches_ledger` (order-dep) | S |

## Recommendation

Order by impact × effort:

1. **Tier 6 (4 flows, ~3 hours)** — closes the most user-visible gaps. Each is independent so safe to ship incrementally.
2. **Tier 9 (5 fixes, ~2 hours)** — clears the failing-test signal that's been blocking confidence in deploys.
3. **Tier 7 (4 flows, ~6 hours)** — bridges between pages; the operator UX win is biggest here.
4. **Tier 8 (polish, ~6 hours)** — defer to a follow-up window.

Total: ~17 hours. Tier 6 + 9 ship in this turn.
