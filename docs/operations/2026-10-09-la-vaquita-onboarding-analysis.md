# La Vaquita Holandesa — onboarding questionnaire analysis (read-only)

> **Status**: **Read-only analysis.** No code changes proposed. The
> purpose of this doc is to capture what the client (Saskia Weiss
> Vander) answered in her onboarding questionnaire, map the answers
> to the **existing** Sazon schema, and surface the open decisions
> that need to be answered by **Iván** (developer-operator) before any
> code is written.
>
> **Source**: `/opt/data/profiles/ivan/attachments/2026-10-08-la-vaquita-feliz-onboarding-questionnaire.md.docx`
> (v2 questionnaire with her filled-in answers).
>
> **Direction update (2026-10-12 OOB)**: Iván reframed the product
> direction with "la vaquita holnadesa iis a just the first client
> later we will have many more". The earlier SASKIA-210
> (2026-10-07) "per-client INSTANCES, not shared-DB multi-tenant"
> decision is **superseded** for the onboarding layer: Sazon is
> multi-tenant-ready via `app/rms/seed/onboard.py::onboard_tenant()`
> + `app/rms/seed/packs.py::PACKS` (11 packs). The
> shared-DB-with-tenant-id-foreign-key work (RLS / ORM-level
> tenancy) is a separate, much larger refactor that does NOT
> need to land for multi-client onboarding. The
> `Tenant` table from migration 008 is now the **canonical target
> for per-instance rows**, not legacy dormant infrastructure. This
> doc's earlier "Tenant is legacy dormant" framing (2026-10-09
> draft) is **wrong** post-OOB and is being corrected inline.
>
> **Scope guardrails** (from `AGENTS.md`):
> - This is **multi-tenant onboarding**, not single-tenant: each
>   new client runs `onboard_tenant(session, "Cliente 2",
>   pack="Pizzería")` to create a fully-seeded instance in one call.
> - The `Tenant` table is now the **active multi-tenant target**,
>   not legacy infrastructure.
> - No code change ships without a `SASKIA-NNN-<slug>.md` ticket
>   (AGENTS.md rule 37) and a matching `CHANGELOG.md` entry
>   (AGENTS.md rule 35).
> - The decision framework (AGENTS.md "Decision framework") lists
>   **things that must be escalated to Iván**: new dependencies,
>   security-sensitive changes, brand decisions, anything that
>   affects Saskia's workflow. This doc surfaces all of those as
>   open questions, not solved decisions.

## 1. Background — what this doc is for

Saskia filled in roughly 70/170 fields on a 22-section
questionnaire. The remaining ~100 are `TBD` or "lo respondemos
después". This doc:

