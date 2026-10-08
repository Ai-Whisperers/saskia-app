# La Vaquita Feliz — Pre-Launch Seed Reconciliation

**Date:** 2026-10-08
**Owner:** Iván
**Status:** DRAFT — pre-launch
**Client:** Saskia Weiss Vander (La Vaquita Feliz / La Vaquita Holandesa)
**Context:** Bakery has NOT opened yet. No real sales history exists. We need to
seed a believable, complete demo dataset that Saskia can run against on day 1
and that we can swap to real data as her first transactions come in.

---

## TL;DR

We have THREE sources of truth to reconcile:

1. **Seed (authoritative)** — `app/rms/seed/sazon.py` — the live code that
   populates a fresh DB. 94 ingredients, 22 recipes, 31 products, plus
   suppliers/customers/channels/etc.
2. **Workbook (canonical)** — `data/herebus_seed_canonical.json` — the Excel
   workbook Saskia's operator exported. 28 sheets, 22 recipes, 94 inventory items.
3. **Catalog (image-gen)** — `data/images/items.json` — what the AI image
   pipeline needs to generate. Built from the seed, 22 base products + 9 variants
   + 94 ingredients.

**Bottom line:** The seed is the source of truth. The canonical workbook has
**four real gaps** to close (margins, packaging items, packaging variants per
recipe, the dupe REC-006). Everything else is consistent.

---

## Section 1 — What matches between the two seeds

| Item | Seed | Canonical | Match? | Notes |
|---|---|---|---|---|
| Ingredients | 94 | 94 | ✅ | Names + prices match. Seed has more compliance detail. |
| Recipes | 22 | 22 | ⚠️ | Same count. Canonical has REC-006 listed twice (frikandel + bitterballen) — workbook bug. Seed is correct: frikandel is rec_022, bitterballen is rec_006. |
| Recipe ingredients | 208 lines | varies per recipe | ✅ | All 22 recipes covered. Babka has 11 ing in canonical, 11 in seed. Stroopwafel 12/12. |
| Categories_product | 6 | (uses 4 in the workbook) | ✅ | Seed has 6 (Panadería, Pastelería, Salados, Bebidas, Especiales, Tortas). Workbook only uses 4 of them; the extra 2 are forward-looking. |
| Categories_recipe | 5 | n/a | ✅ | Masa dulce, Masa salada, Hojaldre, Bizcocho, Crema. |
| Suppliers | 5 | n/a | ✅ | Distribuidora El Molino, Lácteos Paraguay, Frutas del Sur, Dulcería Santa Rita, Embalajes Express. |
| Customers | 15 | n/a | ✅ | 15 distinct customers (the rest of the field count was tuple fields, not customers). |
| Channels | 6 | n/a | ✅ | Mostrador, Mostrador (encargo), and 4 more. |
| Delivery zones | 4 | n/a | ✅ | Centro, Recoleta, Villa Morra, + 1 more. |
| Payment methods | 7 | n/a | ✅ | efectivo, tarjeta, transferencia, + 4 more. |
| Pedidos (sample) | 13 | n/a | ✅ | All "fulfilled" or "ready" — no real history needed. |
| Production templates | 21 | n/a | ✅ | Per-recipe + per-variant. |
| Message templates | 11 | n/a | ✅ | WhatsApp templates. |
| Compliance/HACCP | 94 | n/a | ✅ | One per ingredient (HACCP_TEMP_MIN_C etc.). |
| Storage types | 5 | n/a | ✅ | dry, fresh, ambient, + 2 more. |
| Stock statuses | 5 | n/a | ✅ | ok, low, out, + 2 more. |
| Benchmarks | 16 | n/a | ✅ | Market price benchmarks per category. |
| Margin tiers | 5 | 3 per recipe (WHOLESALE, RETAIL, EVENTUAL) | ⚠️ | See Section 2. |
| Freezer temp days | 16 | n/a | ✅ | Per category. |
| Date presets | 6 | n/a | ✅ | hoy, ayer, + 4 more. |
| Business info | 4 fields | n/a | ⚠️ | Seed has placeholder ("Av. España 1234", "hola@lavaquita.example", "+595 21 555-1000"). See Section 3. |

