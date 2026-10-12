# SASKIA-215: Add LOCATION + SEASONAL settings + SeasonalEvent model

**Date:** 2026-10-12
**Epic / Story:** (La Vaquita onboarding continuation, no epic)
**Owner:** Iván
**Estimate:** 2-3h
**Status:** drafted (post-OOB-2026-10-12)

## Background

SASKIA-213 replaced the placeholders in the La Vaquita seeder
(BUSINESS_INFO + SASKIA_* constants) with the real values from the
2026-10-08 onboarding questionnaire. SASKIA-214 drafted the
multi-tenant refactor (per-instance config). This ticket fills in
the **gaps that the questionnaire answered but the schema can't
yet persist** — specifically the location, seasonal, and recipe
labor fields.

## What

1. **Add `LOCATION` to `SettingGroup` enum** (in
   `app/rms/settings_registry.py`)
2. **Add 2 new settings** in the `LOCATION` group:
   - `location.barrio` (str) — question §22.1. Default = `""`.
     Value from Saskia: `"San Lorenzo"`.
   - `location.zona` (str) — question §22.2. Choices:
     `["residencial", "comercial", "mixta", "industrial"]`.
     Default = `"residencial"`. Value from Saskia:
     `"residencial"`.
3. **Add `SEASONAL` to `SettingGroup` enum**
4. **Add 1 new setting** in the `SEASONAL` group:
   - `seasonal.notif_lead_days` (int) — question §16.6. Default
     = `30`. Value from Saskia: `30`.
5. **Add `RECIPE` to `SettingGroup` enum**
6. **Add 2 new settings** in the `RECIPE` group:
   - `recipe.labor_cost_enabled` (bool) — question §7.4. Default
     = `0`. Value from Saskia: `1` (yes).
   - `recipe.labor_cost_per_hour_gs` (int) — question §7.4
     default. Default = `25000`.
7. **Add `sales.shop_whatsapp` setting** in the existing `SALES`
   group — question §8.1. Default = `""`. Value from Saskia:
   `"+595 991 683805"`.
8. **Update `tests/test_settings.py`** count assertions to add
   the 6 new settings + 3 new groups.
9. **Update `CHANGELOG.md`** per AGENTS.md rule 35.
10. **Update `seed/sazon.py`** so the seeder populates the 4
    answered settings (Saskia's values) on `seed_sazon()`.
11. **Out of scope for this ticket**: `SeasonalEvent` model
    (the actual seasonal event rows — Semana Santa 2027,
    Navidad 2027, etc.). That's a separate migration + model
    ticket (SASKIA-216) because it requires a new table.

## Why

- The 2026-10-12 OOB message said **"the website of sazon should
  load all of the thigns"** — meaning every piece of data
  Saskia gave us should be loadable. Today, the location,
  seasonal, and recipe-labor answers **can't be persisted**
  because the settings don't exist.
- These are **the lowest-effort additions** (settings, not models)
  that unblock the most questionnaire data. Models are larger
  work.
- Each new setting is a 4-line addition to the registry + 1-line
  test update. The settings_registry pattern is well-established
  (68 settings, 13 groups already); adding 6 more is routine.

## Tasks

- [ ] Add `LOCATION`, `SEASONAL`, `RECIPE` to `SettingGroup` enum
- [ ] Add 5 new settings (location.barrio, location.zona,
      seasonal.notif_lead_days, recipe.labor_cost_enabled,
      recipe.labor_cost_per_hour_gs, sales.shop_whatsapp) — 6 total
- [ ] Update `tests/test_settings.py::test_settings_count` and
      `test_settings_per_group_counts` (add 3 groups to set, add
      counts for the 3 new groups, bump `len(SETTINGS) == 74`)
- [ ] Add a new test `tests/test_settings_la_vaquita_answers.py`
      that asserts each of the 4 answered settings has the right
      default (sanity check that the questionnaire values would
      land in a fresh-seeded DB)
- [ ] Update `seed/sazon.py` to populate the 4 answered values
      from the constants (analogous to how `BUSINESS_INFO` feeds
      `branding.*` settings in `_seed_settingskv_branding`)
- [ ] Update `CHANGELOG.md`
- [ ] Run `make check` and `uv run pytest tests/test_settings*.py
      tests/test_seed_vaquita_constants.py -v`
- [ ] Open PR, wait for CI

## Acceptance

- `len(SETTINGS) == 74` (was 68; +6 new settings)
- `groups == {..., SettingGroup.LOCATION, SettingGroup.SEASONAL,
   SettingGroup.RECIPE}` (was 13 groups, now 16)
- Each new setting has a clear docstring referencing the
  questionnaire section
- `seed_sazon()` on a fresh DB populates
  - `sales.shop_whatsapp = "+595 991 683805"`
  - `location.barrio = "San Lorenzo"`
  - `location.zona = "residencial"`
  - `seasonal.notif_lead_days = 30`
  - `recipe.labor_cost_enabled = 1` (true)
  - `recipe.labor_cost_per_hour_gs = 25000`
- All existing tests still pass (no regressions)
- `make ruff` + `make format-check` clean

## Out of scope (deferred)

- **SeasonalEvent model** (SASKIA-216): the actual table that
  stores rows for "Semana Santa 2027", "Navidad 2027", etc. Needs
  a migration and a model. Saskia's §16.1 + §16.5 answers name
  events but the model doesn't exist.
- **Alérgenos icons in public menu** (§19.6): the
  `Product.allergens` column exists but the public menu template
  doesn't render icons. Separate UI ticket.
- **Insurance / Employee / Payroll / GrowthPlan models**: all
  referenced by the questionnaire but the models don't exist and
  Saskia TBD'd or didn't need them.
- **Per-tenant scope for SettingsKV** (the
  shared-DB-multi-tenant RLS work): separate, much larger ticket.

## Risks

- **Low risk**. This is a config registry addition following an
  established pattern. The 6 new settings don't change any
  existing behavior; they only add new keys.
- **Test count assertions** must be updated in
  `tests/test_settings.py` or CI will fail.
- **Idempotency**: the seeder's `_seed_settingskv_branding`
  helper uses `if existing is None: insert` (skips if row exists).
  Adding a new key on a fresh DB will insert; on an already-seeded
  DB the new keys won't appear (the rows don't exist yet) and the
  seeder will insert them. **No backfill is needed for fresh
  installs; for existing instances, run `seed_sazon()` again and
  the 6 new keys will appear.**

## Reference

- OOB message: 2026-10-12 ("the website of sazon should load
  all of the thigns")
- Analysis doc: `docs/operations/2026-10-09-la-vaquita-onboarding-analysis.md` §6.3
- Existing settings registry: `app/rms/settings_registry.py`
  (68 settings, 13 groups)
- SASKIA-213 (placeholder replacement, shipped):
  `docs/intake/SASKIA-213-vaquita-seed-data-update.md`
- SASKIA-214 (multi-tenant refactor, drafted):
  `docs/intake/SASKIA-214-per-instance-business-info.md`
- Sazon seeder: `app/rms/seed/sazon.py` (constants
  `BUSINESS_INFO` already feed `branding.*` settings)
