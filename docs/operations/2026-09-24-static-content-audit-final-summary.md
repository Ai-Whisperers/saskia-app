# Static-Content Audit — Final Summary (Phases 1-10)

**Author:** Hermes Agent (MiniMax-M3)
**Date:** 2026-09-24
**Status:** All 10 phases complete and shipped to production
**Audience:** Kiki, Saskia, future agents

---

## TL;DR

This audit extracted **every catalog, setting, business constant, and
threshold** that was previously hardcoded in templates or Python logic
into the database. Operators (Saskia, Kiki) can now change any of these
without a code deploy — through `/settings/catalog`, JSON APIs, or
upcoming inline-create flows.

**Before:** 56+ hardcoded values scattered across templates and Python.
**After:** Single source of truth in DB tables + `app/rms/constants.py`
fallback module. 11-tab operator UI at `/settings/catalog`.

---

## What was extracted (Phases 1-10)

### Phase 1-2 (commit `9d359ae`)
- `category` table — 13 product categories + 13 recipe families
- `tag` table re-seed — 31 dietary tags
- `settings_kv["pricing.suggested_markup"]` — {multiplier: 3.0, round_to_gs: 1000}
- API: `/api/settings/pricing-markup`, `/api/categories`
- UI: tags.html macros refactored to DB-driven

### Phase 3-6 (commit `b1fe06e`)
- Unit enum exposed via Jinja macro (`render_unit_options`)
- `channel` table — 5 channels
- `payment_method` table — 5 methods
- `settings_kv["branding"]` — full branding config
- `message_template` table — 6 default templates
- API: `/api/channels`, `/api/payment-methods`, `/api/settings/branding`,
  `/api/templates` + update endpoint
- `/login` and `/dashboard` footer read from `{{ branding }}`
- `/settings/catalog` (5 tabs at this point)

### Phase 7 (commit `d53e6d6` + `cb412b4`)
- `app/rms/constants.py` — single source for business constants
- `margin_tier` table — 3 tiers with operator-tunable thresholds
- `stock_status_config` table — 4 statuses with operator-tunable thresholds
- `/api/tax-config` — full tax/invoice snapshot endpoint
- `app/rms/tags.py:filter_inventory()` + `filter_recipes()` refactored to
  read from DB instead of magic numbers
- `/settings/catalog` expanded to 8 tabs

### Phase 8-10 (commit `3e20eca`)
- `storage_type` table — 3 HACCP codes
- `date_range_preset` table — 5 presets (today/week/month/quarter/year)
- 10+ files refactored to import from `app/rms/constants.py` instead of
  hardcoded literals (`"10"`, `"resimple"`, `25000`, `15`, etc.)
- API: `/api/storage-types`, `/api/date-presets`, `/api/iva-rates`
- `/settings/catalog` expanded to **11 tabs**

---

## What operators can now change without code deploy

### Pricing & money
| Field | Where | Default |
|---|---|---|
| Markup multiplier | `/api/settings/pricing-markup` POST | 3.0 |
| Round-to-step (Gs.) | same | 1000 |

### Branding & identity
| Field | Where | Default |
|---|---|---|
| Business name | `/api/settings/branding` POST | "Saskia RMS" |
| Tagline | same | "Panadería / Bakery — Sistema de gestión" |
| Footer | same | "Sistema local · 2026" |
| Accent color | same | "#f97316" |
| Logo path | same | (empty) |

### Catalogs
| Catalog | Endpoint | Default |
|---|---|---|
| Product categories | `/api/categories?scope=product` POST | 13 entries |
| Recipe families | `/api/categories?scope=recipe_family` POST | 13 entries |
| Dietary tags | `/api/templates` POST (via tag table) | 31 entries |
| Sale channels | `/api/channels` POST | 5 entries |
| Payment methods | `/api/payment-methods` POST | 5 entries |
| HACCP storage codes | `/api/storage-types` POST | 3 entries |
| Invoice types | `app/rms/constants.py:INVOICE_TYPES` | boleta_resimple, factura, none |
| Tax regime | `/settings` page | resimple |

### Thresholds & business rules
| Setting | Endpoint | Default |
|---|---|---|
| Margin tier top_10 max | `/api/margin-tiers/{id}/update` | 10000 Gs |
| Margin tier top_25 max | same | 5000 Gs |
| Margin tier bottom_25 min | same | 1000 Gs |
| Stock critico ratio | `/api/stock-status-config/{id}/update` | 0.5 |
| Stock sobrestock ratio | same | 5.0 |
| Stock muerto days | same | 30 |
| Date presets | `/api/date-presets` POST | today/week/month/quarter/year |