**Total: ~25 sections, 20 fully matched, 3 with notes (acceptable), 4 with real gaps.**

---

## Section 2 — Real gaps in the seed (vs canonical)

### Gap 2.1 — Margins are NOT in the seed

**What the canonical has (per recipe):**
```json
{
  "rec_id": "REC-017",
  "margins": {"WHOLESALE": 0.30, "RETAIL": 0.50, "EVENTUAL": 0.35}
}
```

**What the seed has:** a flat price in PRODUCTS. No margin calculation per channel.

**Why this matters:** The app has `MARGIN_TIERS` and `CHANNELS` (mostrador vs mostrador-encargo vs etc.). Margins should drive `MARGIN_TIERS` for the operator to know "if I sell via this channel at this margin, my COGS covers X%".

**Fix:** Add a `MARGINS` dict to the seed keyed on recipe_slug, value `{WHOLESALE, RETAIL, EVENTUAL}`. Then the seed function reads it and updates the per-product price on the products where margin applies.

**Estimate:** 30 min. 1 new section, 1 new line in the seed function.

---

### Gap 2.2 — Packaging items are NOT in the seed as a separate concept

**What the canonical has (7 items in `packaging`):**
- MAT-01 bolsita de 15x22 (saco pp cromus incoloro cant 100) — Gs. 24,918
- MAT-02 cintillo 7mm 10m
- MAT-03 bandeja isopor
- MAT-04 bandeja carton
- MAT-05 papel antigrasa blanco
- MAT-06 bolsa de papel mediana
- MAT-07 caja torta 25cm

**What the seed has:** Nothing. No "packaging" list, no packaging items. The 9 L-SKU products in PRODUCTS are "package variants" (docena_X, X_entera) but they reuse the base recipe's image and don't have a separate packaging inventory line.

**Why this matters:** When Saskia bakes a Babka entera, she uses a `caja torta 25cm`. The BOM should subtract that from packaging inventory. The seed doesn't model this.

**Fix:** Add `PACKAGING_ITEMS` to the seed as 7 entries (matching the canonical). Add a `RECIPE_PACKAGING` table mapping recipe_slug → packaging_item_id × qty. Update `apply_sale()` to decrement both recipe_ingredients AND recipe_packaging.

**Estimate:** 2 hours. 1 new section + 1 new table + 1 update to apply_sale().

---

### Gap 2.3 — Packaging variants per recipe are partial

**What the canonical has (per recipe):**
```json
{
  "rec_id": "REC-017",
  "packaging": [{"name": "Cantidad packs", "qty": "Unidad", "unit_price": "Precio pack ₲"}]
}
```

The canonical packaging field is **per-recipe** but is incomplete: 18/22 recipes have it, 4/22 do not (REC-019 goulash crockettes, REC-021 suppli, REC-020 bitterballen vegetariano, REC-006 bitterballen — those are the bulk-only ones).

**What the seed has:** 9 L-SKU products in PRODUCTS that match this concept. The 13 that aren't L-SKU are unit-only.

**Mismatch:** Canonical's "Cantidad packs" is a per-recipe concept. The seed's L-SKU products are per-product. They should be reconciled — either make products have a `packaging_id` foreign key, or make the seed drop the L-SKU duplication and use the canonical packaging list.

**Fix:** Add a `packaging_id` to PRODUCTS (nullable, only for L-SKU products). The seed's L-SKU products map 1:1 to canonical's "Cantidad packs" entries.

**Estimate:** 1 hour. 1 new column in PRODUCTS, 1 new line in `seed_products()`.

---

### Gap 2.4 — REC-006 listed twice in canonical (workbook bug)

**The canonical workbook has:**
- REC-006: Frikandel (100 unidades)  ← wrong, frikandel is REC-022 in seed
- REC-006: bitterballen ← correct

**This is a workbook import bug, not a seed gap.** The seed has:
- frikandel_100_unidades__rec_022 (correct)
- bitterballen__rec_006 (correct)

**Fix:** Re-export the workbook with the corrected rec_ids. Or just ignore — the seed is authoritative and the canonical is reference-only.

**Estimate:** 0. Skip — seed wins.

---

## Section 3 — Saskia-specific data to set up

