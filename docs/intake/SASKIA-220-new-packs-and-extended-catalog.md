# SASKIA-220: Add 5 new pack verticals + extend SeasonalEvent catalog to all tiers

**Date:** 2026-10-12
**Status:** drafted
**Author:** AIW Bot
**Estimate:** 5-7 days (2 days packs + 3 days catalog + 1 day tests)
**Sister tickets:** SASKIA-213 (shipped), SASKIA-215 (shipped), SASKIA-216 (drafted, SeasonalEvent model), SASKIA-217 (drafted, UI), SASKIA-214 (drafted, per-instance config), SASKIA-222 (new, multi-tenant per-tenant settings)
**Deep analysis:** `docs/operations/2026-10-12-multi-tenant-verticals-and-events.md`

## Why

Per the 2026-10-12 OOB ("la vaquita holnadesa iis a just the first client later we will have many more"), Sazon must onboard many tenants. The current `app/rms/seed/packs.py::PACKS` has **11 packs** covering the mainstream food verticals (Café, Catering, Comedor, Empanadas, Hamburguesería, Heladería, Oriental, Panadería, Parrilla, Pastelería, Pizzería). The PY food market has **5+ more verticals with real demand** that aren't covered:

1. **Food Truck / Móvil** — Don Cocido Py is the example; growing vertical; needs mobile inventory
2. **Quiosco / Minimarket / Almacén** — 89% aplican innovación, the most common PY small biz
3. **Chipería / Almidón** — Eusebio Ayala is the "capital del chipá", Ña Nena = embajadora nacional
4. **Pastelería Industrial / Fábrica** — Alberdin (70 años) + franchises = the B2B side
5. **Cervecería / Bar / Pub** — the only one for alcoholic beverages; needs liquor license flow

And the SeasonalEvent catalog (SASKIA-216) covers only the **tier 1 universal** events (~44 event types). The per-pack vertical events (Día de la Pizza, Día de la Empanada, Día del Helado Gratis, etc.) are **not yet in the DB** even though they drive significant demand.

## What

### Part A: Add 5 new packs to `app/rms/seed/packs.py::PACKS`

Each new pack follows the **same structure as the existing 11**: PackData with suppliers, ingredients, recipes, categories, product templates. Estimated work per pack:

1. **Food Truck / Móvil** — 8-12 products (desayunos, meriendas, cocido, chipa, sándwiches, almuerzos agendados). Suppliers: panificadora local, chipería, yerba. Recipes: 8-15.
2. **Quiosco / Minimarket / Almacén** — 30-50 products (galletitas, bebidas, snacks, artículos de limpieza, yerba, tereré). Suppliers: mayorista, distribuidora. Recipes: 0 (mostly resale).
3. **Chipería / Almidón** — 5-10 products (chipá almidón, chipa so'o, chipa kesu, mbejú, sopa paraguaya, pan quesú). Suppliers: almidonera, quesera. Recipes: 5-10.
4. **Pastelería Industrial / Fábrica** — 15-25 products (ravioles, ñoquis, fideos, discos de empanada, milanesas, tortas congeladas). Suppliers: harinera, frigorífico. Recipes: 15-20.
5. **Cervecería / Bar / Pub** — 20-30 products (cervezas nacionales, artesanales, tragos, finger food, picadas). Suppliers: Cervecería Nacional, importadora, destilería. Recipes: 5-10 (picos, snacks).

Total: ~80-120 new products, ~30-50 new ingredients, ~30-50 new recipes, ~10-15 new suppliers.

### Part B: Extend the SeasonalEvent catalog (SASKIA-216) to all tiers

- **Tier 2 (per-pack vertical, ~30 events × 3 yrs = 90 rows)**: Día de la Pizza, Hamburguesa, Helado Gratis, Empanada, Café, Pastelería, Asado, Cervecería, etc.
- **Tier 3 (world gastronomy, ~50 events × 3 yrs = 150 rows)**: Día del Chocolate, Macaron, Tiramisú, Torta, Helado de Vainilla, etc.
- **Tier 4 (NL heritage extended, ~13 events × 3 yrs = 39 rows)**: Stroopwafel, Bitterbal, Poffertjes, Kruidnoten, Hagelslag.

All rows get the `relevance_tags` CSV set to the relevant pack slugs (e.g. `relevance_tags="panaderia,pasteleria"` for Día de la Galleta). Universal events (tier 1) have `relevance_tags=""`.

### Part C: New `_seed_seasonal_events()` in `app/rms/seed/sazon.py`

Move the tier 1 seeder from SASKIA-216 into the full tier 1+2+3+4 seeder here. Total catalog after this ticket: **~411 rows** (137 distinct event types × 3 years).

### Part D: Tests

- `tests/test_seed_5_new_packs.py` — verify each new pack seeds correctly
- `tests/test_seasonal_events_per_pack.py` — verify per-pack relevance_tags filter works
- `tests/test_seasonal_events_holidays.py` — verify tier 2/3/4 dates are correct (spot-check 20 events against web sources)
- All existing 41+ tests must still pass

## Out of scope (deferred)

- **SASKIA-221** (new) — Multi-tenant per-tenant settings: each tenant has a `country`, `pack`, `relevance_tags` filter. The SeasonalEvent catalog queries use this. 4-6h.
- **SASKIA-217** — `/admin/seasonal-calendar` UI page. Already drafted.
- **SASKIA-219** — Annual roll-forward cron for movable dates.
- **SASKIA-218** — `TenantSeasonalEventOverride` table.

## Risks

1. **Pack data quality**: 5 new packs × 80-120 products each = ~500-600 product rows. Some will be wrong (sized wrong, missing cost data). Mitigation: generate from small data dicts + loops, not hand-written 500 lines.
2. **Catalog accuracy**: ~280 new rows for tier 2/3/4, ~30% of dates are "approximate" (no fijo in source). Mitigation: mark them `recurrence="mobile"`, `impact_tag="low"`, `impact_score=0.3` so operators know.
3. **Multi-tenant complexity**: the new packs add 5 `pack_slug` values; existing `relevance_tags` filters need updating. Mitigation: the filter is `LIKE '%pack_slug%'`, so existing empty-string rows (universal) automatically show to all 16 packs.
4. **Storage growth**: ~411 rows in `seasonal_event` is small. Indexes on `(country, slug, event_date)` and `relevance_tags` are enough.

## Acceptance

- `len(PACKS) == 16` (was 11)
- `len(SeasonalEvent.query.all()) == 411` (was 132 from SASKIA-216)
- All 5 new packs: `seed_pack(session, "Food Truck / Móvil")` etc. returns `PackReport` with products+ingredients+recipes counts > 0
- All 41 existing tests + 4 new test files = ~50 tests pass
- `make ruff` + `make format-check` clean
- CHANGELOG.md entry per AGENTS.md rule 35

## Reference

- **Deep analysis**: `docs/operations/2026-10-12-multi-tenant-verticals-and-events.md` (the full per-pack research with sources)
- **SASKIA-216 (parent)**: `docs/intake/SASKIA-216-seasonal-event-model.md` (the model + tier 1 seed)
- **SASKIA-217 (sister)**: `/admin/seasonal-calendar` UI (drafted)
- **OOB-2026-10-12**: "the website of sazon should load all of the thigns la vaquita holnadesa iis a just the first client later we will have many more"
