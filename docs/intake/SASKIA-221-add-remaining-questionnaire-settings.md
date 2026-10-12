# SASKIA-221: Add 25+ remaining settings (business_info, contact, marketing, etc.) to registry

**Date:** 2026-10-12
**Status:** drafted (post-OOB-2026-10-12 + post-HEREBUS-discovery)
**Author:** AIW Bot
**Estimate:** 2 days
**Sister tickets:** SASKIA-215 (shipped — first 6 new settings), SASKIA-213 (shipped), SASKIA-216 (drafted), SASKIA-220 (drafted)
**Source:** `docs/operations/2026-10-12-saskia-full-seed-data-plan.md` §4.11

## Why

The 2026-10-08 questionnaire has **22 sections, 70 filled answers**. SASKIA-215 added 6 of those (LOCATION, SEASONAL, RECIPE groups). The remaining 16 sections are **not yet in the settings registry** but the operator (Saskia) answered them:

- §1 Rubro, §3 Horarios, §4 Equipo, §7-10 Marketing/Redes, §11-12 Volumen, §13-15 Competencia/USP, §17-18 Operación, §19 Compliance, §20-22 Metas

The OOB said "the website of sazon should load all of the thigns" — without these settings, the website cannot show:
- Hours on the home page
- Marketing channels (Instagram, WhatsApp Business)
- Positioning (the "Dutch heritage" USP)
- Operations flags (is_solo, has_delivery)
- Compliance status (RUC, timbrado)
- Goals (target_revenue, target_customers)

## What

Add **25 new settings** across **8 new groups** to `app/rms/settings_registry.py`. Each new setting follows the existing pattern (`SettingsKV` model, KV-wins, read-time, no hardcode).

### New groups + settings

#### Group: `business_info` (3 settings)
- `business_info.category` (string, default="panaderia") — from §1.2
- `business_info.hours_weekday` (string, default="08:00-13:00") — from §3.1 (Mon-Sat 8-13)
- `business_info.hours_weekend` (string, default="cerrado") — from §3.1 (Sun cerrado)
- `business_info.staff_count` (int, default=1) — from §4.5 (Saskia sola)

#### Group: `contact` (5 settings)
- `contact.phone` (string, default="+595 991 683805") — from §2.3
- `contact.email` (string, default="La.vaquitaholandesa@gmail.com") — from §2.4
- `contact.whatsapp` (string, default="+595 991 683805") — from §2.7 (alias of sales.shop_whatsapp; canonical key is sales.shop_whatsapp)
- `contact.instagram_handle` (string, default="") — from §7 (TBD)
- `contact.facebook` (string, default="") — from §7 (TBD)

#### Group: `location` (extend, 4 new)
- `location.address_full` (string, default="Laguán Grande, Arquitectos, Calle 17, Asunción") — from §2.1
- `location.city` (string, default="Asunción")
- `location.department` (string, default="Central")
- `location.reference_point` (string, default="") — for the GPS description

#### Group: `marketing` (3 settings)
- `marketing.primary_channel` (enum: whatsapp|instagram|facebook|web, default="whatsapp") — from §7
- `marketing.has_whatsapp_business` (bool, default=false)
- `marketing.has_website` (bool, default=false) — from §7 (no website per §7)

#### Group: `targeting` (3 settings)
- `targeting.audience` (string, default="familias +上班族") — from §9
- `targeting.age_range` (string, default="25-55") — from §9
- `targeting.area` (string, default="San Lorenzo + Central") — from §10

#### Group: `positioning` (3 settings)
- `positioning.differentiator` (string, default="Dutch heritage + product quality") — from §13-15
- `positioning.unique_selling_points` (string, default="Recetas holandesas auténticas, ingredientes europeos importados (speculaas, ketjap manis, bladerdeeg, harina de centeno), chipa almidón tradicional, atención personalizada") — from §13-15
- `positioning.competitor_count` (int, default=0) — TBD by operator

