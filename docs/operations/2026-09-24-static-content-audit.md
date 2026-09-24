# Static Content Audit — Saskia RMS

**Author:** Hermes Agent (MiniMax-M3)
**Date:** 2026-09-24
**Audience:** Kiki, Saskia, future agents
**Scope:** Identify hardcoded values across `app/` that should live in the database.
**Outcome:** Implement highest-impact fixes; mark the rest for follow-up.

---

## TL;DR

The codebase is mostly well-factored (36 DB tables already, including a flexible `SettingsKV` key/value store). But **5–7 classes of hardcoded data remain** that prevent operators (Saskia, Kiki) from configuring the system without a code deploy. The biggest offenders:

| # | Hardcoded in | Severity | Effort | Fix |
|---|---|---|---|---|
| 1 | `product_category_options` (13 items) | **High** — duplicated, blocks adding categories without code change | Small | Move to `Category` table |
| 2 | `recipe_family_options` (13 items) | **High** — duplicated in `receta_form.html` line 53 | Small | Move to `RecipeFamily` table (or reuse `Category`) |
| 3 | `product_tag_options` + `dietary_tag_options` | **High** — duplicated, identical | Small | Already have `Tag` + `TagLink` tables — use them |
| 4 | `* 3` markup (Python × 1, JS × 2) | **Medium** — affects pricing | Small | Move to `SettingsKV` key `pricing.suggested_markup` |
| 5 | Unit list (`g`, `kg`, `ml`, `und`…) | **Medium** — already an Enum, but UI shows static | Small | Add `unit_options()` helper from `Unit` enum |
| 6 | Channel list (mostrador, delivery, whatsapp) | **Medium** — affects sales reporting | Medium | Move to `Channel` table |
| 7 | Payment method list (efectivo, transferencia…) | **Medium** — affects bank reconciliation | Medium | Move to `PaymentMethod` table |
| 8 | Email/WhatsApp copy templates | **Low** — copy is Spanish, not configurable today | Large | Move to `MessageTemplate` table + editor UI |
| 9 | Footer text ("Sistema local · 2026") | **Low** — branding | Small | Move to `SettingsKV` key `branding.footer` |
| 10 | Timezone (`America/Asuncion`) | **Low** — single-tenant today | Trivial | Move to `SettingsKV` key `locale.timezone` |

---

## Detailed findings

### 1. Product categories (13 hardcoded items)

**Location:** `app/templates/_components/tags.html` lines 9–24

```jinja
{% macro product_category_options() %}
  {% set result = [
    "Panadería", "Pastelería", "Dulces", "Bollería", "Bebidas",
    "Lácteos", "Salados", "Congelados", "Especiales", "Temporada",
    "Sin TACC", "Vegano", "Light",
  ] %}
```

**Issue:** When Saskia wants to add a new category (e.g., "Tartas"), she must edit this file, push a PR, deploy. Slow.

**Fix:** Add a `Category` table with `(id, name, scope)` where `scope` ∈ `{'product', 'recipe_family', 'both'}`. The `product_category_options()` macro becomes a Jinja loop over `categories | where(scope in ('product','both'))`.

---

### 2. Recipe families (13 hardcoded items, **DUPLICATED**)

**Location A:** `app/templates/_components/tags.html` lines 28–43
**Location B:** `app/templates/receta_form.html` line 53 (literal `{% for fam in ['Panadería', 'Pastelería', 'Bollería'... %}`)

Two sources of truth. Adding a family requires editing both files.

**Fix:** Same `Category` table, `scope = 'recipe_family'` or `'both'`. `receta_form.html` line 53 becomes `{% for fam in recipe_families %}` where `recipe_families` is passed from the route.

---

### 3. Dietary tags (13 hardcoded items, **DUPLICATED in tags.html**)

**Location:** `app/templates/_components/tags.html`
- `product_tag_options()` lines 45–64
- `dietary_tag_options()` lines 66–85

These two lists are **byte-identical**. Should be one function. The codebase already has a `Tag` table (`app/rms/models.py`) with `kind ∈ {'product', 'ingredient', 'recipe'}` — exactly the right shape.

**Fix:** `dietary_tag_options()` becomes `{% for tag in dietary_tags %}` where `dietary_tags = session.execute(select(Tag).where(Tag.kind == 'product')).scalars()`. Plus a one-time `ensure_starter_tags()` call at boot (the helper already exists in `app/rms/tags.py` line 115).

---

### 4. Pricing markup `* 3` (hardcoded in **3 places**)