These are fields in `BUSINESS_INFO` and `TENANT_*` that are placeholder. They
need to be filled in before launch with the real data. Currently:

```python
BUSINESS_INFO: dict[str, str] = {
    "business_hours": "Lunes a sábado 7:00-19:00, domingo 8:00-13:00",  # placeholder
    "address": "Av. España 1234, casi Brasil, Asunción",                  # placeholder
    "phone": "+595 21 555-1000",                                          # placeholder
    "email": "hola@lavaquita.example",                                    # placeholder
}
TENANT_NAME = "La Vaquita Feliz"  # could be "La Vaquita Holandesa" — ask
TENANT_SLUG = "la_vaquita_feliz"   # could be "la_vaquita_holandesa" — ask
TENANT_COLOR = "#7b3f00"           # warm brown — matches aesthetic, but could be Delft blue
```

**What we need from Saskia before launch:**
1. Real address (she hasn't picked one yet — she's still setting up the home kitchen)
2. Real phone / WhatsApp
3. Real email
4. Confirm: "La Vaquita Feliz" or "La Vaquita Holandesa"?
5. Hours (will probably be different from placeholder)
6. Logo / branding colors (placeholder brown is fine for now)

**What we can prep WITHOUT Saskia:**
- Confirm the brand name internally (Saskia uses "La Vaquita" colloquially — could be "La Vaquita Feliz" or "La Vaquita Holandesa" depending on which feels right)
- Set up a vanity email routing (lavaquitafeliz.com or similar)
- Pre-load the kitchen with the recipe catalog (done — 22 recipes ready)
- Pre-load the ingredient pantry (done — 94 items)
- Pre-create the supplier accounts (5 Paraguayan distributors)
- Pre-create the delivery zone map (Asunción centro + 3 surrounding)
- Pre-create a training customer list (15 example customers — for the operator demo)
- Pre-create a sample pedido history (13 pedidos from "last 30 days" — synthetic but realistic)

---

## Section 4 — What we should ALSO set up for pre-launch

These aren't gaps in the seed, but are necessary to make the app usable
day 1. The user is asking for the FULL pre-launch setup.

### 4.1 — Visual assets (images)

**Status:** In progress. Image-gen pipeline shipped in commit `9420106c`,
research-backed descriptions in `d8fadabf`. **Currently running 22 product
generations (~10 min remaining).** Then 94 ingredient generations (~40 min).

**End state:**
- 22 product images in `app/static/products/<slug>.jpg`
- 22 product images in `app/static/recipes/<slug>.jpg` (same image, per user request)
- 94 ingredient images in `app/static/ingredients/<slug>.jpg`
- 9 packaging-only products reuse the base recipe's image (no new gen)

**Open question:** Tompoouce is generating as French mille-feuille instead of
Dutch tompouce (no pink fondant icing). 9 attempts failed. Workaround: use the
best-of-candidates that have correct shape + cream + pastry, accept missing pink
topping. Or use a stock photo for the tompouce specifically.

### 4.2 — Email / WhatsApp

**Status:** Deferred. The app supports WhatsApp integration (CHANNELS list) but
Saskia doesn't have a business WhatsApp number yet.

**What we need:**
- WhatsApp Business API credentials (when she picks a number)
- An IMAP/SMTP account for order notifications
- A transactional email service (Resend is configured per skill `saskia-observability`)

### 4.3 — Payment processor

**Status:** Seed has 7 payment methods (efectivo, tarjeta, transferencia, etc.)
but no real merchant account is configured.

**What we need when she opens:**
- Tigo Money / Personal Pay / Bancard merchant account for cards
- Bank account for transfers

### 4.4 — Backup schedule

**Status:** Configured per AGENTS.md rule 17. Daily backup at 03:15, 14-day
retention, fails-closed if backup fails.

**For pre-launch:** Verify the cron is running on the VPS, confirm the backup
location is mounted, do a dry-run restore test.

### 4.5 — Observability

**Status:** Sentry + Resend are configured per `saskia-observability` skill.
Sentry DSN is in BWS. Resend API key is in BWS.

**For pre-launch:** Send a test alert to confirm the integration works, and
verify the on-call rotation (just Iván, since this is pre-launch).

### 4.6 — Operator training data