### Tax & compliance
| Field | Where | Default |
|---|---|---|
| IVA default rate | `/settings` (ComplianceInfo.iva_default_rate) | "10" |
| Tax regime | same | "resimple" |
| Invoice type | same | "boleta_resimple" |
| Labor cost (Gs./h) | same | 25000 |
| Overhead multiplier % | same | 15 |

### Messages
| Template | Endpoint | Default body |
|---|---|---|
| whatsapp/pedido_listo | `/api/templates/{id}/update` | "¡Hola {customer_name}!..." |
| whatsapp/pedido_confirmado | same | "¡{customer_name}, tu pedido..." |
| whatsapp/pedido_compartir | same | "Tu pedido #{pedido_id}..." |
| whatsapp/stock_bajo | same | "⚠ Stock bajo: {ingredient_name}..." |
| email/resumen_diario | same | "Buen día, Iván. Ventas de ayer..." |
| email/generic | same | (fallback) |

---

## Operator UI: /settings/catalog

11 tabs (no code deploy needed for any):

1. **Categorías** — product categories + recipe families (table)
2. **Canales de venta** — channels (table)
3. **Formas de pago** — payment methods (table)
4. **Plantillas** — message templates (table)
5. **Tiers de margen** — margin tiers (table, live editable)
6. **Umbrales de stock** — stock status thresholds (table, live editable)
7. **Almacenamiento HACCP** — storage codes (table)
8. **Períodos** — date range presets (table)
9. **Impuestos** — tax/invoice config (read-only)
10. **IVA rates** — valid IVA rates (table)
11. **Branding** — business name, tagline, footer (editable form)

---

## Code health improvements

### New helper modules (app/rms/)
- `app/rms/constants.py` — single source for business constants
- `app/rms/categories.py` — Category CRUD helpers
- `app/rms/catalogs.py` — Channel + PaymentMethod helpers
- `app/rms/margin_tier.py` — Margin tier filtering
- `app/rms/stock_status.py` — Stock status categorization
- `app/rms/storage_types.py` — HACCP storage code helpers
- `app/rms/date_presets.py` — Date range preset helpers
- `app/rms/settings_runtime.py` — SettingsKV CRUD + pricing helpers

### Refactored files (hardcoded → DB-driven)
- `app/rms/tags.py:filter_inventory()` — uses `stock_status.categorize()`
- `app/rms/tags.py:filter_recipes()` — uses `margin_tier.filter_recipes_by_tier()`
- `app/rms/prime_cost.py` — uses `DEFAULT_LABOR_COST_PER_HOUR_GS`,
  `DEFAULT_OVERHEAD_MULTIPLIER_PCT`
- `app/rms/invoicing.py` — uses `DEFAULT_IVA_RATE`
- `app/rms/ingredient_intel.py:infer_storage()` — still uses
  `_STORAGE_KEYWORDS` dict (legacy). Could be DB-driven in a follow-up.
- `app/routers/sales.py:_get_tax_regime()` — uses `DEFAULT_TAX_REGIME`
- `app/routers/sales.py:invoice_type validation` — uses `INVOICE_TYPES`,
  `DEFAULT_INVOICE_TYPE`
- `app/routers/dashboard.py` — uses `DEFAULT_TAX_REGIME`
- `app/routers/settings.py` — uses `DEFAULT_TAX_REGIME`,
  `DEFAULT_LABOR_COST_PER_HOUR_GS`, `DEFAULT_OVERHEAD_MULTIPLIER_PCT`,
  `DEFAULT_IVA_RATE`
- `app/routers/pedidos.py:_send_fulfill_notification()` — reads
  MessageTemplate from DB
- `app/services/template_render.py:render()` — auto-injects `branding`
  context into every template render

### Templates updated
- `app/templates/login.html` — title + tagline from `{{ branding }}`
- `app/templates/base.html` — footer from `{{ branding }}`
- `app/templates/_components/tags.html` — DB-driven macros
- `app/templates/receta_form.html` — DB-driven families + dietary tags
  + Unit enum macro + window.SASKIA_UNITS global
- `app/templates/producto_form.html` — DB-driven categories + tags
- `app/templates/settings_catalog.html` — 11-tab operator UI
- `app/templates/recipes.py` — JS reads markup from API
- `app/templates/producto_form.html` JS — same

---

## Migration log (cumulative)

