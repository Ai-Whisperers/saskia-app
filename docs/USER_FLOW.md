# Operator user-flow guide — Sazón RMS

> **Purpose**: a permanent repo to capture how the operator (cook / owner / panadero)
> moves through the system end-to-end, day by day. Use it to align new features,
> train new operators, and avoid drifting the UI without a clear story.
>
> **Last updated**: 2026-10-07 — after the notifications-collapse round.

---

## The four jobs-to-be-done

Every operator visit covers one of these jobs. Each maps to specific routes.

| # | Job | Question answered | Routes |
|---|---|---|---|
| **J1** | Plan production | "What should I bake today / tomorrow / next week / next month?" | `/dashboard`, `/produccion`, `/produccion/manana`, `/produccion/prep`, `/produccion/print` |
| **J2** | Execute production | "What did I actually bake? Burnouts, shortfalls, extras?" | `/produccion` (Shift mode), `/ventas/nueva`, `/inventario/movimientos` |
| **J3** | Restock & shop | "What ingredients am I missing? What do I need to buy?" | `/shopping`, `/inventario`, `/pedido_stock_preview` |
| **J4** | Audit + EOD | "Did anything go wrong today? Close the day." | `/eod`, `/eod/check`, `/eod/print`, `/auditoria`, `/produccion/accuracy` |

---

## The day in the operator's life

### 06:30 — Pre-shift glance (`/dashboard`)

Operator lands on the dashboard tile view. Big number cards tell the
story of the day. They see:
- **Today**: pedidos pendientes, ventas del día anterior,
  meta diaria, accuracy 7d
- **Inventory**: ingredientes bajos, products to buy
- **Money**: ventas del mes, top-3 productos
- **HACCP**: today's readings status (green / yellow / red dots)

If anything red, they click and jump into the relevant page.

### 06:45 — Plan today (`/produccion` for_date=today)

> **This is the central screen.** Roughly 30 read here per operator day.

The page renders the full plan for the **selected date** (default = today,
operator changes the date picker for tomorrow / a week from now).

**Top-of-page** (above the fold, no scrolling):
1. **KPI strip** (always visible, 4 cards): productos en el plan · lote total · pedidos comprometidos · % confianza
2. **One-line alerts** (always visible):
   - "🚨 Pedidos pendientes para hoy: Tenés N pedidos confirmados…"
   - "0 ingredientes bajos · 323 sugerencias de sustitución · Reponer ahora →"

**"Notificaciones" group** (collapsed by default — opens in a single click):

> **2026-10-07 redesign**: all eight notification cards are now wrapped
> in one outer `<details>` called "Notificaciones del día" with a header
> showing the active count + critical-icon. Each card inside is its own
> collapsible sub-block. Operator opens one to drill in; the others stay
> tucked away.

| Sub-card | When operator opens it |
|---|---|
| Pedidos pendientes (N) | Click "ver detalle" on a pedido to see its full body |
| Sustitutos sugeridos | Deciding whether to swap one unsavable for a substitute |
| Meta diaria · Real | Re-adjusting the daily target |
| HACCP latest (color dot) | Confirming freezer temperature is in spec |
| HACCP missing (N) | Registering the morning temp readings |
| Cómo se calcula | Once when they're curious about the math |
| Baja confianza (X) | Drilling into products they need to manually review |
| Ayer hiciste (N) | Comparing today vs yesterday as a backstop |

**Products table** (collapsed by default, expands to:
- Filters (allergens, source, status)
- 50 rows max per page
- Each row: receta · ★ quality · unidades sugeridas · +/override · hecho · sobrante · confianza · origen · [Receta · View · Hot]
- Override form: click the cell, type the new qty, Enter
- "💾 Guardar plan" button at the bottom)

**Ingredients table** — moved to its own place (see below).

### 08:30 — Switch to execute / Shift mode

Once they start baking, they click the **"Modo Shift"** toggle. The
products table now has a "Hecho" column where they type the actual qty
as they bake each batch.

