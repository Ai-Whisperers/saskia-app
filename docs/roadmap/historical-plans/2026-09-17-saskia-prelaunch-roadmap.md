# Saskia RMS — Pre-Launch Roadmap

**Status:** plan · **Author:** Iván (via Hermes) · **Date:** 2026-09-17
**Context:** Saskia has 20 products, 12 recipes, 30 ingredients seeded but has never used the app. We are zero-friction conversion setup only.

## Goal
Move Saskia from "demo data inside an app I haven't tried" → "I sold my first real muffin to a real person, recorded it, took efectivo via QR, sent the receipt to my brother."

## Constraints
- Single tenant, single operator (Saskia) + family (Ivan)
- Paraguayan guaraníes (Gs.), Asunción timezone
- WhatsApp & in-person are the sales channels. PedidosYa is opt-in and low-volume
- Free tier Render + Supabase (pauses after 7 days idle) — operator must keep an eye on it
- Demo user (saskia@paragu-ai.com, ivan@paragu-ai.com) is the family login — DO NOT block

## Phases & Status

### Phase 1 — Clean state & payment fields (this session)
- [x] Wipe 919 synthetic sales + stock moves + audit rows (no demo-user block, family keeps using same accounts)
- [x] Add `efectivo | transferencia | qr | tarjeta | otro` payment methods, default efectivo
- [x] Add `channel` column on Sale (mostrador | whatsapp | pedidosya | monchis)
- [ ] Vendor-decision: full PedidosYa API integration vs manual entry (operator chose: manual; revisit if 5+/day)

### Phase 2 — Customer picker overhaul (in flight)
- [running] Modal-based customer picker on `/ventas`
- [running] Search by name/phone/cedula/email/notes (any field)
- [running] Add `cedula` column on Customer (CI/RUC)
- [running] "+ Nuevo cliente" popover inline
- [running] Customer hint: "Cliente: María T. — 12 visitas, Gs. 1.2M lifetime"

### Phase 3 — Pedidos (pre-orders) (next)
- [ ] `Pedido` model (id, customer_id, promised_date, channel, status, payment_intent, notes)
- [ ] PedidoLine: (pedido_id, product_id, qty, unit_price_gs)
- [ ] `/pedidos` list with 3 sections: Hoy/Mañana, Esta semana, Pendientes viejos
- [ ] Pedido → Sale fulfillment button (creates Sale row, decrements stock, awards loyalty)
- [ ] Public pickup-share link `/p/{token}` (WhatsApp-ready)

### Phase 4 — Operator dashboard polish (next)
- [ ] Stock-confidence LED (green/amber/red)
- [ ] "Coffee regulars" card on dashboard
- [ ] 7-day `/produccion` plan view
- [ ] Weekend batch `/eod?start=YYYY-MM-DD&end=YYYY-MM-DD`

### Phase 5 — Excel bulk update (next)
- [ ] `/excel/importar?mode=PATCH` — Productos/Clientes/Ingredientes/Recetas by name match
- [ ] `/excel/plantilla` — prefilled .xlsx with "fill me values" defaults
- [ ] Per-row validation + warnings surfaced
- [ ] Quick receipt-of-stock: `/inventario` inline `+ qty` form

### Phase 6 — Customer retention (deferred)
- [ ] Customer profile page (`/clientes/{id}`) with photo, notes, deal-suggestion text
- [ ] Lifetime spend, top products, visit frequency
- [ ] Vendor-decision: loyalty_points vs manual notes vs auto-suggest rules

### Phase 7 — PedidosYa / Monchis (deferred until 5+ orders/day)
- [ ] PedidosYa Partner API webhook receiver (OAuth + status callback)
- [ ] Channel-aware cost columns (gross vs net after commission)
- [ ] Per-channel dashboard: "PedidosYa orders this week / margin after commission"

## What's out of scope
- Multi-branch / multi-tenant (single shop only)
- Online storefront / customer-facing checkout (WhatsApp is the storefront)
- Inventory ML forecasting (stock-confidence LED is enough)
- Loyalty points (operator chose "manual deal notes" tier — revisit when there's data)

## Operators-only admin

| Path | What |
|---|---|
| `/ops/reset-demo-data` | Wipe sales/stock_moves/audit_demo rows (operator-only, idempotent) |
| `/ops/pedidosya-config` | (later) OAuth setup, webhook secret, manual sync |
| `/excel/plantilla` | Download prefilled template |

## Risks

| Risk | Mitigation |
|---|---|
| Supabase pauses every 7 days idle | UptimeRobot pings `/healthz` every 5 min (already wired); consider Supabase Pro ($25/mo) |
| Cold-start Render 19s on first hit | UptimeRobot keeps container warm; `<60 queries` per dashboard render verified |
| Operator disappears | Sister takes over; family accounts shared; all docs in `docs/user-guide/` |
| Demo user password leak | README-only mention; password sync to Supabase via BWS Admin API only |

## What I can ship this session

| # | Phase | Effort | Owner |
|---|---|---|---|
| 1 | Phase 1: clean state + payment methods + channel | 1.5h | me, in-flight |
| 2 | Phase 2: customer picker overhaul | 2h | delegated (running) |
| 3 | Phase 3: pedidos model + list + fulfillment | 3h | me, after #2 |
| 4 | Phase 5: Excel PATCH + plantilla | 2h | me, after #3 |
| 5 | Phase 4: dashboard polish (stock LED + 7-day plan + weekend EOD) | 1.5h | me, after #4 |
| **Total** | | **~10h** | |