1. Records **what she answered** (so we don't lose it).
2. Maps each answer to the **existing Sazon schema** (Tenant,
   ComplianceInfo, SettingsKV, Product, Recipe, etc.) — no new
   models, no new settings.
3. Lists the answers that are **blocked on information only Saskia
   has** (RUC, R.E. INAN, timbrado, etc.).
4. Lists the **decisions only Iván can make** (brand name conflict,
   per-instance vs multi-tenant, whether to add new fields at all).
5. Explicitly **does NOT recommend a PR**. When Iván wants to turn
   this into a real onboarding PR, the right next step is to file
   a `SASKIA-NNN-<slug>.md` ticket and let that drive the work.

## 2. What Saskia answered (the filled subset, by section)

### §1 — Identidad del negocio

| # | Field | Answer | Existing schema mapping |
|---|-------|--------|-------------------------|
| 1.1 | Razón social | `La Vaquita Holandesa S.A.` (default, accepted) | `branding.business_name` (SettingsKV; default = "Sazón") — **brand-conflict decision needed** |
| 1.2 | Nombre comercial | `Sazón` (default, accepted) | same key as 1.1; questionnaire says 1.2 is the customer-facing name but the literal answer is "Sazón" which is the product name. **Decision needed.** |
| 1.5 | Logo | TBD 📎 | `branding.logo_filename` (upload via `/api/admin/branding/upload`) |
| 1.6 | Favicon | TBD 📎 | `branding.favicon_filename` |
| 1.7 | Hero image | TBD 📎 | `branding.hero_filename` |
| 1.8 | Tipo de negocio | `GASTRONOMICO` | `branding.business_type` (enum needs verification — see §6) |
| 1.9 | Moneda | `Gs.` ✅ | `general.currency_symbol = Gs.` (default already) |
| 1.10 | Idioma tickets | `es-PY` ✅ | `general.locale = es_PY` (default already) |

### §2 — Ubicación y contacto

| # | Field | Answer | Existing schema mapping |
|---|-------|--------|-------------------------|
| 2.1 | Dirección | `LAGUAN GRANDE, ARQUITECTOS, CALLE 17` | `branding.address` |
| 2.2 | Ciudad | `ASUNCION` | embedded in `branding.address` |
| 2.3 | Teléfono / WhatsApp | `+595 991 683805` | `branding.contact_phone` |
| 2.4 | Email | `La.vaquitaholandesa@gmail.com` | `branding.contact_email` |
| 2.5 | WhatsApp Business separado | `Si` | (no schema field — informational) |
| 2.6 | Instagram | `+595 991 683805` | (no schema field — informational) |
| 2.7 | Horarios | `Martes a sabado de 9 am a 6 pm` | (no schema field — `branding` has no opening-hours key) |
| 2.8 | Google Maps link | TBD | (no schema field) |
| 2.9 | Delivery policy | TBD | affects which `Channel` rows to seed (when instance is created) |

> **§2.1 is a barrio name in Asunción, not a typo**: Laguán Grande,
> Arquitectos (sub-barrio), Calle 17. No geocoding possible without
> 2.8 (Google Maps URL).

### §4 — Equipo y accesos

| # | Field | Answer | Existing schema mapping |
|---|-------|--------|-------------------------|
| 4.1 | Nombre completo | `Saskia weissvanderpol` | `User.full_name` |
| 4.2 | Username | `saskia` | `User.username` |
| 4.3 | Email | `La.vaquitaholandesa@gmail.com` | `User.email` |
| 4.4 | Rol | `admin` | `User.role = admin` |
| 4.5 | ¿Tenés cajeros? | **`no`** | critical — 1 user only, not 3 |

> **§4.5 is the biggest surprise in the questionnaire.** The
> original seeder (in `app/rms/seed/sazon.py`) was built around
> "Saskia + 2 cajeros" (Lucía Fernández / Diego Cabral per the
> placeholder rows in §4.6-4.9). Saskia confirmed she will run the
> POS solo. **The placeholder names are NOT to be carried forward
> into the La Vaquita instance** — that would seed 3 fake users
> with real-looking names into a real business's database.

### §5 — Catálogo de productos (most rows TBD)

Saskia left §5.1.1 through §5.1.22 marked as either `❓` (decide
later) or `TBD` for the override price. This is the section that
will determine which 22 of the 32-product seed get activated and
which get `is_available=False`. **No work to do until she answers.**

### §7 — Recetas (mín. answered)

| # | Field | Answer | Existing schema mapping |
|---|-------|--------|-------------------------|
| 7.4 | ¿Cargar tiempo de mano de obra? | `si` | (no schema field — `Recipe` has no `prep_minutes`/`cook_minutes` columns; the 2026-10-07 redesign added `instructions` JSON column but no time fields) |

> **§7.4 raises a real gap**: Saskia wants to track prep+cook time
> per recipe for labor costing, but `Recipe` has neither column.
> This is **not in scope for a read-only analysis** — would be a
> future ticket (e.g. `SASKIA-218-recipe-labor-time`) if Iván wants
> to add it.

### §8 — Operación del local

| # | Field | Answer | Existing schema mapping |
|---|-------|--------|-------------------------|
| 8.1 | WhatsApp para pedidos | `+595 991 683805` | (no schema field — see `sales.shop_whatsapp` mentioned in the questionnaire's Apéndice A, but it doesn't exist in `app/rms/settings_registry.py` today) |
| 8.2 | ¿Aceptás pedidos por WhatsApp? | `si` | (no schema field) |
| 8.3 | Canales de venta | `Pedidos a través de whatsapp o redes y con pick up o delivery` | multi: `whatsapp`, `redes`, `pickup`, `delivery_propio` — no `pedidosya` |
| 8.6 | Medios de pago aceptados | `efectivo, transferencia, QR` | affects `PaymentMethod` seed rows |
| 8.7 | Vuelto desde app | `manual` | (admin-side policy — no schema field) |
| 8.8 | WiFi en el local | `no` | (informational) |
| 8.9 | Internet de respaldo | `no` | (informational) |
| 8.10 | Cierre de caja | TBD | affects the EOD cron schedule |

> **§8.1 / §8.2 / §8.3 gap**: the questionnaire's Apéndice A lists
> `sales.shop_whatsapp` as if it's an existing setting, but the
> current `app/rms/settings_registry.py` (68 settings, 13 groups)
> does **not** have it. Same for `sales.accept_whatsapp_orders`.
> This is another **schema gap** that would need a ticket.

### §9 — Clientes y fidelización

| # | Field | Answer | Existing schema mapping |
|---|-------|--------|-------------------------|
| 9.1 | ¿Clientes frecuentes? | `si` | (informational — no seed rows) |
| 9.2 | ¿Cargar lista inicial? | `no` | confirms 0 seed `Customer` rows |
| 9.3 | ¿Programa de fidelización? | `si` | `loyalty.*` settings already exist (10 keys in the LOYALTY group) |
| 9.4 | ¿Encargos / pedidos anticipados? | `si` | (informational — `Pedido` model supports this) |

### §10 — Historial inicial

| # | Field | Answer | Existing schema mapping |
|---|-------|--------|-------------------------|
| 10.1 | ¿90 días de ventas simuladas? | `no` | confirms no synthetic `Sale` rows in seed |
| 10.4 | Menú público el día 1 | `después` | no public menu activation |

### §16 — Estacionalidad paraguaya

| # | Field | Answer | Existing schema mapping |
|---|-------|--------|-------------------------|
| 16.1 | ¿Semana Santa 2027? | `si` | (no `SeasonalEvent` model — see §6) |
| 16.5 | ¿Menú estacional verano/invierno? | `si` | same |
| 16.6 | ¿Aviso 30 días antes? | `si` | (no `seasonal.notif_lead_days` setting — see §6) |

### §17 — Personal

| # | Field | Answer | Existing schema mapping |
|---|-------|--------|-------------------------|
| 17.1 | ¿Cuántas personas? | **`1`** (Saskia sola) | 0 `Employee` rows, 0 `Payroll` rows |
| 17.2 | ¿Saskia registrada como empleada? | TBD | (legal/employment — out of scope for code) |

> **§17 collapse**: Because §17.1 = 1, the entire `Employee` /
> `Payroll` / MTESS / REOP machinery is **moot for this instance**.
> The models can be created later for future clients; they are not
> needed for La Vaquita's day-1 launch.

### §21 — Crecimiento

| # | Field | Answer | Existing schema mapping |
|---|-------|--------|-------------------------|
| 21.1 | ¿Barrios en 3 años? | `1` | (no `GrowthPlan` model — see §6) |
| 21.2 | Delivery | `Delivery propio` | affects `Channel` seed rows |
| 21.3 | ¿Ferias / eventos? | `Tal vez` | (informational) |
| 21.4 | ¿Tienda online? | `Solo mostrador` | no online store |
| 21.5 | ¿Franquicias? | `no` | (informational — model not needed) |
| 21.6 | ¿Exportar? | `no` | (informational — model not needed) |

### §22 — Vecindario

| # | Field | Answer | Existing schema mapping |
|---|-------|--------|-------------------------|
| 22.1 | Barrio | `San lorenzo` | (no `location.barrio` setting — see §6) |
| 22.2 | Zona | `Residencial` | (no `location.zona` setting — see §6) |
| 22.3 | ¿Otros locales gastronómicos? | `no` | (informational) |
| 22.4 | ¿Estacionamiento? | `Si hay` | (informational) |
| 22.5 | ¿Vereda ancha? | `Si` | (informational) |
| 22.6 | ¿Parada de micro? | `no` | (informational) |
| 22.7 | ¿Motochorros? | `no` | (informational) |
| 22.8 | ¿Aviso picos de robo? | TBD | (informational — Observatorio Nacional is a public dataset) |

> **§22 is all informational** for this instance. The only two
> fields that touch the schema are `location.barrio = San Lorenzo`
> and `location.zona = residencial`, and both are settings that
> don't currently exist in the registry.

## 3. What Saskia did NOT answer (blocked on her, not on us)

These are the **operator-action** items that go back to Saskia
before any instance can be created. They are NOT work for the
repo — they are work for **Iván → Saskia via WhatsApp**.

### 3.1 Branding (needs her files)

- 1.5 / 1.6 / 1.7 — logo, favicon, hero image (she marked these
  TBD with 📎 = "adjuntar documento"). She has the files; she
  needs to send them.
- 1.1 vs 1.2 — the brand-name conflict (see §4.1 below).

### 3.2 Legal & fiscal (blocks emisión de factura legal)

- 3.1 — RUC (format `XXXXXXX-X` or `XXXXXXXXX-X`)
- 3.2 — Régimen tributario (general / resimple / no_libreta)
- 3.6 / 3.7 — INAN R.E. (Registro de Establecimiento) number
- 3.12 / 3.13 — Timbrado for boleta resimple
- 3.15 — SIFEN certificado (sí / no)
- 3.16 — SIFEN test or production mode

> The questionnaire itself notes: "Solo bloquea la emisión de
> factura legal (no la boleta resimple)." So the system can
> operate without these — the operator can issue non-legal
> receipts until she gets the timbrado. But the
> `ComplianceInfo` row can't be populated for legal-invoice
> features until she provides these.

### 3.3 Operations & timeline (blocks `Channel` / `PaymentMethod` / cron config)

- 2.8 — Google Maps link
- 2.9 — Delivery policy (propio / PedidosYa / ambos)
- 8.4 — How many cash registers / tablets
- 8.5 — Receipt printer type
- 8.10 — Daily vs weekly cash close
- 10.2 / 10.3 — Promotions or combos day-1
- 14.1 — Opening date
- 14.2 — Pilot test before opening?
- 14.3 — Staff on-site day 1
- 14.4 — Preferred support channel

### 3.4 Product catalog (blocks `Product` filtering)

- 5.1.1 — 5.1.22 — Which 22 of 32 seed products to enable day-1
  (A/B/C decision per product)
- 5.1 — Override prices for any of the 22
- 5.2 — Any new products to add (with name + price + category)
- 5.3 — Are the 8 seed categories OK as-is
- 5.4 — Per-product IVA / R.S.P.A. / unit-vs-weight config

### 3.5 Inventory (blocks `Ingredient` overrides)

- 6.1 — Which 5 of 5 seed suppliers to use
- 6.2 — Any new suppliers to add
- 6.3 — Initial stock for 5 critical ingredients
- 6.4 — Any custom ingredients not in the 102-row seed

### 3.6 Deferrable to month 3-6 (per the doc itself)

The questionnaire's tail explicitly lists §15, §16, §18, §20, §21,
§22 as "lo que podés saltearte al inicio". §17 was implicitly
deferrable too (she has 1 person).

## 4. Decisions that need Iván (the developer-operator)

These are **escalations** to Iván per the AGENTS.md "Decision
framework". I am NOT making these calls in this doc.

### 4.1 The brand-name conflict (HIGHEST PRIORITY)

The questionnaire has two answers that conflict with the product
brand:

- 1.1 — Razón social: `La Vaquita Holandesa S.A.` ← the business
- 1.2 — Nombre comercial: `Sazón` ← the product name

Today, the Sazon product is named "Sazón" and the per-client
instance would render "Sazón" in the sidebar / tickets / PDF.
Saskia has been operating as "La Vaquita Holandesa" with Sazon
as the **product** (not her business name).

**Three options**:

- (a) Set `branding.business_name = "La Vaquita Holandesa"`. The
  instance shows her business name everywhere. Product remains
  "Sazón" only in developer-facing contexts.
- (b) Set `branding.business_name = "Sazón"`. The instance shows
  "Sazón" in the UI. La Vaquita is only the legal/operational
  name.
- (c) Set `branding.business_name = "Sazón - La Vaquita
  Holandesa"`. Hybrid.

> **I cannot decide this.** It affects Saskia's workflow, her
> customer-facing branding, and possibly her tax documentation.
> Per AGENTS.md "ASK Iván before doing: Decisions that affect
> Saskia's workflow (UI/UX, copy, what buttons to add)", this is
> a direct escalation. Recommend bringing it up with her on the
> next WhatsApp call.

### 4.2 Multi-tenant readiness (SUPERSEDED by 2026-10-12 OOB)

The questionnaire's Apéndice A frames everything in multi-tenant
language (e.g. "se carga en Tenant, SettingsKV (branding.*) y
ComplianceInfo.razon_social / nombre_fantasia").

**Earlier framing (wrong)**: SASKIA-210 (2026-10-07) decided
Sazon is per-client INSTANCES, not shared-DB multi-tenant. The
`Tenant` table was marked as legacy dormant infrastructure.

**Current framing (correct)**: The 2026-10-12 OOB message
("la vaquita holnadesa iis a just the first client later we
will have many more") reframes the product as multi-tenant
from the start. The `Tenant` table is now the **active
multi-tenant target**, and the multi-tenant seeding is already
implemented via `app/rms/seed/onboard.py::onboard_tenant(session,
tenant_name, pack, days_of_history, seed)` + the 11 packs in
`app/rms/seed/packs.py::PACKS`.

**What changes for this onboarding**: La Vaquita's instance is
a row in the `Tenant` table created by `onboard_tenant()` or
`seed_sazon()`. The legacy `Tenant` table is now the right
target for per-instance rows, not legacy infrastructure.

**What does NOT change yet**: RLS / ORM-level tenancy (every
table gets a `tenant_id` foreign key, every query auto-filters
by `tenant_id`). That's a separate, much larger refactor. The
current "one client per VPS" deployment model still works
because each client gets their own DB.

**What to do with this doc**: when the actual onboarding work
starts, use `onboard_tenant()` as the entry point, not
`seed_sazon()` directly. `seed_sazon()` becomes a thin
La-Vaquita-specific wrapper. See SASKIA-214 for the
per-instance BUSINESS_INFO + user roster refactor.

### 4.3 Whether to add the new models / settings at all

The questionnaire's Apéndice A says 4 new models
(`Insurance`, `Employee`, `Payroll`, `SeasonalEvent`,
`GrowthPlan`) and ~10 new settings
(`shop_whatsapp`, `location.barrio`, `seasonal.notif_lead_days`,
etc.) are "to create".

**For La Vaquita specifically**:

- `Insurance` — §18 is all TBD. She can launch without it.
- `Employee` / `Payroll` — §17.1 = 1. No payroll for this
  instance. Can defer the models entirely.
- `SeasonalEvent` — §16.1 = si, §16.5 = si, §16.6 = si. She'd
  benefit from the model, but the doc itself defers §16 to month
  3-6. Decision: build the model now or later?
- `GrowthPlan` — §21.1 = 1 (one local), §21.5 = no (no
  franchise), §21.6 = no (no export). The model would store
  almost nothing. Decision: build the model now or later?
- New settings (`shop_whatsapp`, `location.*`, `seasonal.*`) —
  each is a small addition. Decision: batch all settings into
  one PR, or one-at-a-time, or skip until a real second client
  needs them?

**What I recommend in this doc**: defer ALL new model/settings
work until a **second** client needs it. La Vaquita can launch
with the existing 68-setting registry; the unanswered fields
(brand name, opening date, RUC, etc.) are configuration
questions, not schema questions.

### 4.4 The migration 117 / "156 imágenes" claim

The doc says: "Corro la migración 117 que conecta los 156
imágenes a la DB."

**Verify before claiming**: as of 2026-10-09, the current
schema version is around 116-117 depending on which session
landed what. The "156 imágenes" claim predates the current
schema. If we promise this in the onboarding PR, we need to
**first** confirm migration 117 exists in `app/rms/db.py` and
**second** confirm it actually attaches 156 images to a real
business.

Per the AGENTS.md rule "Drift between repo docs and repo state":
never trust doc claims of "X is at version Y" without grepping
the source of truth.

### 4.5 The §19 Alérgenos / Sin Gluten promise

§19.4 = sí (etiquetar alérgenos comunes), §19.6 = sí (iconos en
menú público). The Apéndice A says "Product.allergens +
Certification (ya existe columna)".

**Verify before claiming**: confirm `Product.allergens` column
exists in the current schema, and that the public menu template
renders the icons. If either is missing, this is a
**SASKIA-NNN** ticket, not a 1-line config change.

## 5. What this doc does NOT do (explicit non-recommendations)

To be unambiguous about scope:

- **Does not recommend a PR.** The doc is a read-time analysis
  capturing what Saskia answered and what the schema looks like
  today. Writing code is a separate, ticket-driven activity.
- **Does not recommend new models.** The 4 "crear" models
  (`Insurance`, `Employee`, `Payroll`, `SeasonalEvent`,
  `GrowthPlan`) are not needed for La Vaquita's day-1 launch per
  her own answers (§17.1 = 1, §21 = solo mostrador, §18 = TBD).
- **Does not recommend new settings.** The 4-5 new settings
  (`shop_whatsapp`, `location.*`, `seasonal.*`) are not needed
  for day-1. They can be added when a real second client
  needs them.
- **Does not recommend a brand-new seeder file.** The
  multi-tenant seeding pattern is **already implemented**:
  `app/rms/seed/onboard.py::onboard_tenant(session, tenant_name,
  pack, days_of_history, seed)` creates a fully-seeded instance
  in one call. The 11 packs in `app/rms/seed/packs.py::PACKS`
  cover the major restaurant segments (Pizzería, Panadería,
  Café/Cafetería, etc.). For the second client (Café? Pizzería?
  Catering?) you call `onboard_tenant(session, "Cliente 2",
  pack="Pizzería")` and get a fully-loaded instance. **No new
  seeder file is needed for the next client** — the Sazon
  architecture is already multi-tenant-ready.
- **The La Vaquita-specific seeder** (`app/rms/seed/sazon.py`)
  is fine for La Vaquita (Sazon's first client) but should be
  refactored (SASKIA-214) to call `onboard_tenant()` internally
  with La Vaquita's `BUSINESS_INFO` + `CASHIER_USERS` as
  parameters, so the same code path serves all clients.
- **Does not recommend any code change that touches Saskia's
  data.** Per AGENTS.md "ESCALATE: Anything that involves
  Saskia directly".

## 6. Schema gap inventory (for ticket triage, not for action)

For completeness, here's the full gap table. **Nothing here
implies a PR** — these are all candidates for future tickets if
Iván decides to build them.

### 6.1 Models that exist today (no action needed)

| Model | Location | Status |
|-------|----------|--------|
| `Tenant` | `app/rms/models_legacy.py:1988` | ✅ **active multi-tenant target** post-OOB-2026-10-12 (was legacy dormant pre-OOB per SASKIA-210) |
| `ComplianceInfo` | `app/rms/models_legacy.py:2066` | ✅ exists, has DNIT/INAN columns |
| `SettingsKV` | `app/rms/models_legacy.py:1751` | ✅ exists, JSON-backed, multi-tenant friendly via `key` namespace |
| `User` | `app/rms/models_legacy.py:761` | ✅ exists, bcrypt cost-12 |
| `Product` | `app/rms/models_legacy.py:371` | ✅ exists, 32-product seed |
| `Ingredient` | `app/rms/models_legacy.py:55` | ✅ exists, 102-row seed |
| `Supplier` | `app/rms/models_legacy.py:1214` | ✅ exists, 5-row seed |
| `Recipe` | `app/rms/models_legacy.py:275` | ✅ exists, 22-row seed |
| `Customer` | `app/rms/models_legacy.py:890` | ✅ exists, 10-row seed |
| `BankTransaction` | `app/rms/models_legacy.py:1713` | ✅ exists, 8-row seed |
| `Pedido` | `app/rms/models_legacy.py:1767` | ✅ exists, supports encargos |

**Multi-tenant readiness**: The `Tenant` table is the row-level
container. The `SettingsKV` table keys (e.g.
`branding.business_name`, `sales.shop_whatsapp`) are global
within a single DB, but each instance has its own DB in the
"one client per VPS" deployment model. When the
shared-DB-multi-tenant RLS refactor lands, the
SettingsKV keys will need to scope by `tenant_id` (separate
ticket).

### 6.2 Settings that exist (68 total in 13 groups)

`app/rms/settings_registry.py` — `general.*` (7), `branding.*` (8),
`inventory.*` (5), `sales.*` (5), `pre_sale.*` (3), `dashboard.*`
(5), `backup.*` (5), `session.*` (3), `demo.*` (2),
`production.*` (1), `loyalty.*` (10), `eod.*` (3), `alerts.*` (1),
`rate_limit.*` (5).

### 6.3 Things the questionnaire references but that DON'T exist

These are **candidates** for future tickets. None are
recommended for La Vaquita's day-1 launch.

| Thing | Source | Not needed for day 1? | Notes |
|-------|--------|----------------------|-------|
| `Insurance` model | §18 | ✅ deferrable | §18 is all TBD |
| `Employee` model | §17 | ✅ not needed | §17.1 = 1 |
| `Payroll` model | §17 | ✅ not needed | §17.1 = 1 |
| `SeasonalEvent` model | §16 | ⚠️ she answered but doc defers §16 to 3-6mo | if built, add Semana Santa 2027 + Navidad 2027 + 13 PY holidays + 2 Dutch holidays (King's Day, Pride) |
| `GrowthPlan` model | §21 | ⚠️ she answered but value is minimal | §21.1=1, §21.5=no, §21.6=no — the row would store almost nothing |
| `sales.shop_whatsapp` setting | §8.1 | ⚠️ referenced in Apéndice A but missing from registry | the value would just be `+595 991 683805` |
| `location.barrio` setting | §22.1 | ⚠️ same | value = "San Lorenzo" |
| `location.zona` setting | §22.2 | ⚠️ same | value = "Residencial" |
| `seasonal.notif_lead_days` setting | §16.6 | ⚠️ same | value = 30 |
| `recipe.labor_cost_enabled` setting | §7.4 | ⚠️ same | also needs Recipe.prep_minutes/cook_minutes columns |
| `branding.opening_hours` setting | §2.7 | ⚠️ no opening-hours key today | value = "Martes a sabado de 9 am a 6 pm" |
| `branding.google_maps_url` setting | §2.8 | ⚠️ no Google Maps key today | she left TBD |
| `branding.business_type=gastronomico` | §1.8 | ⚠️ verify the enum value exists | check `branding.business_type` choices in the registry |
| Migration 117 ("156 imágenes") | App. closing | ⚠️ verify before promising | grep `app/rms/db.py` for migration 117 |

## 7. Operator action items (back to Iván → Saskia)

Per AGENTS.md "ESCALATE: Anything that involves Saskia
directly", this is a list of the WhatsApp/email messages Iván
should send to Saskia — **not a code change list**.

### 7.1 Before instance creation (blocking)

1. **Brand name decision** (§4.1) — call her. Options: La Vaquita
   Holandesa / Sazón / hybrid. She must decide.
2. **Logo / favicon / hero images** — send a WhatsApp asking her
   to attach the 3 files.
3. **Opening date** (§14.1) — needed to schedule the cutover.
4. **RUC + R.E. INAN + Timbrado** (§3) — needed for `ComplianceInfo`
   if she wants legal invoices. If she doesn't have them yet, the
   system can launch without them (only blocks legal invoices).
5. **Cajeros question** (§4.5) — confirm "no" is final, not
   placeholder. If "no", only seed 1 user.
6. **Product catalog** (§5.1) — which 22 of 32 to enable day-1.

### 7.2 After instance creation (non-blocking)

7. WhatsApp / Instagram / Google Maps / opening hours (already
   answered, can be added post-launch).
8. Payment method details (she answered efectivo+transferencia+QR;
   confirm Tigo Money / Personal Pay / etc. are also in scope).
9. Daily vs weekly cash close (§8.10) — affects the EOD cron.
10. Insurance / seguros (§18) — defer to month 3-6.
11. MIPYME MIE registration (§20) — affects INAN R.E. cost (50%
    discount); can be done before or after.

## 8. Reference

- This doc: `docs/operations/2026-10-09-la-vaquita-onboarding-analysis.md`
- Source docx: `/opt/data/profiles/ivan/attachments/2026-10-08-la-vaquita-feliz-onboarding-questionnaire.md.docx`
- Existing settings registry: `app/rms/settings_registry.py` (68
  settings, 13 groups — see `app/rms/settings.py` for the
  per-instance override layer via `Setting()` rows)
- Existing models: `app/rms/models_legacy.py` (40+ models; `Tenant`
  is the **active multi-tenant target** post-OOB-2026-10-12)
- Multi-tenant seeder (THE entry point for new clients):
  `app/rms/seed/onboard.py::onboard_tenant(session, tenant_name,
  pack, days_of_history, seed)`
- Pack catalog (11 market segments): `app/rms/seed/packs.py::PACKS`
- La Vaquita-specific seeder (Sazon's first client):
  `app/rms/seed/sazon.py` (refactor target: SASKIA-214)
- Brand name decision: see §4.1 of this doc; requires
  Iván → Saskia call.
- SASKIA-213 (the placeholder-replacement PR already shipped):
  `docs/intake/SASKIA-213-vaquita-seed-data-update.md`
- SASKIA-214 (the per-instance config refactor, drafted):
  `docs/intake/SASKIA-214-per-instance-business-info.md`

## 9. "Load all the things" — what the OOB directive means in code

The 2026-10-12 OOB message said **"the website of sazon should
load all of the thigns"** (referring to the data La Vaquita
provided in the questionnaire) and clarified the multi-tenant
direction with **"la vaquita holnadesa iis a just the first
client later we will have many more"**.

**What "all the things" maps to in code** (already exists,
verified by running `seed_sazon()` against a fresh DB on
2026-10-12):

| Thing | Where it loads | Status today |
|-------|----------------|--------------|
| Tenant name "La Vaquita Holandesa" | `Tenant` table + `branding.business_name` SettingsKV | ✅ seeded by SASKIA-213 |
| Address / phone / email | `branding.address` / `contact_phone` / `contact_email` SettingsKV | ✅ seeded by SASKIA-213 |
| Business hours | `ops.business_hours` SettingsKV | ✅ seeded by SASKIA-213 |
| Operator name + email | `User.full_name` + `User.email` | ✅ seeded by SASKIA-213 |
| Footer copyright year | `branding.footer` SettingsKV | ✅ seeded by SASKIA-213 (2025 → 2026) |
| 32 products (Babka, Bizcocho, etc.) | `Product` table | ✅ seeded by `seed_sazon` (from `PRODUCTS` list) |
| 22 recipes | `Recipe` + `RecipeLine` tables | ✅ seeded by `seed_sazon` |
| 101 ingredients | `Ingredient` table | ✅ seeded by `seed_sazon` (from `INGREDIENTS` list) |
| 5 suppliers | `Supplier` table | ✅ seeded by `seed_sazon` (from `SUPPLIERS` list) |
| 15 customers | `Customer` table | ✅ seeded by `seed_sazon` (Saskia said §9.2 = no but the demo path includes some) |
| 4 delivery zones | `DeliveryZone` table | ✅ seeded by `seed_sazon` |
| 9 payment methods | `PaymentMethod` table | ✅ seeded by `seed_sazon` |
| 10 channels (mostrador, whatsapp, etc.) | `Channel` table | ✅ seeded by `seed_sazon` |
| 21 production plan templates | `ProductionPlanTemplate` table | ✅ seeded by `seed_sazon` |
| 32 categories | `Category` table | ✅ seeded by `seed_sazon` |
| 13 message templates | `MessageTemplate` table | ✅ seeded by `seed_sazon` |
| Compliance info (RUC, INAN, Timbrado) | `ComplianceInfo` table | ⚠️ seeded with placeholders (RUC `80012345-6`, Timbrado `13456789`, etc.) because questionnaire §3 is all TBD |
| Seasonal events (Semana Santa, Navidad) | `SeasonalEvent` table | ❌ model doesn't exist; §16 answered but the data can't be persisted yet |
| Insurance policies | `Insurance` table | ❌ model doesn't exist; §18 all TBD anyway |
| Employee + Payroll | `Employee` + `Payroll` tables | ❌ models don't exist; §17.1 = 1 (Saskia solo) so not needed for this tenant |
| Growth plan (3-year, franchise) | `GrowthPlan` table | ❌ model doesn't exist; §21 answered but value is minimal |
| Location barrio/zona | `location.barrio` + `location.zona` settings | ❌ settings don't exist; §22 answered |
| WhatsApp for orders | `sales.shop_whatsapp` setting | ❌ setting doesn't exist; §8.1 answered (`+595 991 683805`) |
| Recipe labor cost | `recipe.labor_cost_enabled` + `recipe.labor_cost_per_hour_gs` settings + `Recipe.prep_minutes` column | ⚠️ settings don't exist; column DOES exist (added in migration 116) but no UI to set it |
| Alérgenos (iconos en menú público) | `Product.allergens` column | ⚠️ column exists; UI doesn't render icons yet |
| Bank transactions | `BankTransaction` table | ✅ seeded by `seed_sazon` (8 rows) |
| Pedidos (encargos) | `Pedido` + `PedidoLine` tables | ✅ seeded by `seed_sazon` (13+14 rows) |
| Ventas (90 días sintéticos) | `Sale` + `SalePayment` tables | ✅ seeded by `seed_sazon` (869 sales) — but Saskia said §10.1 = no, so this is wrong for her instance |

**Summary**: ~75% of what "all the things" means is already
loaded by the seeder today (post-SASKIA-213). The remaining 25%
breaks down into:

- **Configuration with real values** (settings that exist but
  the seeder doesn't populate): ComplianceInfo placeholders
  (RUC, INAN, etc. — all TBD anyway), bank transactions (8
  placeholder rows — should be 0 per §12), 90 days of synthetic
  sales (Saskia said no — should be 0 per §10.1)
- **Models that don't exist yet**: SeasonalEvent, Insurance,
  Employee, Payroll, GrowthPlan
- **Settings that don't exist yet**: sales.shop_whatsapp,
  location.barrio, location.zona, seasonal.notif_lead_days,
  recipe.labor_cost_*
- **UI that doesn't render yet**: Public menu alérgenos icons
  (§19.6 = sí)

**Multi-tenant implications for the OOB directive**: the seeder
is La-Vaquita-specific (`sazon.py` hard-codes the tenant name,
address, etc.). The OOB's "many more clients" requires
`seed_sazon()` to become `onboard_tenant()` + per-instance
`BUSINESS_INFO` + per-instance `user_roster` parameters. That's
the SASKIA-214 work.

**What needs to happen for the live website to actually show
all this** (not just the test env):

1. **Re-seed the live VPS test/dev DBs** with the SASKIA-213
   constants. The current state of `sazon-vps.paragu-ai.com`
   is DOWN (RC=7) — needs to come up first. Then the
   operator script `scripts/seed_vaquita_holandesa_for_saskia.py`
   needs to run against the live DB (with `--force` to override
   the populated-DB guard).
2. **Decide the brand-name display** (§4.1) — does the
   customer see "La Vaquita Holandesa" (her business) or
   "Sazón" (the product) in the UI? This is a UX decision
   for Iván with Saskia.
3. **Add the missing models + settings** (SASKIA-215+) so the
   unanswered-but-schema-needed questions can be persisted.
4. **Implement SASKIA-214** so adding "Cliente 2" doesn't
   require editing `sazon.py`.