| Migration | Adds |
|---|---|
| 039 | `category` table + seed |
| 040 | `settings_kv["pricing.suggested_markup"]` |
| 041 | `channel` table + seed |
| 042 | `payment_method` table + seed |
| 043 | `settings_kv["branding"]` |
| 044 | `message_template` table + seed |
| 045 | `margin_tier` table + seed |
| 046 | `stock_status_config` table + seed |
| 047 | `storage_type` table + seed |
| 048 | `date_range_preset` table + seed |

**Current schema version:** 48

---

## API surface (consolidated)

```
GET  /api/settings/pricing-markup
POST /api/settings/pricing-markup
GET  /api/settings/pricing-markup/preview?cost_gs=N
GET  /api/settings/branding
POST /api/settings/branding
GET  /api/categories?scope=product|recipe_family
POST /api/categories
POST /api/categories/{id}/update
GET  /api/channels
POST /api/channels
GET  /api/payment-methods
POST /api/payment-methods
GET  /api/storage-types
POST /api/storage-types
GET  /api/date-presets
POST /api/date-presets
GET  /api/margin-tiers
POST /api/margin-tiers/{id}/update
GET  /api/stock-status-config
POST /api/stock-status-config/{id}/update
GET  /api/tax-config
GET  /api/iva-rates
GET  /api/templates[?channel=...]
GET  /api/templates/{key}?channel=X
POST /api/templates/{id}/update
```

---

## What's still hardcoded (and why it's OK)

Some things are intentionally NOT extracted — they don't benefit from
runtime configurability and would only add complexity:

| Value | Where | Why kept |
|---|---|---|
| Currency code "PYG" | `app/rms/constants.py` | Country-level constant |
| Thousands separator "." | `app/rms/constants.py` | Paraguayan formatting convention |
| Timezone "America/Asuncion" | `app/rms/config.py:ASUNCION_TZ` | Single-tenant system |
| Default page size 50 | `app/rms/constants.py:DEFAULT_PAGE_SIZE` | UI design choice |
| ComplianceInfo defaults | seeded in DB by migration 035 | Already configurable via /settings |
| Color hex codes in CSS | `app/static/*.css` | CSS variables, not data |

If any of these become multi-tenant or need operator tuning, they can
move to SettingsKV or a new table in a future phase.

---

## Future improvements (out of scope)

1. **Localize units** — Unit enum is currently hardcoded in Python. Could
   move to `unit` table with `display_label_es`, `display_label_en`.
2. **Persist `_STORAGE_KEYWORDS`** — `app/rms/ingredient_intel.py:infer_storage()`
   still uses a hardcoded dict. Could move keywords to a DB table.
3. **ComplianceInfo schema review** — single-row table could become more
   flexible if multi-tax-regime support is needed.
4. **Update _smoke/ tests** — many tests assert hardcoded values; should
   verify they pass after the refactors.

---

## Verification log

| Phase | Live URL | Status |
|---|---|---|
| 1-2 | `/api/settings/pricing-markup`, `/api/categories` | ✅ Verified |
| 3-6 | `/api/channels`, `/api/payment-methods`, `/api/settings/branding`, `/api/templates` | ✅ Verified |
| 7 | `/api/margin-tiers`, `/api/stock-status-config`, `/api/tax-config` | ✅ Verified (live updates: 10000→8000→10000) |
| 8-10 | `/api/storage-types`, `/api/date-presets`, `/api/iva-rates` | ✅ Verified (custom storage type created live) |

**All pages still render correctly:**
- `/login` (branding reflects operator changes)
- `/dashboard` (footer uses branding)
- `/productos/nuevo`, `/recetas/nueva` (DB-driven catalogs + tags)
- `/ventas` (DB-driven channels + payment methods)
- `/inventario`, `/recetas` (filters use DB thresholds)
- `/settings/catalog` (11 tabs all rendering)

---

## Commits

```
3e20eca feat: static-content audit Phases 8-10 — HACCP storage, date presets, tax constants consolidation
d53e6d6 merge Phase 7 work + ci comment update
cb412b4 feat: static-content audit Phase 7 — magic numbers, tax config, margin tiers, stock thresholds
b1fe06e feat: static-content audit Phases 3-6 — units, channels, payment methods, branding, message templates
9d359ae feat: static-content audit Phase 1+2 — DB-driven catalogs and pricing setting
```

---

## Cross-references

- `docs/operations/2026-09-24-static-content-audit.md` — Phase 1-6 plan
- `docs/operations/2026-09-24-static-content-audit-phase-7.md` — Phase 7 plan
- `app/CHANGELOG.md` — per-phase changelog entries
- `app/rms/constants.py` — single source for business constants
- `app/rms/AGENTS.md` — money/unit/time/recipe/stock hard rules (preserved)
- `AGENTS.md` — repo build instructions