The /produccion page has a POST /produccion/shift-execute endpoint
that records a unit-style "received" entry into SaleStockMove (or
SalesMovement — whichever was the actual model after the 092
migration that deprecated SaleStockMove). After saving, a green
toast appears:

> ✓ Turno guardado: N productos registrados en producción real.

…and the toast offers a quick path to log today's sales:

> "📝 Registrá una venta" → /ventas/nueva

### 09:30 — Restock check (`/shop` or `/shopping`)

> **2026-10-07 ask**: "somewhere to see all that is missing to go buy / update"

New page: **/shopping** (already exists at app/shopping.py + app/templates/shopping_list.html).

It shows:
- Ingredients grouped by **supplier**
- Severity (Falta = 0 stock, Justo = < 1 day of ventas, Suficiente)
- "Comprar" / "Mark as bought" / "Delete" actions per line
- Quick-add: "+ add a line not in the list"
- "Pull from production plan" auto-sync button

Operators can also reach it from the one-line alert:
> "Reponer ahora →" links to /shopping

### 10:00 — Recipe-portions view

> **Shipped 2026-10-07e**: `/produccion/prep-recipes` — the "weighing
> each recipe's ingredients" page the operator prints and takes to the bench.

For each recipe in today's plan, the page renders:
- Recipe name + link to `/recetas/{id}`
- Number of batches to make (= qty_to_produce / recipe.yield_qty)
- Per-ingredient scaled quantities (e.g. Harina: 4.5 kg, Manteca: 1.2 kg)
- Stock-on-hand vs needed (Falta / Justo / Suficiente)
- Severity band on each card (Falta first, then Justo, then Suficiente)
- Cumulative cross-recipe totals (sums per ingredient across all
  recipes — operator uses this to double-check `/shopping-list`)

Access from `/produccion` via the link card under "Ingredientes necesario"
(🍰 Por receta (pesar)).

### 17:00 — End-of-shift

Once sales are done, the operator clicks "📝 Registrá una venta" or
just goes to /ventas/nueva.

### 19:00 — End-of-day

Operator goes to **/eod** (End-Of-Day).

Renders an EOD checklist:
- HACCP missing readings? (block until all entered)
- Sales count for the day (vs last-7-day avg)
- Burnouts / shortfalls detected
- Merma (waste) outliers
- "Cerrar día" button → POST /eod/completar

After the day is closed:
- All shifts for that date become locked
- Production accuracy % is recalculated for the day
- /eod/print renders a printable close-of-day report
- "Anomalías del día" → /eod/anomalies/run runs a one-shot anomaly check

### Weekly / monthly review

| Cadence | Route | Purpose |
|---|---|---|
| **Weekly** | `/produccion/accuracy` | Per-day accuracy chart; pin products that consistently over/under |
| **Monthly** | `/reportes/cierre-mensual` | Closed-month totals: ventas, ventas, mejor/peor producto, merma real |
| **Ad-hoc** | `/auditoria` | Per-target log: who changed what, when |

### Planning further ahead

Operator wants to plan a week / month ahead?

- **Tomorrow**: `/produccion/manana` — uses DOW-aware forecast with a 12-week lookback + seasonal events. Operators override the qty by typing a number; the form posts to `/produccion/override`.
- **This week**: `/produccion` with the date picker, OR `/produccion/template/template`
  (templates_ops.py:123) — `/template/fork-week` copies last week into this week.
- **Next month**: there's no dedicated /produccion/month view today. The date
  picker accepts any date but the forecast is only as good as 84 days of history.
  **Gap to address**: a /produccion/month view that aggregates by week and shows
  monthly seasonal events would close this.

---

## Notifications collapse — the 2026-10-07 redesign