**Status:** The seed populates 13 synthetic pedidos in the last 30 days, 15
example customers, 5 suppliers, and 21 production templates. This is the demo
content the operator will see on day 1.

**For pre-launch:** Add a "tour" guide (markdown doc) that walks Saskia
through the UI step by step. The `saskia-observability` skill mentions this.

### 4.7 — Menu / price sign-off

**Status:** All 31 products have prices. The seed has wholesale vs retail
implied via PRODUCTS but no explicit pricing tier per channel.

**For pre-launch:** Saskia needs to confirm the 31 prices are what she wants
to charge on opening day.

### 4.8 — Recipe photo verification

**Status:** Once the 22 product images are generated, Saskia should review them
and confirm they look like what she bakes. If not, we need to either re-generate
or use real photos.

**For pre-launch:** Schedule a 30-min review with Saskia once the image batch
completes.

### 4.9 — Domain & hosting

**Status:** Per `aiw-cloudflare-deployment` skill, the app is at
`sazon-vps.paragu-ai.com` via Traefik + Cloudflare DNS-01.

**For pre-launch:** Saskia needs to decide on her customer-facing domain.
Options: `lavaquitafeliz.com.py` / `lafeliz.com.py` / use a subdomain of
paragu-ai.

### 4.10 — Compliance / regulatory

**Status:** The seed has 94 HACCP entries (one per ingredient) and freezer
temp monitoring. HEM-Bromatología (Paraguay health regulator) requires food
handler training for bakery staff.

**For pre-launch:** Confirm Saskia has her bromatología certificate and that
her home kitchen meets the requirements for a home-based food business.

---

## Section 5 — Open questions for Saskia

To complete the pre-launch setup, we need answers to:

1. **Brand name:** "La Vaquita Feliz" or "La Vaquita Holandesa"?
2. **Address:** Where is the home bakery? (we need this for delivery zone setup)
3. **Phone / WhatsApp:** What's the business contact number?
4. **Email:** Personal email or set up a business one?
5. **Customer-facing domain:** Buy a .com.py or use paragu-ai subdomain?
6. **Opening date:** Target date for going live?
7. **Initial hours:** What hours will the bakery be open?
8. **Payment methods:** Confirm which of the 7 in the seed to enable.
9. **Delivery zones:** Are the 4 seed zones right? Add more?
10. **WhatsApp Business:** Already set up? Need credentials?
11. **Photos:** Will she provide her own product photos, or use AI-generated?

---

## Section 6 — Timeline (recommended)

| When | What | Owner |
|---|---|---|
| Now → Oct 9 | Finish image generation (22 + 94). Commit. | Iván |
| Oct 9 | Generate packaging item images (7 items). | Iván |
| Oct 9 | Close seed gaps: add MARGINS, PACKAGING_ITEMS, RECIPE_PACKAGING. Run migrations 115, 116, 117. | Iván |
| Oct 10 | Email Saskia the 10 open questions. | Iván |
| Oct 11–12 | Saskia answers. | Saskia |
| Oct 13 | Update seed + config with real business info. Re-run seed against fresh DB. | Iván |
| Oct 14 | Run a full end-to-end demo: place a pedido, record a sale, verify stock decrements, take a backup, restore from backup. | Iván |
| Oct 15 | Hand off to Saskia. Walk through the UI. | Iván + Saskia |
| Oct 16+ | Soft launch (if opening on Oct 20). | Saskia |

---

## Section 7 — Files referenced

- `app/rms/seed/sazon.py` — the seed (authoritative)
- `data/herebus_seed_canonical.json` — the canonical workbook (reference)
- `data/images/items.json` — the catalog for image generation
- `docs/operations/2026-10-08-vaquita-image-template.md` — visual template
- `docs/operations/2026-10-08-image-gen-runbook.md` — image-gen runbook
- `app/CHANGELOG.md` — change log (must update for any seed change)
- `AGENTS.md` — hard rules for the repo

---

## Section 8 — PR / branch

This work is on `feat/workbook-seed-reconciliation` (PR #79 follow-up).
The image pipeline is shipped. The seed reconciliation doc is shipped.
The remaining gaps (margins, packaging items, packaging variants) are filed
as SASKIA-211, SASKIA-212, SASKIA-213 for the next sprint.
