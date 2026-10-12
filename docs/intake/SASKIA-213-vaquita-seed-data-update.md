# SASKIA-213: Update La Vaquita seed with real client data from onboarding questionnaire

**Date:** 2026-10-12
**Epic / Story:** (operational onboarding, no epic)
**Owner:** Iván
**Estimate:** 1h
**Status:** in_progress

## What

The current `app/rms/seed/sazon.py` (the La Vaquita Holandesa seeder)
contains **placeholder values** that don't match the real client's
(Saskia Weiss Vander) answers from the 2026-10-08 onboarding
questionnaire. This ticket updates the seeder with the answers
Saskia actually gave, so the next `seed_sazon()` call (or the
fresh install of the La Vaquita instance) populates the real
identity instead of the placeholders.

**Scope of THIS ticket** (intentionally narrow):

1. `BUSINESS_INFO` dict (lines 472-479 in sazon.py):
   - `address` → `"LAGUAN GRANDE, ARQUITECTOS, CALLE 17, Asunción"`
   - `phone` → `"+595 991 683805"`
   - `email` → `"La.vaquitaholandesa@gmail.com"`
   - `business_hours` → `"Martes a sábado de 9 am a 6 pm"`

2. `SASKIA_*` constants (lines 130-134):
   - `SASKIA_FULL_NAME` → `"Saskia Weiss Vander"` (her actual
     answer to §4.1; the current `"Saskia Weiss"` is missing
     "Vander")
   - `SASKIA_EMAIL` → `"La.vaquitaholandesa@gmail.com"` (her
     answer to §4.3; current `saskia@lavaquita.example` is
     placeholder)

3. `branding.tagline` (line 5067) — currently `"Panadería
   artesanal desde 1985"` — this is a placeholder too, but
   Saskia didn't answer §1.3, so **leave the default**.

4. `branding.footer` (line 5071) — currently `"© 2025 La
   Vaquita Holandesa — Hecho con cariño en Asunción"`. The
   2025 copyright is wrong (2026 is current year). Update
   to `"© 2026"`. This is a one-character fix.

**Scope explicitly EXCLUDED from this ticket** (will become
follow-up tickets if Iván wants):

- `CASHIER_USERS` (lines 136-140) — Saskia answered §4.5 = `no`
  (no cashiers), but the seeder still creates Lucía and Diego
  as fake cashiers. **This is the wrong user count for THIS
  tenant**, but removing the cashier block would break the
  function signature `_ensure_user(...)` that iterates over
  `CASHIER_USERS`. The right fix is a follow-up ticket
  (SASKIA-214) that makes the cashier list configurable per
  instance. For THIS ticket, we leave `CASHIER_USERS` alone but
  add a comment noting the §4.5 = no data.

- `COMPLIANCE` dict (lines 444-471) — RUC, R.E. INAN, Timbrado,
  SIFEN, Director Técnico, etc. are all TBD in the
  questionnaire. The current placeholders (RUC `80012345-6`,
  Timbrado `13456789`, etc.) are **better than nothing** because
  they let the system operate (boleta resimple without legal
  invoice is allowed without these). **Leave as-is.**

- `branding.business_type` (line 5068) — currently `"panaderia"`.
  Saskia answered §1.8 = `GASTRONOMICO` which is not a value in
  the registry's `branding.business_type` choices. This is a
  **schema gap**, not a config gap. Defer to a follow-up ticket.

- `TENANT_COLOR` (line 124) — currently `"#7b3f00"`. The
  questionnaire's §1.4 default is `"#6B4423"`. These are two
  different shades of brown. The questionnaire's color is the
  doc's suggested default; the seed's is the developer's
  earlier pick. **Not in scope** — would be a UI redesign
  decision, not a config update.