#### Group: `operations` (5 settings)
- `operations.is_solo` (bool, default=true) — from §4.5
- `operations.has_cashiers` (bool, default=false) — from §4.5
- `operations.has_delivery` (bool, default=false) — from §17
- `operations.has_pickup` (bool, default=true) — from §17
- `operations.has_dine_in` (bool, default=false) — from §17

#### Group: `compliance` (3 settings)
- `compliance.ruc` (string, default="") — from §19 (TBD)
- `compliance.timbrado` (string, default="") — from §19 (TBD)
- `compliance.fecha_vencimiento_timbrado` (date, default=None) — from §19 (TBD)

#### Group: `goals` (3 settings)
- `goals.target_revenue_monthly_gs` (int, default=0) — from §20 (TBD)
- `goals.target_products` (int, default=30) — from §20 (the +30 in §11.4 = 30 products meta)
- `goals.target_customers_daily` (int, default=30) — from §11.2 (20-30 meta)

**Total: 25 new settings across 8 new/extended groups**.

### Counts update
- Was: 74 settings across 16 groups (SASKIA-215)
- After this: **99 settings across 22 groups** (16 + 8 new = 24 actually, but `location` is extended, not new → 16 + 7 new + 1 extended = 24 groups)

Wait, let me recount:
- Current 16 groups (from SASKIA-215): branding, location, seasonal, recipe, sales, plus the 11 settings-only groups
- New 7 new groups: business_info, contact, marketing, targeting, positioning, operations, compliance, goals (8 new actually, but `location` is extended)
- After: 16 + 8 = **24 groups**

### Test updates
- `tests/test_settings.py` — update count from 74 → 99 settings, 16 → 24 groups
- New test file: `tests/test_settings_questionnaire_answers.py` — verify all 70 questionnaire answers map to a registry key (or are explicitly marked as "data not config")
- New test file: `tests/test_seasonal_events_relevance_filter.py` — verify the relevance_tags filter works for per-pack visibility

## Out of scope (deferred)

- **SASKIA-223** — HEREBUS data import (100 ingredients, 23 recipes, 7 packaging, 24 products, 20 suppliers) — separate ticket
- **SASKIA-224** — Recipe yield backfill (16 of 23 recipes have empty B4) — separate ticket
- **SASKIA-220** — 5 new packs + tier 2/3/4 catalog expansion — separate ticket

## Risks

1. **Many "TBD" placeholders**: ~8 of the 25 new settings have empty defaults (instagram, facebook, ruc, timbrado, lat, lng, supplier contacts, etc.). The seeder must set the questionnaire-answered values but leave TBD ones blank. Operator fills in later.
2. **Schema not needed**: this is settings_kv only, no new migration. Settings go in `settings_kv` (already exists).
3. **HEREBUS overlap**: some of these settings (location.address_full, contact.phone) are also in HEREBUS as the operator's manual records. The Sazon settings become the **canonical** source; HEREBUS is a parallel spreadsheet the operator uses mentally.
4. **Test count bloat**: 99 settings × 1 test per setting = 99 tests. Use parametrize + a single test_settings_consistent.

## Acceptance

- `len(registry.groups) == 24` (was 16)
- `len(registry.settings) == 99` (was 74)
- `seed_sazon()` populates the 25 new keys with the questionnaire values
- All 41+ existing tests still pass
- New test files: 2 new test files, 6+ tests pass
- `make ruff` + `make format-check` clean
- CHANGELOG.md entry per AGENTS.md rule 35

## Reference

- **Full data plan**: `docs/operations/2026-10-12-saskia-full-seed-data-plan.md` §4.11
- **Questionnaire analysis**: `docs/operations/2026-10-09-la-vaquita-onboarding-analysis.md`
- **SASKIA-215 (parent)**: `docs/intake/SASKIA-215-add-location-seasonal-recipe-settings.md` (the 6 new settings)
