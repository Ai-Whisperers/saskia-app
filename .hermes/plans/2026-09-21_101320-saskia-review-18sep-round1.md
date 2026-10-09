# Saskia RMS — Round 1 review (Thu 18-sep 2026)

**Date:** 2026-09-21
**Author:** Hermes Agent (Ivan)
**Branch:** `feat/rms-fase1-review-round1`
**Deploy target:** hosted (`saskia-rms.paragu-ai.com`, Render + Neon)
**Source:** `Downloads/saskia rms first review thursday 18_09.docx`

## Budget

| Bucket | h |
|---|---:|
| Scope tickets (T1–T9) | 18 |
| Q1=(c) restock + price history + reports + insight | 10 |
| Q2=(c) full calendar dashboard | 10 |
| Q3=(a) forecast_source translate + override | 2 |
| **TOTAL** | **40** |
| PDF contingency | 27 |
| **Overflow beyond contingency** | **13** |
| PDF total budget | 97 |
| Headroom to §7 | 57h |

**Status:** orange. Inside 97h PDF total; **13h over the 27h contingency** — flag to K.W. on completion, no §7 conversation yet.

## Phasing

Phase-grouped per `saskia-rms-engagement` skill. Each phase = 1 implementer subagent + 2-stage review (spec + quality, in parallel). TDD within phases. Hour-log row on first commit per phase.

### Phase A — Quick wins + nav cleanup (4h)

Small, low-risk; clear the easy items first so we have a clean baseline to test the bigger ones against.

- **T2** Hide `/auditoria` + `/ops/status` from main nav (keep URLs working). 0.5h
- **T3** `/produccion` "Ver receta" button → `/recetas/{id}/editar` instead of `/productos/{id}/editar`. 1h
- **T4** Pedidos status filter UI on `/pedidos` (terminados / pendientes). 1.5h
- **T7** `/settings` form polish — dropdowns + a11y + visual-noise cut. 2h *(includes the "avoiding visual noise" guideline applied across the page)*

**Subtotal:** 4h

### Phase B — Schema additions (8h)

Two new tables: `ingredient_price_event` (Q1) and (no new table for Q2, but recipe line `unit` column). Migrations.

- **T1** Recipe line `unit` selector — schema v5 adds `line_unit` to `recipe_line`. Form: grams / kg / ml / l / und dropdown next to qty input. Update `RecipeLine` model, recipe form, recipe router, costing walk. 3h
- **Q1 core** Schema v4 `ingredient_price_event(ingredient_id, price_gs, recorded_at, source)` + helper to write on restock + read for history queries. 4h
- **Q2 prep** Calendar grid component shell (week + month views, navigation) — no business logic yet, just layout. 1h

**Subtotal:** 8h

### Phase C — Cross-cutting UX (6h)

- **T5** `/eod` includes production-completed summary (totals produced today, vs forecast). 2h
- **T6** "Merma de receta completa" flow on `/merma` — pick recipe + qty (whole batches) + reason, drops stock across all ingredients proportionally. 2h
- **T8** Cross-page consistency pass: dates (Asunción local), money format (Gs. 1.234.567 everywhere), sale vs report totals reconcile. 2h

**Subtotal:** 6h

### Phase D — Q1 (c) surface + Q2 (c) interactions + Q3 (a) (15h)

- **Q1 surface** Restock form captures `purchase_price_gs` per ingredient → writes `ingredient_price_event` + updates `Ingredient.purchase_price_gs`. `/inventario` row gets min/current/max strip + 90-day sparkline. `/reportes/precios` page with table + chart + CSV export. Dashboard insight "ingredientes con fluctuación > 20% último mes". 5h *(continues from Phase B schema work)*
- **Q2 finish** Full calendar dashboard: month view + week view + click-through to per-day plan. Per-day seasonal-multiplier editor. Per-product `manual` override on a day. 9h
- **Q3 (a)** Translate `forecast_source` enum to human-readable label + help tooltip + per-product override dropdown. 2h

**Subtotal:** 15h

### Phase E — QA + handoff (7h)

- **T9** QA plan deliverable + smoke + regression + functionality tests + user stories. 4h
- **Saskia review deployment** Manual deploy verification, screenshot pass on hosted, `/healthz` check. 1h
- **Buffer / cross-cutting fixes** Issues from review round. 2h

**Subtotal:** 7h

**Grand total:** 4 + 8 + 6 + 15 + 7 = **40h** ✓

## Tickets

### T1 — Recipe line `unit` selector (Phase B)

**What:** Recipe line currently has only `qty`. Add `line_unit` column (g / kg / ml / l / und) so Saskia can type `250 g` of flour and have it convert correctly against an ingredient stored in `kg`. Required by her bullet: "Se debe de poder agregar en gramos la cantidad".

