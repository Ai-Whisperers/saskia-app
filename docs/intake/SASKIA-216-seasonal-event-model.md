# SASKIA-216: SeasonalEvent model + multi-tenant seed catalog (PY + NL heritage)

**Date:** 2026-10-12
**Status:** drafted (post-OOB-2026-10-12)
**Author:** AIW Bot
**Estimate:** 2-3 days
**Sister tickets:** SASKIA-213 (shipped), SASKIA-215 (shipped), SASKIA-214 (drafted), SASKIA-217 (followup UI), SASKIA-218 (per-tenant overrides)
**Deep analysis:** `docs/operations/2026-10-12-seasonal-events-comprehensive-catalog.md` (the full research, this is the short version)

## Why

The 2026-10-12 OOB said "the website of sazon should load all of the thigns la vaquita holnadesa iis a just the first client later we will have many more". The 2026-10-08 onboarding questionnaire §16.1 (Semana Santa = si), §16.5 (Menú estacional verano/invierno = si), §16.6 (Aviso 30 días antes = si, already wired as `seasonal.notif_lead_days` setting) — all three are answered "yes" but the **schema can't persist them** because no `SeasonalEvent` model exists.

The website has to render a calendar of upcoming events. The catalog (PY national holidays + PY commercial days + Catholic movable feasts + school calendar + a few NL heritage dates for the "Vaquita Holandesa" brand) is the seed data for that page. The model has to be **multi-tenant-ready** (per OOB): one shared table with a `relevance_tags` filter so each client instance sees only what's relevant to its market.

## What

1. **New model `SeasonalEvent`** in `app/rms/models_legacy.py`:
   - `id`, `slug`, `name_es`, `name_nl`, `name_en`, `description`
   - `event_date`, `end_date` (nullable for multi-day)
   - `country` (ISO-3166-1 alpha-2, default "PY")
   - `category` ("legal" / "commercial" / "religious" / "school" / "folk" / "sectoral" / "heritage")
   - `impact_score` (0.0-1.0, for production scaling math)
   - `impact_tag` ("critical" / "high" / "medium" / "low" / "info", for UI dot)
   - `relevance_tags` (CSV: "panaderia,cafeteria,pizzeria" — empty = all)
   - `is_annual` (bool), `recurrence` (e.g. "fixed", "easter-3", "third-sunday-june", "movable-by-decree")
   - `created_at`, `updated_at`
   - Unique on `(country, slug, event_date)`

2. **Migration 119** in `app/rms/migrations/_119_seasonal_event_table.py`:
   - Create `seasonal_event` table per above schema
   - Idempotent: check `CREATE TABLE IF NOT EXISTS` (SQLite) / `IF NOT EXISTS` (Postgres)
   - Bump `CURRENT_SCHEMA_VERSION` 118 → 119
   - Register in `app/rms/db.py` migrations dict

3. **Seeder `_seed_seasonal_events(ctx)`** in `app/rms/seed/sazon.py`:
   - Inserts **132 rows** = 44 distinct event types × 3 years (2026, 2027, 2028)
   - Idempotent: skip if `(country, slug, event_date)` exists
   - Tier 1 (critical, 10 events): Semana Santa, Pascua, Día de la Madre PY, Navidad, Año Nuevo, Reyes, San Juan Ára, San Lorenzo patron (10 Aug), Asunción patron (15 Aug), Nochebuena
   - Tier 2 (high, 7 events): Día del Niño, Día del Amigo, Independencia, Inicio/Fin de clases PY, Virgen de Caacupé
   - Tier 3 (medium, 15 events): Carnaval Encarnaceno, Día del Padre, Día del Maestro, Día de la Mujer, Héroes, Trabajadores, Paz del Chaco, Jura de la Constitución, Boquerón, Vacaciones invierno, Black Friday, CyberDay, Cuaresma, Corpus Christi, Sinterklaas (NL heritage)
   - Tier 4 (low, 9 events): Día del Panadero, Almaceneros, Música, Pueblos Originarios, Primavera, Tereré, Singles Day, Halloween, San Valentín
   - Tier 5 (info, 3 events): Koningsdag NL, Bevrijdingsdag NL, King's Birthday
   - Full catalog with baked 2026/2027/2028 dates in the analysis doc §7.1

4. **Tests** in `tests/test_migration_119_seasonal_event.py`:
   - Schema bumps to 119
   - Table exists with right columns
   - `seed_sazon()` inserts the expected row count (≥ 132, ≤ 150 to allow for decree additions)
   - Idempotency: re-running doesn't grow
   - Unique constraint: inserting a duplicate `(country, slug, event_date)` fails

5. **CHANGELOG.md** entry per AGENTS.md rule 35.

## Out of scope (deferred)

- **SASKIA-217**: `/admin/seasonal-calendar` UI page (read-only, respects `seasonal.notif_lead_days`)
- **SASKIA-218**: `TenantSeasonalEventOverride` table for per-tenant visibility
- **SASKIA-219**: `scripts/refresh_seasonal_events.py` cron for annual roll-forward (Easter, decrees)
- **Annual runtime computus** for Easter / Ash Wednesday / Corpus Christi / Ascension (currently baked for 2026-2028 only)
- **Multi-locale UI** (today only `name_es`; `name_nl` + `name_en` are stored but not displayed)

## Risks

- **Low schema risk**: adding one new table doesn't affect existing models.
- **Medium seeder risk**: 132 rows is a lot of code; one bad date is a 1-row fix but the seed function becomes 132 lines. Mitigation: generate the rows programmatically from a small data dict + a year loop.
- **External dependency risk**: Carnival, CyberDay, school calendar dates change annually. Mitigation: the seed inserts actual dates (not recurring rules) for 2026-2028; SASKIA-219 will handle the annual refresh.
- **Multi-tenant semantic risk**: if the next client is in NL, the PY holidays should NOT show in their calendar. The `relevance_tags` column handles this for verticals; the `country` column handles this for geography. But the **default seeder** today is PY-only; the NL client would need a different seeder (or a `onboard_tenant(country="NL", ...)` extension — SASKIA-214).

## Acceptance

- `CURRENT_SCHEMA_VERSION == 119` after migration
- `len(SeasonalEvent.query.all()) >= 132` after `seed_sazon()` on a fresh DB
- Re-running `seed_sazon()` does NOT grow the count
- All 132 dates are correct (compare to `docs/operations/2026-10-12-seasonal-events-comprehensive-catalog.md` §3.2, §4.1, §4.2, §5.1)
- All 31 existing seed+settings tests still pass; no regressions
- `make ruff` + `make format-check` clean

## Reference

- **Deep analysis**: `docs/operations/2026-10-12-seasonal-events-comprehensive-catalog.md` (the full PY + NL holiday research with sources, baked 2026/2027/2028 dates, schema rationale)
- **Questionnaire §16**: `docs/operations/2026-10-09-la-vaquita-onboarding-analysis.md` §6.2 (existing analysis that flagged this gap)
- **SASKIA-215 (parent)**: `docs/intake/SASKIA-215-add-location-seasonal-recipe-settings.md` (the `seasonal.notif_lead_days` setting that the UI will respect)
- **SASKIA-214 (sister)**: `docs/intake/SASKIA-214-per-instance-business-info.md` (the per-instance config refactor that will pass the catalog as a parameter)
- **OOB-2026-10-12**: "the website of sazon should load all of the thigns la vaquita holnadesa iis a just the first client later we will have many more"