**Locations:**
- `app/routers/recipes.py:514–519` — Python backend
- `app/templates/producto_form.html:319–320` — JS live calc
- `app/templates/receta_form.html:759` — JS escandallo calc

All three compute `cost * 3` as the suggested retail price. Change to 2.5× → must edit 3 files. Risky.

**Fix:** Single source via `SettingsKV`:
- Key: `pricing.suggested_markup`
- Value: `{"multiplier": 3.0, "round_to_gs": 1000}`
- Backend reads it; a small `/api/settings/pricing-markup` GET endpoint serves the value to JS.
- A `/settings` page lets Saskia change it without a deploy.

---

### 5. Unit list (already enum, but UI is hardcoded)

**Location:** `app/rms/units.py` (the `Unit` enum)
**Usage:** UI selects `<option>g</option>` etc. in `receta_form.html` line 113+

The Python side enforces unit discipline well (per `app/rms/AGENTS.md` rule: "Never store units as free-text in DB"). But the UI dropdowns hardcode `g`, `kg`, `ml`, `l`, `und`, `docena`, `porción`. Adding a unit (e.g., "oz") requires code change.

**Fix:** Expose `app/rms/units.py:Unit` members through a `unit_options()` Jinja macro that loops the enum. Adding a unit = 1-line edit + Enum import.

---

### 6. Sale channels (mostrador, delivery, whatsapp)

**Locations:**
- Backend: probably in sales router (filter_by_channel logic)
- UI: filter dropdowns on `/ventas`, `/pedidos`

Not yet searched exhaustively — see **Open finding** below.

**Fix (when fixed):** `Channel` table with `(code, label, is_default, sort_order)`. Channels: `mostrador`, `delivery`, `whatsapp`, `pedidosya`, `web`, etc. Already used in `app/routers/herebus.py:261` via `SettingsKV["channels_margins"]` JSON — so the pattern is established; just lift it to first-class.

---

### 7. Payment methods (efectivo, transferencia, tarjeta, tigo_money)

**Locations:** search needed — likely in `app/routers/ventas.py` and `/banco` UI.

**Fix (when fixed):** `PaymentMethod` table with `(code, label, requires_reference, fee_pct)`.

---

### 8. Email / WhatsApp message templates

**Locations:** Static copy in `app/routers/pedidos.py`, `/bank`, `/notifications`.

**Fix (longer term):** `MessageTemplate` table with `(channel, key, subject_es, body_es, body_en?)`. UI in `/settings/templates` lets Kiki edit copy without code deploy. Russian/Spanish/English future-proof.

**Priority:** Low — these are touched rarely, and copy is hard to get right without designer review.

---

### 9. Branding strings (footer, header copy, login page text)

**Locations:**
- `app/templates/login.html:16–17` — "Saskia RMS / Panadería / Bakery — Sistema de gestión"
- Footer `app/templates/base.html` — "Sistema local · 2026"
- Brand accent color in CSS (e.g., `--color-accent: #f97316`)

**Fix:** `SettingsKV` keys:
- `branding.business_name` — "Saskia RMS"
- `branding.tagline` — "Panadería / Bakery — Sistema de gestión"
- `branding.footer` — "Sistema local · 2026"
- `branding.accent_color` — "#f97316"
- `branding.logo_path` — relative path to `/static/uploads/`

`base.html` and `login.html` read these. Operators control branding from `/settings/branding`.

---

### 10. Timezone (`America/Asuncion`)

**Location:** 9 files. `app/rms/config.py`, `app/rms/db.py`, `app/rms/models.py`, `app/rms/settings.py`, `app/rms/settings_original.py`, `app/routers/produccion.py`, `app/rms/AGENTS.md`, `CRUD_FORM_MAP.md`, `SASKIA_BACKEND_AUDIT_2026-09-22.md`.

**Fix:** `SettingsKV` key `locale.timezone`. Most usages should go through `app/rms/timezone.py:ASUNCION_TZ` which reads `SettingsKV` once at startup with fallback.

**Priority:** Low — single-tenant today, the only operator is in Paraguay.

---

## What's already DB-driven (do NOT touch)

| Already good | Where |
|---|---|
| Tags | `Tag` + `TagLink` (35 starter tags seeded) |
| Customers | `Customer` table |
| Suppliers | `Supplier` table |
| Delivery zones | `DeliveryZone` table |
| Waste logs | `WasteLog` table |
| Recipes | `Recipe` + `RecipeLine` |
| Sales | `Sale` + `SaleStockMove` |
| Compliance info | `ComplianceInfo` table |
| Production plans | `ProductionPlan` + templates |
| Units | `Unit` enum (storage), just needs UI macro |

