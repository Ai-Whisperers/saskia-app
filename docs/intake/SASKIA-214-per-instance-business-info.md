# SASKIA-214: Per-instance BUSINESS_INFO + user roster config (multi-tenant scaffolding)

**Date:** 2026-10-12
**Epic / Story:** (multi-tenant scaffolding, no epic yet)
**Owner:** Iván
**Estimate:** 4-6h
**Status:** drafted (post-OOB-2026-10-12)

## Background — why this ticket exists

The 2026-10-12 OOB message from Iván reframes the Sazon product
direction: **"la vaquita holnadesa iis a just the first client later
we will have many more"**. This reverses the SASKIA-210 (2026-10-07)
"per-client instances" stance — Sazon is now expected to be
**multi-tenant ready** so adding new clients doesn't require
re-architecting.

Sazon already has the multi-tenant scaffolding in place:

- `app/rms/seed/onboard.py::onboard_tenant(session, tenant_name, pack, days_of_history, seed)`
  creates a fully-seeded instance in one call. Takes a `tenant_name`
  and a `pack` (Pizzería, Panadería, Café/Cafetería, etc.).
- `app/rms/seed/packs.py::PACKS` has 11 packs (Café/Cafetería,
  Catering/Eventos, Comedor/Kilo, Empanadas/Criolla,
  Hamburguesería/Rápida, Heladería, Oriental, Panadería,
  Parrilla/Restaurante, Pastelería/Confitería, Pizzería).
- `app/rms/seed/sazon.py` is the **La Vaquita-specific** seeder —
  it hard-codes `TENANT_NAME = "La Vaquita Holandesa"`,
  `BUSINESS_INFO = { address, phone, email, business_hours }`,
  and `CASHIER_USERS = [("lucia", ...), ("diego", ...)]`.

**The gap**: `sazon.py` is a one-off seeder, not a parameterized
multi-tenant function. Adding a new client today means:
1. Either copy-paste `sazon.py` to `sazon_<client>.py` and edit
   the hard-coded constants (no shared logic, no shared tests)
2. Or re-run `sazon.py` and overwrite the La Vaquita data

Neither scales. The right shape is:

- A new function `seed_client_instance(session, *, tenant_name,
  business_info: dict[str, str], user_roster: list[tuple],
  pack: str, days_of_history: int = 0)` that takes all
  per-instance config as parameters
- `sazon.py` becomes a thin wrapper that calls
  `seed_client_instance(..., business_info=LA_VAQUITA_BUSINESS_INFO,
  user_roster=LA_VAQUITA_USER_ROSTER, pack="Panadería")`
- `onboard_tenant()` already calls `seed_pack()` which is
  parameterized — it just needs a `seed_instance()` wrapper
  around it that takes the per-instance config

**Concrete deliverables**:

1. **`app/rms/seed/instance.py`** (new file): defines
   `BusinessInfo` dataclass (or TypedDict), `UserRoster` dataclass,
   and `seed_client_instance(session, *, tenant_name, business_info,
   user_roster, pack, days_of_history, seed)` that:
   - Creates the `Tenant` row from `tenant_name`
   - Creates the `User` rows from `user_roster`
   - Inserts the `branding.*` + `ops.*` SettingsKV rows from
     `business_info`
   - Calls `seed_pack(session, pack, tenant_name=tenant_name)`
   - Calls `seed_pack_demo(session, days_of_history, seed)` if
     `days_of_history > 0`
   - Returns a `SazonReport` (or new `InstanceReport` type)
2. **`app/rms/seed/sazon.py`** (refactor): keep all the existing
   constants (`BUSINESS_INFO`, `SASKIA_*`, `CASHIER_USERS`,
   `COMPLIANCE`, etc.) but make `seed_sazon()` call
   `seed_client_instance(..., business_info=BUSINESS_INFO,
   user_roster=[("saskia", "saskia1234", SASKIA_FULL_NAME,
   SASKIA_EMAIL), *CASHIER_USERS], pack="Panadería")`
3. **`app/rms/seed/onboard.py`** (small change): add a
   `business_info` + `user_roster` parameter to
   `onboard_tenant()` and pass them through to the new
   `seed_client_instance()`
4. **`tests/test_seed_instance.py`** (new): parameterized tests
   for `seed_client_instance()` with multiple per-instance
   configs to verify the data flows through correctly
5. **Documentation**: update `docs/operations/2026-10-09-la-vaquita-onboarding-analysis.md`
   to reflect the multi-tenant direction (remove the SASKIA-210
   "per-client instances" framing). Add a section explaining how
   to onboard the next client (Café/Cafetería, Pizzería, etc.)