- Logo, favicon, hero image — all TBD (she has the files but
  hasn't sent them). **Cannot update.**

- Product catalog §5.1 (which 22 of 32 to enable day-1) — all
  `❓` (undecided). **Cannot update.**

- Suppliers §6.1 (which 5 of 5 to use) — all `❓`. **Cannot
  update.**

- Recipes §7 (manual of obra, margen objetivo per category) —
  only §7.4 answered. Schema gap (no `prep_minutes` /
  `cook_minutes` columns in `Recipe`). **Cannot update.**

- §16 SeasonalEvent model — schema doesn't exist. Defer.

- §18 Insurance model — schema doesn't exist. Defer.

- §22 location.barrio / location.zona settings — schema doesn't
  exist. Defer.

## Why

- **Operator impact**: the next time the La Vaquita instance is
  seeded or re-seeded, the system will show Saskia's real phone
  number on the login page, the real email on tickets and
  PDFs, the real address, the real business hours, and the
  real operator name. Today it shows placeholders that would
  confuse her and her customers.
- **Custodian sanity**: placeholders that survive into a
  production instance are a footgun. A future session that
  reads the seeder and assumes "this is what the client
  confirmed" could merge changes that ship the wrong phone
  number to a customer.
- **Brand**: a footer with "© 2025 La Vaquita Holandesa" on
  a 2026-launched instance is a 1-year-old copyright. Easy
  fix while we're here.

## Tasks

- [ ] Update `BUSINESS_INFO.address`
- [ ] Update `BUSINESS_INFO.phone`
- [ ] Update `BUSINESS_INFO.email`
- [ ] Update `BUSINESS_INFO.business_hours`
- [ ] Update `SASKIA_FULL_NAME` to `"Saskia Weiss Vander"`
- [ ] Update `SASKIA_EMAIL` to `"La.vaquitaholandesa@gmail.com"`
- [ ] Update `branding.footer` to `"© 2026"`
- [ ] Add comment near `CASHIER_USERS` noting the §4.5 = no data
      (so a future reader knows this is intentional, not a bug)
- [ ] Update `app/CHANGELOG.md` per AGENTS.md rule 35
- [ ] Add a unit test that asserts the seeder's `BUSINESS_INFO`
      matches the values from the questionnaire (regression
      guard against placeholder regression)
- [ ] Run `uv run pytest tests/test_seed_sazon.py -k BUSINESS_INFO`
      (or equivalent) to verify the seed runs idempotently
- [ ] Run `make ruff && make format-check` (or equivalent) on
      the touched files

## Acceptance

- `BUSINESS_INFO` and `SASKIA_*` constants in `sazon.py` match
  the values in this ticket's "Scope" section exactly.
- `branding.footer` says `© 2026` (not `© 2025`).
- A comment near `CASHIER_USERS` documents that the seeder
  currently creates 2 cashiers, which is the WRONG user count
  for the La Vaquita instance (per questionnaire §4.5 = `no`),
  and that this is being addressed in a follow-up ticket
  SASKIA-214.
- `app/CHANGELOG.md` has a new entry under the next version
  section referencing this ticket.
- One new test in `tests/test_seed_sazon.py` (or appropriate
  location) asserts the new `BUSINESS_INFO` values, so a
  future placeholder regression fails CI.
- All touched files pass ruff + format-check.
- The diff is **< 20 lines** of production code + 1 test +
  CHANGELOG entry. Anything bigger is a scope creep and
  should be split into SASKIA-214 or another follow-up.

## Risks

- **Low risk** — this is a config update in the seeder, not a
  schema or API change. The seeder is only called from
  `seed_sazon()` which is itself only called from explicit
  operator scripts (per the seeder's docstring) — no
  automatic invocation on import.
- **Idempotency risk** — the existing seed logic uses
  `_ensure_user(...)` and `_ensure_setting(...)` which check
  for existing rows by natural key. Changing the values
  **will not** update existing rows. If the La Vaquita
  instance has already been seeded with placeholder values,
  the operator must run a one-time backfill (out of scope for
  this ticket). Document this in the PR description.
- **Brand-name "Sazón" vs "La Vaquita Holandesa"** — the
  current `branding.business_name` default in
  `app/rms/settings_registry.py` is `"Sazón"`. The seeder
  overrides this to `TENANT_NAME = "La Vaquita Holandesa"`
  on line 5069. So the visible brand is "La Vaquita
  Holandesa" on the seeded instance. **This is intentional,
  not a bug** — the questionnaire's §1.2 default of
  `Sazón` was a doc default, not Saskia's answer. If Iván
  wants to re-confirm the brand choice with Saskia, that's
  a separate call (see §4.1 of the analysis doc).

## Source

- Questionnaire: `/opt/data/profiles/ivan/attachments/2026-10-08-la-vaquita-feliz-onboarding-questionnaire.md.docx`
- Analysis doc: `docs/operations/2026-10-09-la-vaquita-onboarding-analysis.md`
- Seeder file: `app/rms/seed/sazon.py`
- Settings registry: `app/rms/settings_registry.py`