The pre-redesign layout had 8 separate notification cards stacked at the top of
/produccion, eating ~30% of the viewport on every load. The operator asked
("all of these notifications in a section together and make it all
collapsible with a title header etc") to bundle them.

**Old**:
```
┌──────────────────────────────────────────────────────────────┐
│ 🚨 Pedidos pendientes para hoy: Tenés 2 pedidos…              │
└──────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────┐
│ 📦 Pedidos pendientes (2)               [▼] clic para abrir  │
│  └─ Pedido #16 — Patricia Méndez · 11:00 …                    │
│  └─ Pedido #17 — Mauro Cáceres · 18:00 …                     │
└──────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────┐
│ ⚠️ 0 ingredientes bajos · 323 sugerencias…   [▼] clic…      │
└──────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────┐
│ Meta diaria: 102 · Real: 15 · 15%             [▼] clic…      │
└──────────────────────────────────────────────────────────────┘
…8 separate rows, each with their own border + triangle
```

**New** (this commit):
```
┌──────────────────────────────────────────────────────────────┐
│ 🔔 Notificaciones del día (8)             [▼] Ver todo       │
└──────────────────────────────────────────────────────────────┘
```

Operator clicks the header once → all 8 sub-cards expand in place.
Operator clicks again → all 8 collapse. Each sub-card keeps its own
left-border severity color so the operator still sees "4 warning,
2 info, 0 danger" at a glance even with the body hidden.

When all notifications are clean, the summary line shows "✓ 0 alertas
críticas · 1 info" in green. Operators can still see "all green"
status without expanding.

---

## Recipes + portions — the 2026-10-07 ask

> **Reorganize ingredients by recipe, with amounts & links to recipes.**

The current `Ingredientes necesarios` table is great for the
shopping list (organize by ingredient, see "what am I short on")
but useless for the kitchen bench (the operator wants to know
"for 6 batches of Sopa Paraguaya I need 4.5kg of harina, 1.2L of
milk, 18 eggs").

**New view**: `/produccion/prep-recipes`
**Or**: extend `/produccion/prep` (already exists at print_export.py:199)
with a "by recipe" tab.

Layout:
```
┌────────────────────────────────────────────────────────────┐
│ Sopa paraguaya ───────── 6 batches × Tamaño unit: 1.0 kg   │
│  Ver receta → link to /recetas/{id}                         │
├────────────────────────────────────────────────────────────┤
│  Harina de trigo             4.5 kg   (de stock: 18.0 kg)  │
│  Manteca                     1.2 kg   (de stock: 2.0 kg)   │
│  Cebolla                     0.6 kg   (de stock: 5.0 kg)   │
│  Queso Paraguay              0.9 kg   (de stock: 3.5 kg)   │
│  Huevo                       18 u     (de stock: 60 u)     │
├────────────────────────────────────────────────────────────┤
│ ⚠️ Atención: 0.3 kg de manteca shortfall si hoy resta  │
│    Sustituto sugerido: margarina (sim 0.85)                 │
└────────────────────────────────────────────────────────────┘
…one card per recipe in today's plan
```

This is the print-friendly view — the operator prints it, walks
to the bench, ticks off ingredients as they pull them from the
shelf.

---

## Soft-launched: where the operator lands first thing

The first decision the operator makes is which date to plan for.
Right now `/produccion` defaults to today. Should it default to
tomorrow? Tomorrow is when the operator is most likely planning.
For now: keep today default, add a prominent "📅 Planear mañana →
/produccion/manana" button in the topbar so the operator can jump
straight there.

---

## Open gaps

- ❌ **Plan by week / month** — only "tomorrow" has a dedicated route.
  Today / week / month fall back on the date picker.
- ❌ **Recipe-by-recipe prep view** — TODO.
- ❌ **EOD mobile** — the EOD checklist works on desktop but the HACCP
  readings form needs a mobile-friendly field layout for the freezer temp
  gun.
- ❌ **Operator audit trail** — we track every change in /auditoria but
  the operator never sees it. The differentiation needs to be "show me
  only what I changed today".

---

## Related plans

- `.hermes/plans/notifications-collapse-20261007.md` — design notes for
  this round
- `.hermes/plans/produccion-table-overhaul-20261007.md` — table sort /
  pagination / filtering
- `.hermes/plans/css-deep-audit-20261007.md` — color & contrast audit
- `docs/HOUR-LOG.md` — operator time-tracking
- `docs/TEST_ARCHITECTURE.md` — test pyramid