6. **CHANGELOG.md** entry (per AGENTS.md rule 35)

## Out of scope (deferred)

- **RLS / ORM-level tenancy** (e.g. row-level security, every
  table gets `tenant_id` foreign key, every query auto-filters
  by `tenant_id`). Sazon's current architecture is "one
  client per deployment" (each client gets their own VPS +
  Docker + DB). This ticket is about the **seed layer**;
  ORM-level tenancy is a much bigger refactor (SASKIA-210's
  original "future" item) and not needed yet because each
  client deploys to their own VPS anyway.
- **Per-tenant SettingsKV persistence**: today the seeder inserts
  `branding.*` rows on first run; subsequent `seed_sazon()` calls
  skip them (the existing rows are matched by `key`). This is
  fine for the "one DB per client" model. Multi-DB single-tenant
  ORM-level work is the next step, not this ticket.
- **`SeasonalEvent` / `Insurance` / `GrowthPlan` / `Employee` /
  `Payroll` models**: all referenced by the La Vaquita
  questionnaire but don't exist yet. They need their own
  tickets (SASKIA-215+).
- **`location.barrio` / `location.zona` / `seasonal.notif_lead_days`**
  settings: need their own registry entries + ticket.
- **`branding.business_type = "gastronomico"`** enum gap: separate
  ticket.

## Acceptance

- A new file `app/rms/seed/instance.py` defines
  `seed_client_instance()` and is imported by both
  `sazon.py` and `onboard.py`
- `seed_sazon()` still works on a fresh DB (all existing tests
  pass, including `test_seed_vaquita_holandesa_for_saskia.py`
  and the new `test_seed_vaquita_constants.py`)
- New test `test_seed_client_instance_with_pizzeria_pack` runs
  `onboard_tenant(session, "Pizzería Don Carlos",
  pack="Pizzería", business_info=PIZZERIA_INFO,
  user_roster=PIZZERIA_USERS)` on a fresh DB and asserts
  - The `Tenant` row exists with `nombre_fantasia="Pizzería Don Carlos"`
  - The `User` rows match `PIZZERIA_USERS` (no Saskia, no Lucía,
    no Diego)
  - The `SettingsKV` row for `branding.contact_phone` matches
    `PIZZERIA_INFO["phone"]` (not La Vaquita's)
  - The `Product` rows are from the Pizzería pack
    (search for "Pizza" — should be present, "Babka" should NOT)
- New test `test_seed_client_instance_idempotent_per_pack` runs
  `seed_client_instance()` twice with the same args and asserts
  no duplicate rows
- The analysis doc at
  `docs/operations/2026-10-09-la-vaquita-onboarding-analysis.md`
  is updated: §2 (per-instance vs multi-tenant) and §6
  (schema gap inventory) reflect that Sazon IS multi-tenant
  via the onboard + pack pattern, not per-client instances

## Risks

- **Medium risk** — the seeder is 5,000+ lines and the refactor
  touches the central function. The 25 existing seed tests
  must continue to pass; if any break, the refactor changed
  behavior and needs to be reverted. The pattern from the
  2026-10-09 refactoring session (extract helper, run tests
  in isolation, then extract more) is the playbook.
- **Idempotency** — the existing `seed_sazon()` uses
  `_ensure_*` helpers that match by natural key. The new
  `seed_client_instance()` must use the same pattern (or call
  into the existing helpers), or a second run with different
  `business_info` args will create duplicate SettingsKV rows.
  The test `test_seed_client_instance_idempotent_per_pack`
  guards this.
- **Migration of existing instances** — any La Vaquita instance
  that was already seeded with the old `sazon.py` constants
  has placeholder values in the DB. The new
  `seed_client_instance()` will not update those rows (matches
  by key, skips if present). A one-time backfill script is
  needed (out of scope for this ticket; documented in
  SASKIA-213's CHANGELOG entry).

## Reference

- OOB message: 2026-10-12 (H₂ of the dev session)
- Sazon seed: `app/rms/seed/sazon.py` (5000+ lines)
- Onboard function: `app/rms/seed/onboard.py::onboard_tenant()`
- Packs: `app/rms/seed/packs.py` (11 packs)
- Analysis doc: `docs/operations/2026-10-09-la-vaquita-onboarding-analysis.md`
- SASKIA-213 (placeholder replacement): `docs/intake/SASKIA-213-vaquita-seed-data-update.md`
- SASKIA-210 (pre-OOB "per-client instances" decision): to be
  marked as "decision-superseded" once this ticket ships