**Acceptance:**
- Migration v5 adds `line_unit` to `recipe_line` (default = ingredient's unit)
- Recipe form has unit dropdown next to qty input per line
- Costing walk normalizes line qty into ingredient unit before computing cost
- Test: roundtrip — recipe with 250g flour + ingredient in kg computes the right cost
- Backward compat: existing recipes default to ingredient's unit

### T2 — Hide /auditoria and /ops/status from main nav (Phase A)

**What:** Remove the two `nav_link` calls in `app/templates/base.html`. Routes stay accessible if URL typed directly. Bullet: "no tener secciones que el cliente jamás usaría".

**Acceptance:**
- Topnav no longer shows Auditoría / Ops
- `/auditoria` and `/ops/status` still work (operator can bookmark)
- Test: topnav HTML doesn't contain "Auditoría" or "Ops" strings

### T3 — /produccion "Ver receta" routes to recipe edit (Phase A)

**What:** `app/templates/produccion.html` line 31 has `<a href="/productos/{{ r.product_id }}/editar">Ver receta</a>`. It should link to the recipe, not the product. Bullet: "Actualmente cuando se aprieta el cta de receta te manda a la pagina de producto".

**Acceptance:**
- Button text + href both target the recipe (need a `recipe_id` join on `ProductionRow`)
- If product has no recipe, button hidden
- Test: rendered HTML contains `/recetas/{id}/editar`

### T5 — /eod production-completed section (Phase C)

**What:** Today's EOD should surface how much production actually got done vs forecast. Bullet: "Al final del día debe registrarse cuánto de la producción se completó".

**Acceptance:**
- New section on `/eod` showing today's products planned (from forecast) vs completed (TBD — needs a `production_completion` event table OR reuse `merma` inverse)
- EOD "todo listo" badge requires production-completion entries
- Test: EOD progress includes production completion items

### T6 — Merma whole-batch flow (Phase C)

**What:** `/merma` currently only supports per-ingredient waste. Add whole-batch loss ("se me quemó toda la masa"). Bullet: "Aveces hay mermas de recetas completas".

**Acceptance:**
- `/merma` has two tabs/submodes: ingredient waste + whole recipe waste
- Whole-recipe merma: pick recipe + qty (in batch units) + reason → drops stock across all ingredients proportionally, records event
- Test: merma of 2x batch of "Muffin x12" reduces flour/eggs/etc by 2x the recipe

### T7 — /settings form polish + visual-noise cut (Phase A)

**What:** Bullets: "Drop down menu little things, in settings" + "We are avoiding visual noise".

**Acceptance:**
- All `/settings` form widgets reviewed; dropdowns have proper `<label>`s, focus styles, no inline styles
- Visual noise pass on `/settings`: remove redundant badges, collapse similar rows, consistent spacing
- a11y: keyboard nav, ARIA labels on every input
- Test: axe-core snapshot on `/settings` shows 0 criticals

### T8 — Cross-page consistency (Phase C)

**What:** Bullet: "Debe coincidir con los registros de las demás páginas".

**Acceptance:**
- Date format uniform (Asunción local, `dd/mm/yyyy`)
- Money format uniform (`Gs. 1.234.567` everywhere — `m.gs()` macro audit)
- `/ventas` today's total = `/reportes` today's total = `/reportes/libro_ventas` filtered today
- Test: parametrized — pick 5 random days, check totals reconcile across all 3 pages

### T9 — QA plan (Phase E)

**What:** Bullet: "Crea y analiza todos los user cases y user stories y crea pruebas de QA correspondientas, para smoke testing, regression testing, functionality testing, etc".

**Deliverable:** `docs/qa/saskia-review-round1-qa.md` with:
- User stories per ticket (from Saskia's POV)
- User cases per page (click-throughs)
- Smoke test list (deploy-blocking)
- Regression test additions to `tests/`
- Functionality test additions to `tests/`

### Q1=(c) — Price history full surface (Phase B + D)

**What:** Bullets: "En inventario al hacer las compras… que le muestre al usuario el costo actual… fluctuación de precios… mejor precio de venta" + "Reponer y que acá se pueda actualizar con la lista de compras y los precios actuales".

**Acceptance:**
- Schema v4 `ingredient_price_event(id, ingredient_id, price_gs, recorded_at, source)` + migration
- `/reorder` restock form captures `purchase_price_gs` per ingredient → writes event + updates current
- `/inventario` row: min/current/max strip + 90-day sparkline
- `/reportes/precios` page: table of all ingredients with their history + line chart per ingredient + CSV export
- Dashboard insight: "X ingredientes subieron >20% último mes" (severity-warn card)
- Costing uses `last 30d avg price` (not current snapshot) for product unit cost
- Tests: roundtrip restock → event → sparkline data; fluctuation insight threshold

**Out of scope:** auto-recommend new `sale_price_gs` based on cost fluctuation. That's E11 food cost territory, separate ticket.

### Q2=(c) — Full calendar dashboard (Phase B + D)

**What:** Bullet: "Haz que sea un calendario ciclico, por semana… al introducir la cantidad que se va a producir e ingresar en la receta debe de estar multiplicado por la cantidad correcta".

**Acceptance:**
- `/produccion` gets a calendar navigation: today / week / month views
- Week view: 7-column grid (L-D), each cell shows day's products
- Month view: month grid with day-cell summary (top 3 products)
- Click any day → today's full plan (existing per-day view)
- Per-day seasonal-multiplier editor (cell dropdown: x1, x1.25, x1.5, x2, manual)
- Per-day per-product `manual` qty override
- Existing bug "cantidad × recipe" math: audit + fix (recipe qty already scales by qty_to_produce, but verify in test)

**Blocker:** T-0.1 (forecast_source clarification with Saskia) — non-billable WhatsApp, gates the per-day seasonal-multiplier editor. If Saskia clarifies before Phase D, no impact. If not, the override UI ships but the multiplier editor waits.

### Q3=(a) — forecast_source human-readable + override (Phase D)

**What:** Bullet: "Also que es forecast_source?".

**Acceptance:**
- `forecast_source` enum rendered as label: "rolling_14d_avg" → "Promedio 14 días", "seasonal_event" → "Evento estacional", "manual" → "Manual"
- Tooltip explaining each
- Per-product override dropdown on `/produccion` (per-day)

## Hour log seed

```
| Date       | Task | Hours | Bucket       | Notes                                |
|------------|------|-------|--------------|--------------------------------------|
| 2026-09-21 | T2   | 0.5   | scope        | Hide auditoria + ops from topnav     |
| 2026-09-21 | T3   | 1.0   | scope        | Ver-receta routes to recipe          |
| 2026-09-21 | T4   | 1.5   | scope        | Pedidos status filter                |
| 2026-09-21 | T7   | 2.0   | scope        | Settings polish + visual-noise cut   |
| 2026-09-21 | T1   | 3.0   | scope        | Recipe line unit + grams input       |
| 2026-09-21 | Q1core| 4.0   | scope        | Schema v4 + restock write            |
| 2026-09-21 | Q2prep| 1.0  | scope        | Calendar grid component shell        |
| 2026-09-21 | T5   | 2.0   | scope        | EOD production-completed section     |
| 2026-09-21 | T6   | 2.0   | scope        | Merma whole-batch flow               |
| 2026-09-21 | T8   | 2.0   | scope        | Cross-page consistency               |
| 2026-09-21 | Q1sf | 5.0   | scope        | Surface + reportes/precios + insight |
| 2026-09-21 | Q2fin| 9.0   | scope        | Full calendar dashboard + interactions|
| 2026-09-21 | Q3   | 2.0   | scope        | forecast_source label + override     |
| 2026-09-21 | T9   | 4.0   | scope        | QA plan + tests                      |
| 2026-09-21 | DEP  | 1.0   | scope        | Hosted deploy verification           |
| 2026-09-21 | BUF  | 2.0   | scope        | Cross-cutting fixes from review      |
|------------|------|-------|--------------|--------------------------------------|
| TOTAL      |      | 40.0  |              |                                      |
| SCOPE      |      | 40.0  |              |                                      |
| CONTINGENCY|      | 0     |              | all 27h absorbed                     |
| OVERFLOW   |      | 13.0  | (against 27) | flag to K.W.                         |
```

## Deploy

- Branch `feat/rms-fase1-review-round1` → PR to `main` → auto-deploy to Render
- Manual verification on hosted before marking each phase done
- No force-pushes. Conventional commit prefixes per phase (`feat(nav):`, `feat(schema):`, etc.)

## Risks

- **T-0.1 blocker on Q2** — if Saskia doesn't clarify `forecast_source` semantics before Phase D, the seasonal-multiplier editor waits. Other Q2 work proceeds.
- **Render free-tier spin-down** — first deploy may be slow. Use UptimeRobot per `render.yaml` comments.
- **Schema v4 + v5 in one engagement** — both migrations need ordered execution; v5 backfills `line_unit` from ingredient's unit (no destructive change).
- **Subagent timeout false alarm** — per `saskia-rms-engagement` skill, 8min "no progress" doesn't mean failure. Check `git log` + tests before re-dispatching.