---

## Implementation plan (ordered by ROI)

### Phase 1: Catalog table for categories + families + tags (this session)
1. Add migration creating `category` table (`id, name, scope, sort_order`)
2. Add `Category` model + CRUD helper
3. Seed with current hardcoded values (13 categories, 13 families, deduplicated)
4. Replace `product_category_options()` and `recipe_family_options()` macros with DB-driven loops
5. Remove the duplicate inline list in `receta_form.html` line 53
6. Replace `product_tag_options()` and `dietary_tag_options()` with DB-driven loops over `Tag` table
7. Add `/settings/categories` CRUD page so Saskia can add/edit categories without deploy

### Phase 2: Pricing settings via SettingsKV (this session)
1. Seed `SettingsKV["pricing.suggested_markup"] = {"multiplier": 3.0, "round_to_gs": 1000}`
2. Add `/api/settings/pricing-markup` GET endpoint
3. Update `app/routers/recipes.py:519` to read from `SettingsKV`
4. Update `producto_form.html` and `receta_form.html` JS to fetch from endpoint
5. Add UI control in `/settings/pricing` for multiplier

### Phase 3: Units enum exposure (next session)
1. Add `unit_options()` Jinja macro that loops `Unit` enum
2. Replace hardcoded `<option>` tags in `receta_form.html` and `producto_form.html`
3. Update `IngredientPurchaseEditModal` and other forms

### Phase 4: Channels and payment methods (next session)
1. Add `Channel` table + seed (mostrador, delivery, whatsapp, pedidosya, web)
2. Add `PaymentMethod` table + seed (efectivo, transferencia, tarjeta, tigo_money)
3. Update sales router + filters to use these tables

### Phase 5: Branding + locale (later)
1. Add `SettingsKV` keys for branding
2. Add `/settings/branding` page
3. Move timezone to `locale.timezone` SettingsKV key

### Phase 6: Message templates (when Kiki asks for it)
1. Add `MessageTemplate` table
2. Add `/settings/templates` editor

---

## Open findings (need a deeper sweep)

- [ ] Where exactly are `Channel` strings used in the sales router? (search `/ventas` filter)
- [ ] Where exactly are `PaymentMethod` strings used? (search `/banco`)
- [ ] Are there hardcoded image placeholder URLs? (search `placeholder.com`, `via.placeholder`)
- [ ] Are there hardcoded "lorem ipsum" or example SKUs in seed scripts?
- [ ] What hardcoded Spanish copy strings live outside `templates/`? (audit error messages in `app/rms/errors.py`)

---

## Estimated impact

| Phase | Effort | Operator benefit |
|---|---|---|
| Phase 1 (catalogs) | 4 hours | Saskia can add categories/tags from UI |
| Phase 2 (markup setting) | 1 hour | Change markup from 3× to 2.5× without deploy |
| Phase 3 (units macro) | 2 hours | Adding a unit doesn't require code review |
| Phase 4 (channels + payments) | 4 hours | Cleaner sales reporting |
| Phase 5 (branding) | 2 hours | Re-brand without code change |
| Phase 6 (templates) | 8 hours | Kiki edits copy from UI |

Total: ~21 hours to make the system fully DB-configurable without code deploys.

---

## Risk notes

- **Don't migrate what already works.** The Tag system exists; just use it. Don't create a parallel `DietaryTag` table.
- **Don't break tag IDs.** Existing products/recipes have tag links by `tag_id`. Keep the `Tag` schema stable.
- **SettingsKV is JSON.** That's fine for small config but not for high-frequency queries. Catalog tables (Phase 1) should be real SQL tables with FKs.
- **Seeding is idempotent.** Use `ensure_starter_*` helpers that already exist; never `INSERT INTO ... ON CONFLICT` in migration files.
- **Backwards-compat for missing data.** If `SettingsKV["pricing.suggested_markup"]` is missing, default to 3.0 (today's behavior). Don't break the system during the rollout.

---

## Cross-references

- `app/rms/models.py` — 36 tables including `SettingsKV`, `Tag`, `TagLink`
- `app/rms/tags.py:115` — `ensure_starter_tags()` helper
- `app/rms/AGENTS.md` — Money, unit, time, recipe, stock rules
- `AGENTS.md` — Repo-level build instructions
- `app/CHANGELOG.md` — Change tracking
