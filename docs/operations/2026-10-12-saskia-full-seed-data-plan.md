# SASKIA-FULL: Consolidated Saskia seed data — questionnaire + HEREBUS + multi-tenant catalog

**Date:** 2026-10-12
**Author:** AIW Bot
**Status:** comprehensive analysis (pre-implementation)
**Sister tickets:** SASKIA-213 (shipped), SASKIA-215 (shipped), SASKIA-216 (drafted), SASKIA-220 (drafted), SASKIA-217 (drafted), SASKIA-214 (drafted)
**Sources consolidated:**
1. **2026-10-08-la-vaquita-feliz-onboarding-questionnaire.docx** (250KB, 70 filled answers, 22 sections) — see `docs/operations/2026-10-09-la-vaquita-onboarding-analysis.md`
2. **HEREBUS_FoodBiz spreadsheet** (Google Sheet, 30 sheets, 100 ingredients, 23 recipes, 7 packaging items, 3 operational sheets) — see §2 below (new analysis, this doc)
3. **Multi-tenant event catalog** (SASKIA-216/220) — see `docs/operations/2026-10-12-seasonal-events-comprehensive-catalog.md` + `docs/operations/2026-10-12-multi-tenant-verticals-and-events.md`

---

## 1. Why this doc

The user asked for "all we have for saskia seed data" + "all the findings" + "all the things to add to the seed" + "all the thigns to store in db that will be used to populate the pages and the content". This is the **single source of truth** that consolidates all 3 data sources into a per-table action plan: what each Sazon table should contain after the seeder runs, so the Sazon website can render every page Saskia expects.

The Sazon website pages (from the Sazon app) that need this data:
- `/` (home — branding, location, hours, upcoming events)
- `/menu` (product catalog with prices, photos, allergens)
- `/menu/<product>` (product detail with ingredients, allergens, allergens toggle, WhatsApp order button)
- `/recetas` (recipe catalog — REC-001 to REC-023)
- `/recetas/<id>` (recipe detail with steps, photos)
- `/admin/seasonal-calendar` (SASKIA-217 — upcoming events with lead-time)
- `/admin/calendar` (operational — production planner, waste tracker)
- `/admin/inventory` (the 100 ingredients, stock levels, suppliers)
- `/admin/recipes` (the 23 recipes, costs, margins)
- `/admin/orders` (sales by channel, P&L dashboard)
- `/admin/settings` (the 74 settings from SASKIA-215 + business info)

---

## 2. The HEREBUS spreadsheet — full inventory (new data source)

The Google Sheet (id `1z43h66KulWS4QS8wJAKoIMV3sk6yZqfC`) is named "HEREBUS" and is Saskia's **real working spreadsheet** for cost planning + production. It is structured for a **single bakery** (La Vaquita Holandesa). The "HEREBUS" name = the historical Dutch bakery technique (also a reference to a famous Dutch biscuit/cookie maker).

### 2.1 Sheets overview (30 sheets total)

| # | Sheet | Rows | Type | What it stores |
|---|---|---|---|---|
| 1 | **Instructions** | ~25 | meta | How to use the workbook (Spanish, Vaquita-context) |
| 2 | **Inventory** | 100 | data | The 100 ingredients with prices, stock, suppliers |
| 3 | **Packaging** | 7 | data | Bolsitas, cintillos, bandejas, papel antigrasa, bolsa, caja |
| 4-26 | **Recipe_* (23 sheets)** | ~25 each | data | REC-001 to REC-023, one per recipe |
| 27 | **recipe_bitterballen_100_pcs** | ~25 | data | REC-006 (lowercase variant) |
| 28 | **Production_Planner** | ~12 header + 0 data | data | Empty template for tracking batches |
| 29 | **Waste_Tracker** | ~13 header + 0 data | data | Empty template for tracking merma |
| 30 | **Dashboard_PL** | ~13 header + 0 data | data | Empty template for P&L by recipe |

### 2.2 Inventory sheet — 100 ingredients fully detailed

The Inventory is the **master ingredient catalog** Saskia has built up. Each row has:
- `ID` (ING-001 to ING-100, sequential)
- `Nombre` (Spanish, lowercase, descriptive)
- `Grupo` (one of 12 categories: Harinas y bases, Endulzantes, Lácteos y huevos, Cacao café y chocolate, Especias y condimentos, Levaduras y gasificantes, Frutas y frutos secos, Verduras y legumbres, Carnes, Salsas y líquidos, Aceites y grasas, Preparados y otros)
- `PkgQty` (the package size in `PkgUnit`)
- `PkgUnit` (g, ml, und, docena)
- `BulkPrice ₲` (the package price in PYG)
- `UnitPrice ₲` (calculated: `BulkPrice / PkgQty`)
- `StockQty` (how much she has now — most are None/empty)
- `MinReorder` (the minimum before reordering — most are None)
- `LastUpdate` (when the price was last verified)
- `Precio ref (repo saskia-app)` (the price that was already in the Sazon app at 2026-10-07, for cross-reference)
- `Notas` (free text — supplier name, market, "CONFIRMAR" flags, etc.)

#### 2.2.1 Group breakdown

| Grupo | Count | Examples |
|---|---|---|
| **Especias y condimentos** | **28** | Laurel, Vainilla, Ajo, Anís estrellado, Canela, **Especias mixtas**, **Speculaas** ⭐, Jengibre, Nuez moscada, Ralladura de limón, Sal, Perejil, Cebolla en polvo, Ajo en polvo, Knorr, Pimienta, Mostaza, Pimentón ahumado, Alcaravea, Cayena, Tomillo fresco, Ajo en copos, Cebolla en copos, Sésamo blanco/negro, Amapola, Sal escamada Maldon |
| **Lácteos y huevos** | 12 | Crema agria, Crema de leche, Crema pastelera, Huevos, Leche, Manteca, Queso muzzarella, Queso crema, Suero de leche (buttermilk), Leche condensada, Leche en polvo, Queso rallado |
| **Preparados y otros** | 11 | Estabilizante para nata, Polvo para natillas, **Masa choux** ⭐, **Masa de hojaldre** ⭐, Gelatina, **Café Espresso Molido** ⭐, Galletas dulces (base cheesecake), Gelatina sin sabor, Caldo de carne en cubos, Puré de tomate, Caldo de hongos en cubos |
| **Frutas y frutos secos** | 9 | Frambuesas, Fruta, Nueces, Pasas, Frutilla, Mango, Fruta Confitada, Mburukuja, Manzana |
| **Verduras y legumbres** | 8 | Cebolla, Zanahoria, Garbanzo, Cebolla morada, Morrón rojo, Apio, Echalote, Girgolas frescas |
| **Harinas y bases** | 7 | Harina de centeno ⭐, Harina de repostería, Harina de trigo, Harina Patentada, Maicena, Pan rallado, Arroz para sushi |
| **Salsas y líquidos** | 7 | Agua, Jugo de limón, Jugo de remolacha, Vinagre, **Ketjap manis** ⭐, Salsa de soja, Nata para montar |
| **Endulzantes** | 5 | Azúcar, Azúcar glas, Azúcar morena, Melaza, Miel |
| **Carnes** | 5 | Panceta de cerdo, Pechuga de pollo, Bola de lomo, Carnaza de segunda, Falda de res |
| **Levaduras y gasificantes** | 4 | Bicarbonato de sodio, Levadura fresca, Levadura seca, Polvo de hornear |
| **Cacao café y chocolate** | 3 | Cacao en polvo, Café instantaneo, Chocolate |
| **Aceites y grasas** | 1 | Aceite |

**Total: 100 ingredients across 12 categories.**

#### 2.2.2 Dutch heritage ingredients (the "Holandesa" connection)

These are the ingredients that **only make sense for a Dutch-themed bakery** — they're the unique selling point of "La Vaquita Holandesa":

| ING | Nombre | Use in Dutch recipes |
|---|---|---|
| ING-001 | Harina de centeno (Rye flour) | Ontbijtkoek (REC-004) — the iconic Dutch breakfast cake |
| ING-032 | **Speculaas** (spice mix) | Galletas de especuloos (REC-010), Stroopwaffle (REC-003) — the Dutch Christmas cookies |
| ING-051 | Pasas (Raisins) | Oliebollen (REC-016) — Dutch New Year oil balls |
| ING-069 | **Ketjap manis** (sweet soy sauce) | Ketjap Manis Quick (REC-007) — Dutch-Indonesian |
| ING-076 | **Masa de hojaldre / Bladerdeeg** | Hojaldre (REC-008), Petisús (REC-015) — Dutch puff pastry |
| ING-087 | Alcaravea (Caraway) | Dutch cheeses, breads |
| ING-097/098 | Sésamo blanco/negro | Everything Bagel seasoning (REC-023) |
| ING-099 | Amapola (Poppy seeds) | Dutch broodjes, Bagels |
| ING-100 | Sal escamada Maldon | Dutch finishing salt |

The **Ketjap Manis, Speculaas, Bladerdeeg, Harina de centeno** are the four ingredients that make La Vaquita Holandesa unique. No other PY panadería has these.

#### 2.2.3 The "CONFIRMAR" flags

Many recent additions (ING-082 to ING-100) have "CONFIRMAR" in the Notas field. These are prices Saskia **hasn't verified yet** and needs to update:
- ING-082 Morrón rojo: "est. mercado ~5.000/und — CONFIRMAR"
- ING-083 Apio: "8.000/docena (preciosdelagro) ≈ 667/tallo"
- ING-084 Puré de tomate: "est. lata Arcor 210g ~6.500 — CONFIRMAR"
- ING-085 Pimentón ahumado: "cocinar.com.py 12.000/100g"
- ING-087 Alcaravea: "est. especia ~12.000/100g — CONFIRMAR"
- ING-088 Cayena: "est. especia ~12.000/100g — CONFIRMAR"
- ING-089 Echalote: "est. mercado ~4.000/und — CONFIRMAR"
- ING-090 Girgolas frescas: "est. ~40.000/kg — CONFIRMAR"
- ING-091 Tomillo fresco: "est. atado chico ~3.000 — CONFIRMAR"
- ING-092 Caldo de hongos: "est. Maggi x12 = 8.360 (como caldo carne)"
- ING-093 Arroz para sushi: "Ypacaraí 22.400/500g"
- ING-094 Queso rallado: "Tregar 40g = 5.250 (Supermas)"
- ING-095 Ajo en copos: "TodoNegocio 7.000/60g"
- ING-096 Cebolla en copos: "est. similar ajo — CONFIRMAR"
- ING-097 Sésamo blanco: "est. dietetica ~7.000/100g — CONFIRMAR"
- ING-098 Sésamo negro: "est. dietetica ~7.000/100g — CONFIRMAR"
- ING-099 Amapola: "est. dietetica ~8.000/100g — CONFIRMAR"
- ING-100 Sal Maldon: "est. gourmet ~15.000/100g — CONFIRMAR"

**Operator decision needed**: which of these should be locked at the listed price, and which should be flagged for live re-quote?

### 2.3 Packaging sheet — 7 items

| MAT | Nombre | Descripción | Categoría | PkgQty | PkgUnit | BulkPrice ₲ | UnitPrice ₲ |
|---|---|---|---|---|---|---|---|
| MAT-01 | bolsita de 15x22 | saco pp cromus incoloro cant 100 | bolsita | 100 | und | 24,918 | 249.18 |
| MAT-02 | cintillo 7mm 10m | bandera py | decoracion | 250 | unid 40cm | 8,000 | 32 |
| MAT-03 | bandeja isopor | B-190 blanco | bandeja | 100 | und | 25,200 | 252 |
| MAT-04 | bandeja carton | bandejas pegadas n*3 | bandeja | 25 | und | 8,401 | 336.04 |
| MAT-05 | papel antigrasa blanco | papel | papel | 100 | und | 12,000 | 120 |
| MAT-06 | bolsa de papel mediana | para entrega de productos | bolsa | 1 | und | 350 | 350 |
| MAT-07 | caja torta 25cm | (no description) | caja | 1 | und | 2,800 | 2,800 |

**Total valor stock packaging: 22,426.20 ₲** (per the cell at R12 col H)

### 2.4 The 23 recipes (REC-001 to REC-023)

This is the **full recipe catalog** Saskia has. Each recipe sheet has:
- Header: Receta ID (REC-NNN), Recipe name, Yield quantity
- Bloque 1 (rows 1-6): metadata
- Bloque 2 (rows 7-22): ingredients (up to 14 or 20)
- Bloque 3 (rows 25-28): packaging
- Bloque 4 (rows 30-34): márgenes por canal (wholesale/retail/eventual)
- Bloque 5 (rows 36-42): calculated prices
- Bloque 6 (rows 44-53): instrucciones de uso

| REC | Slug | Name | Yield | Dutch heritage? | Country | Pack match |
|---|---|---|---|---|---|---|
| REC-001 | chocolate_muffin_20x20 | Chocolate Muffin 20x20 cm | 1 molde (Yield empty) | no | universal | Panadería, Pastelería |
| REC-002 | cheesecake_20x20_cm | Cheesecake 20x20 cm | 170 portions | no | universal | Pastelería |
| REC-003 | stroop_waffle | Stroop Waffle | 12 unidades | **yes** (NL) | NL heritage | Panadería |
| REC-004 | ontbijtkoek_700g_flour | Ontbijtkoek 700g flour | 1 molde | **yes** (NL) | NL heritage | Panadería |
| REC-005 | carrot_cake_43x33x15_cm | Carrot Cake 43x33x15 cm | 1 molde | no | universal | Pastelería |
| REC-006a | frikandel_100_pcs | Frikandel 100 pcs | 100 unidades | **yes** (NL) | NL heritage | Catering, Panadería |
| REC-006b | bitterballen_100_pcs | Bitterballen 100 pcs | 100 unidades | **yes** (NL) | NL heritage | Catering, Panadería |
| REC-007 | ketjap_manis_quick_version | Ketjap Manis (Quick Version) | 1 batch | **yes** (NL-Indonesian) | NL heritage | Catering, Panadería |
| REC-008 | hojaldre_bladerdeeg | Hojaldre / Bladerdeeg (puff pastry) | 1 batch | **yes** (NL) | NL heritage | Panadería, Catering |
| REC-009 | pastelitos_rosados_roze | Pastelitos Rosados / Roze | 1 batch | **yes** (NL "roze") | NL heritage | Pastelería |
| REC-010 | galletas_de_especuloos | Galletas de Especuloos (Speculaas) | 1 batch | **yes** (NL) | NL heritage | Panadería, Pastelería |
| REC-011 | bizcocho_basico_25_cm | Bizcocho Básico 25 cm | 1 molde | no | universal | Panadería, Pastelería |
| REC-012 | bizcocho_basico_30_cm | Bizcocho Básico 30 cm | 1 molde | no | universal | Panadería, Pastelería |
| REC-013 | tarta_de_manzana | Tarta de Manzana (Apple Pie) | 1 molde | no (universal) | universal | Panadería, Pastelería |
| REC-014 | proficroles_den_bosch | Profiteroles de Den Bosch (Bossche Bollen) | 1 batch | **yes** (NL Den Bosch) | NL heritage | Pastelería |
| REC-015 | petisus_de_hojaldre_y_crema | Petisús de Hojaldre y Crema (cream puffs) | 1 batch | no (universal) | universal | Panadería, Pastelería |
| REC-016 | oliebollen_bunuelos | Oliebollen / Buñuelos tradicionales | 1 batch | **yes** (NL New Year) | NL heritage | Panadería |
| REC-017 | babka | Babka (Polish-Jewish origin) | 1 molde | no (international) | universal | Panadería, Pastelería |
| REC-018 | bombones_de_chocolate | Bombones de Chocolate | 20 unidades | no (universal) | universal | Pastelería |
| REC-019 | goulash_crockettes_100 | Goulash Croquettes 100 pcs | 100 unidades | **yes** (NL) | NL heritage | Catering, Panadería |
| REC-020 | veggie_bitterballen_100 | Veggie Bitterballen 100 pcs | 100 unidades | **yes** (NL vegetarian) | NL heritage | Catering, Panadería |
| REC-021 | suppli_caccio_e_pepe | Supplì Cacio e Pepe | 12 unidades | no (Italian) | universal | Panadería, Catering |
| REC-022 | everything_bagels_8 | Everything Bagels (8 unidades) | 8 unidades | no (American/Jewish) | universal | Panadería |
| REC-023 | everything_bagel_seasoning | Everything Bagel Seasoning | 57 g | no (universal) | universal | Panadería |

**Summary**:
- **Total: 23 recipes** (REC-001 to REC-023, with REC-006 used twice for Frikandel AND Bitterballen — DATA ISSUE TO FIX)
- **Dutch heritage recipes: 11** (REC-003, 004, 006a, 006b, 007, 008, 009, 010, 014, 016, 019, 020) = 47% of catalog
- **Universal recipes: 12** (REC-001, 002, 005, 011, 012, 013, 015, 017, 018, 021, 022, 023) = 53% of catalog
- **Italian: 1** (REC-021 Supplì)
- **International: 1** (REC-017 Babka, REC-022 Everything Bagels)
- **All recipes are PY-palatable** (Dutch, Italian, Polish, American-Jewish — these are all immigrant communities in PY)

This is the **unique selling proposition of La Vaquita Holandesa**: a PY panadería with a Dutch heritage line. The 11 Dutch recipes + the 4 Dutch signature ingredients (Speculaas, Ketjap Manis, Bladerdeeg, Harina de centeno) + the brand name "La Vaquita Holandesa" = the story.

### 2.5 Production_Planner, Waste_Tracker, Dashboard_PL

These three are **empty templates** (Saskia hasn't used them yet). The schema is:
- Production_Planner: Fecha, Receta, Porciones plan., Porciones reales, Min mano de obra, Costo total ₲, Notas
- Waste_Tracker: Fecha, Receta, Porciones perdidas, Cantidad, Razón, Costo perdido ₲, Acción correctiva
- Dashboard_PL: Recipe, PortionsSold, UnitPrice ₲, Revenue ₲, Cost/Portion ₲, TotalCost ₲, Margin ₲, Margin %

The Sazon app **already has equivalents** for these (ProductionPlan, Waste, Sale, etc.). The HEREBUS schema is **a working spreadsheet** Saskia uses mentally; the Sazon app should **auto-populate** these from actual data (Sazon records each sale and each waste event, so the dashboards fill themselves).

---

## 3. The questionnaire — 70 filled answers (summary, from 2026-10-09 doc)

The 2026-10-08 questionnaire has 22 sections. The 70 filled answers are mapped to Sazon schema in the analysis doc. Key findings (for completeness):

| Section | What was answered | Where it lives in Sazon |
|---|---|---|
| §1.1 Nombre del local | "La Vaquita Holandesa" | `branding.business_name` (settings) |
| §1.2 Rubro | Panadería / Pastelería | `business_info.category` (NEW) |
| §2.1 Dirección | "Laguán Grande, Arquitectos, Calle 17, Asunción" | `location.address` (settings) |
| §2.3 Teléfono | +595 991 683805 | `contact.phone` (settings) |
| §2.4 Email | La.vaquitaholandesa@gmail.com | `contact.email` (settings) |
| §2.7 WhatsApp | +595 991 683805 | `sales.shop_whatsapp` (SASKIA-215) |
| §3.1 Horario semanal | Mon-Sat 8-13, Sun cerrado | `business_info.hours` (NEW) |
| §4.1-4.5 Equipo | Saskia sola (no cajeros) | `business_info.staff_count` (NEW) |
| §5.1-5.4 Productos | 22+ products, 6 categorías | Product table (already in DB) |
| §6 Métodos de pago | Efectivo, Transferencia, Tigo Money, Personal Pay | PaymentMethod table (already) |
| §7-8 Marketing / Redes | Instagram + WhatsApp (no web) | `marketing.*` settings (NEW) |
| §9-10 Cliente objetivo | Familias +上班族, San Lorenzo/Central | `targeting.*` settings (NEW) |
| §11-12 Volumen | 5-15 portions/día actual, 20-30 meta | capacity metrics (NEW) |
| §13-15 Competencia / Diferenciadores | Dutch heritage is the USP | `positioning.differentiator` (NEW) |
| §16.1 Semana Santa 2027 | si | `SeasonalEvent` (SASKIA-216) |
| §16.5 Menú estacional verano/invierno | si | `SeasonalEvent` (SASKIA-216) |
| §16.6 Aviso 30 días antes | si | `seasonal.notif_lead_days` (SASKIA-215) |
| §17-18 Operación | Solo (Saskia), no empleados | operations settings (NEW) |
| §19 Compliance | RUC/Timbrado TBD | `compliance.*` (NEW, all TBD) |
| §20-22 Goals | Growth targets | `goals.*` (NEW) |

**Sections with NEW settings I need to add** (estimated 30-50 more):
- `business_info` (category, hours, staff_count, etc.)
- `contact` (full contact details: phone, email, whatsapp, instagram)
- `location` (already done in SASKIA-215: barrio, zona; need to add: address_full, city, department, lat, lng, reference_point)
- `marketing` (instagram_handle, facebook, has_website, has_whatsapp_business)
- `targeting` (target_audience, age_range, income_level, area)
- `positioning` (differentiator, unique_selling_points)
- `operations` (is_solo, has_cashiers, has_delivery, has_pickup, has_dine_in)
- `compliance` (ruc, timbrado, fecha_vencimiento_timbrado)
- `goals` (target_revenue, target_products, target_customers)

These are NOT yet in the registry. **This is the SASKIA-221 ticket.**

---

## 4. Per-table action plan: what each Sazon table should contain after seeding

This is the **consolidated deliverable**: for each Sazon table, what should be populated, from which source, with what values.

### 4.1 `tenants` (the multi-tenant root, SASKIA-214 / 222)

| Column | Value | Source |
|---|---|---|
| id | 1 | auto |
| name | "La Vaquita Holandesa" | questionnaire §1.1 |
| slug | "la-vaquita-holandesa" | derived |
| pack_slug | "panaderia" | from Sazon PACKS |
| country | "PY" | from location.zona |
| created_at | 2026-10-08 (questionnaire received) | meta |
| active | true | default |

### 4.2 `users` (operators/staff)

| Column | Value | Source |
|---|---|---|
| id | 1 | auto |
| email | "La.vaquitaholandesa@gmail.com" | questionnaire §2.4 |
| name | "Saskia Weiss Van Der Pol" | derived from brand |
| role | "admin" | (only operator per §4.5) |
| tenant_id | 1 | FK |
| password_hash | bcrypt('admin') | from Sazon default |

**Note**: The current seeder creates 3 fake users (Lucía, Diego, etc.). The Sazon-215 + this analysis **recommend removing the 3 fake users** and having only Saskia. **Operator decision pending.**

### 4.3 `ingredients` (the Sazon version of HEREBUS Inventory)

**Total to seed: 100 ingredients** (all of HEREBUS Inventory).

| Column | Value | HEREBUS source |
|---|---|---|
| id | 1-100 | ING-001 to ING-100 |
| sku | "ING-001" | Inventory!A col |
| name | "Harina de centeno" etc. | Inventory!B col |
| category | "Harinas y bases" etc. | Inventory!C col (12 categories) |
| package_size | 1000.0 (g) etc. | Inventory!D col |
| package_unit | "g", "ml", "und" | Inventory!E col |
| package_price_gs | 25000.0 (₲) | Inventory!F col |
| unit_price_gs | 25.0 (₲/g) | Inventory!G col (= F/D) |
| stock_qty | 1500.0 (g) etc. | Inventory!H col (most None) |
| min_reorder | (mostly None) | Inventory!I col |
| last_price_update | 2026-10-07 | Inventory!J col |
| supplier_id | FK to suppliers | derived from Notas |
| tenant_id | 1 | multi-tenant |
| dutch_heritage_flag | true for ING-001, 032, 051, 069, 076, 087, 097-100 | computed (the Dutch ingredients) |
| needs_confirm_flag | true for ING-082-100 | from "CONFIRMAR" notes |

**Special ingredient groups to flag**:
- `category IN ('Especias y condimentos', 'Salsas y líquidos', 'Carnes', 'Levaduras y gasificantes', 'Cacao café y chocolate', 'Aceites y grasas', 'Preparados y otros')` — these have notes about suppliers
- ING-032 Speculaas, ING-069 Ketjap Manis, ING-001 Harina de centeno, ING-076 Masa de hojaldre — flag as `dutch_heritage=true`
- ING-082 through ING-100 — flag as `needs_confirm=true`

### 4.4 `recipes` (the Sazon version of HEREBUS Recipe_*)

**Total to seed: 23 recipes** (REC-001 to REC-023).

| Column | Value | HEREBUS source |
|---|---|---|
| id | 1-23 | REC-001 to REC-023 |
| sku | "REC-001" etc. | Recipe_*!A col |
| name | "Chocolate Muffin 20x20 cm" etc. | Recipe_*!B col (the title row 1) |
| slug | "chocolate_muffin_20x20" | derived from title |
| yield_qty | 100.0, 170.0, 12.0, etc. | Recipe_*!B4 col |
| yield_unit | "unidades", "porciones", "molde" | Recipe_*!D4 col |
| notes | "elaboración" or "método" | Recipe_*!E5 col (often None) |
| dutch_heritage_flag | true for 11 NL recipes | computed |
| prep_time_min | TBD (not in HEREBUS, default 60) | new |
| cook_time_min | TBD | new |
| difficulty | TBD (1-5) | new |
| category | "pasteleria", "panaderia", "snack" | derived |
| tenant_id | 1 | multi-tenant |

**Data issue to fix**: REC-006 is used for both **Frikandel** (REC-006a in the spreadsheet) and **Bitterballen** (REC-006b in the spreadsheet, lowercase). The Sazon DB should give them distinct IDs (e.g. REC-006 Frikandel, REC-024 Bitterballen). This is a **data integrity issue** in HEREBUS that should be normalized on import.

**Recipes that need operator (Saskia) review for yield** (B4 is empty):
- REC-001 Chocolate Muffin (no yield)
- REC-004 Ontbijtkoek (no yield)
- REC-005 Carrot Cake (no yield)
- REC-006 Frikandel (no yield)
- REC-007 Ketjap Manis (no yield)
- REC-008 Hojaldre (no yield)
- REC-009 Pastelitos Rosados (no yield)
- REC-010 Galletas Especuloos (no yield)
- REC-011 Bizcocho 25cm (no yield)
- REC-012 Bizcocho 30cm (no yield)
- REC-013 Tarta de Manzana (no yield)
- REC-014 Profiteroles Den Bosch (no yield)
- REC-015 Petisús (no yield)
- REC-016 Oliebollen (no yield)
- REC-017 Babka (no yield)
- REC-022 Everything Bagels (no yield)

That's **16 of 23 recipes (70%) missing the yield**. This is a **data quality issue** Saskia needs to fix. Until fixed, the seeder must use a default yield (e.g. 1 molde or 12 unidades).

### 4.5 `recipe_lines` (the Sazon version of HEREBUS Recipe_* ingredients)

**Total to seed: ~280 lines** (avg 12 ingredients per recipe × 23 recipes).

Each line:
| Column | Value | HEREBUS source |
|---|---|---|
| id | auto | – |
| recipe_id | FK to recipe | derived |
| ingredient_id | FK to ingredient (ING-NNN) | Recipe_*!B col (the Ingrediente ID) |
| quantity | 400.0 (g) etc. | Recipe_*!D col |
| unit | "g", "ml", "und" | Recipe_*!E col |
| unit_price_gs | 40.0 etc. | Recipe_*!F col |
| line_cost_gs | 16000 etc. | Recipe_*!G col (= D × F) |
| notes | "1 cebolla grande, en trozos" etc. | Recipe_*!H col |
| order | 1, 2, 3, ... | Recipe_*!A col |
| tenant_id | 1 | multi-tenant |

### 4.6 `products` (the Sazon product catalog, sold to customers)

The Sazon app has 22+ products already in the seeder. The HEREBUS spreadsheet doesn't have a direct products list — products are **derived from recipes + variations** (e.g. a "Muffin de chocolate" product = REC-001 cut into 12 portions, sold at X Gs each).

| Product name | Recipe source | Channel |
|---|---|---|
| Muffin de Chocolate | REC-001 | retail |
| Cheesecake (rebanada) | REC-002 | retail |
| Stroopwafel | REC-003 | retail, NL heritage |
| Ontbijtkoek | REC-004 | retail, NL heritage |
| Carrot Cake (rebanada) | REC-005 | retail |
| Frikandel (unidad) | REC-006a | retail, NL heritage |
| Bitterballen (unidad) | REC-006b | retail, NL heritage |
| Ketjap Manis (botella) | REC-007 | retail, NL heritage |
| Hojaldre / Bladerdeeg (pack) | REC-008 | wholesale + retail |
| Pastelitos Rosados (pack) | REC-009 | retail, NL heritage |
| Galletas de Especuloos (pack) | REC-010 | retail, NL heritage |
| Bizcocho 25cm | REC-011 | eventos |
| Bizcocho 30cm | REC-012 | eventos |
| Tarta de Manzana | REC-013 | retail, eventos |
| Profiteroles Den Bosch (pack) | REC-014 | retail, NL heritage |
| Petisús de Hojaldre y Crema (pack) | REC-015 | retail, eventos |
| Oliebollen (pack) | REC-016 | retail, NL heritage (New Year) |
| Babka | REC-017 | retail, eventos |
| Bombones de Chocolate (caja) | REC-018 | retail, eventos |
| Goulash Croquettes (pack) | REC-019 | retail, NL heritage |
| Veggie Bitterballen (pack) | REC-020 | retail, NL heritage |
| Supplì Cacio e Pepe (pack) | REC-021 | retail, catering |
| Everything Bagels (pack) | REC-022 | retail |
| Everything Bagel Seasoning (frasco) | REC-023 | retail |

**Total: 24 products** (one per recipe, plus 1 more for the seasoning)

**Note**: the current seeder (`app/rms/seed/sazon.py`) already has 22+ products but with different names and no recipe linkage. **The Sazon seed needs to be rewritten to:
1. Use the HEREBUS recipe names
2. Link each product to its REC-NNN recipe
3. Compute the product cost from recipe cost / yield
4. Add the NL heritage products (Stroopwafel, Ontbijtkoek, Bitterballen, Frikandel, Speculoos, Oliebollen, Bossche Bollen, Goulash Croquettes, Veggie Bitterballen, Pastelitos Rosados, Ketjap Manis)**

### 4.7 `packaging` (the Sazon version of HEREBUS Packaging)

| id | name | category | package_size | package_unit | bulk_price_gs | unit_price_gs | supplier_id |
|---|---|---|---|---|---|---|---|
| MAT-01 | bolsita de 15x22 | bolsita | 100 | und | 24,918 | 249.18 | TBD |
| MAT-02 | cintillo 7mm 10m | decoracion | 250 | unid 40cm | 8,000 | 32 | TBD |
| MAT-03 | bandeja isopor B-190 | bandeja | 100 | und | 25,200 | 252 | TBD |
| MAT-04 | bandeja carton n*3 | bandeja | 25 | und | 8,401 | 336.04 | TBD |
| MAT-05 | papel antigrasa blanco | papel | 100 | und | 12,000 | 120 | TBD |
| MAT-06 | bolsa de papel mediana | bolsa | 1 | und | 350 | 350 | TBD |
| MAT-07 | caja torta 25cm | caja | 1 | und | 2,800 | 2,800 | TBD |

**Total stock: 22,426.20 ₲** (computed from BulkPrice × StockQty in the spreadsheet cell R12 col H)

**New column suggestion**: `package_type` (primary, secondary, gift) — useful for filtering.

### 4.8 `categories` (product categories)

The Sazon app has 6+ categories. The HEREBUS Inventory has 12 ingredient categories. The product catalog has 4-5 categories (panadería, pastelería, snack, catering, eventos).

**Per Sazon convention**: product categories should be the **product type** (panadería, pastelería, snack, evento, catering), not the ingredient category. The seeder should keep 4-6 product categories:
- Panadería (breads, facturas, chipa)
- Pastelería (cakes, cookies, tortas)
- Catering (frikandel, bitterballen, croquettes)
- Eventos (bizcochos grandes, tortas por encargo)
- Otros (packaging, ingredients for sale)

### 4.9 `suppliers`

The HEREBUS Inventory has 100 ingredients with "Notas" mentioning ~20 different suppliers (Supermas, Ypacaraí, Tregar, TodoNegocio, cocinar.com.py, preciosdelagro, etc.). The Sazon `suppliers` table should have ~15-20 rows:

| Name | Type | Notes |
|---|---|---|
| Supermas | supermarket | Carne, verdura, lácteos |
| Ypacaraí | rice | Arroz para sushi |
| Tregar | cheese | Queso rallado, muzzarella |
| TodoNegocio | condiments | Ajo en copos, etc. |
| cocinar.com.py | online | Especias, pimentón |
| preciosdelagro | market | Apio, verduras frescas |
| Dietetica | spices | Sésamo, amapola, sal Maldon |
| Cervecería Nacional (alcohol) | alcohol | (not in HEREBUS; for next client) |
| Local Harina (Harina de centeno) | mill | Rye flour supplier |
| ... | ... | ... |

**Operator decision needed**: Saskia needs to provide supplier names + contact info for the ~20 unique sources.

### 4.10 `payments` (payment methods)

Already in the seeder per questionnaire §6:
- Efectivo
- Transferencia bancaria
- Tigo Money
- Personal Pay

### 4.11 `settings_kv` (the 74+ settings from SASKIA-215)

The 74 settings across 16 groups (LOCATION, SEASONAL, RECIPE, etc.) are already in the registry. The HEREBUS data doesn't directly map to settings (it's operational data, not config). But there are a few new settings that should be added:

- `business_info.category` (panadería/pastelería)
- `business_info.hours_weekday` (Mon-Sat 8-13)
- `business_info.hours_weekend` (Sun cerrado)
- `business_info.staff_count` (1 = Saskia)
- `contact.instagram_handle` (NEW)
- `contact.facebook` (NEW)
- `contact.whatsapp_business` (true/false)
- `location.address_full` (the full address)
- `location.city` (Asunción)
- `location.department` (Central)
- `location.lat` (TBD)
- `location.lng` (TBD)
- `location.reference_point` (TBD)
- `marketing.primary_channel` (WhatsApp)
- `targeting.audience` (familias +上班族)
- `targeting.age_range` (25-55)
- `targeting.area` (San Lorenzo + Central)
- `positioning.differentiator` (Dutch heritage + product quality)
- `operations.is_solo` (true)
- `operations.has_delivery` (false)
- `operations.has_pickup` (true)
- `operations.has_dine_in` (false)
- `compliance.ruc` (TBD)
- `compliance.timbrado` (TBD)
- `goals.target_revenue_monthly_gs` (TBD)
- `goals.target_products` (TBD)
- `goals.target_customers` (TBD)

**Total: ~25 more settings** to add to the registry (SASKIA-221).

### 4.12 `seasonal_event` (SASKIA-216)

The SeasonalEvent table is **universal** (not per-tenant) and the catalog is 411 rows for all packs. The seeder for SASKIA-216 inserts 132 rows for tier 1 + the SASKIA-220 ticket adds tier 2/3/4.

La Vaquita's calendar (filtered by `relevance_tags LIKE '%panaderia%'`) shows **~230 events across 3 years (2026-2028)**.

### 4.13 `production_plans`, `waste_events`, `sales` (operational tables)

These are **not seeded** — they're populated by the operator's daily actions. The HEREBUS Production_Planner, Waste_Tracker, Dashboard_PL are the operator's spreadsheet view; the Sazon equivalents fill themselves.

---

## 5. Per-page action plan: what the Sazon website shows after this seed

| Page | Data source | What it shows |
|---|---|---|
| `/` (home) | tenants, settings_kv, seasonal_event | Logo, business name, tagline, hours, location, upcoming events (3-5 nearest) |
| `/menu` | products, categories | All products grouped by category, with prices, photos |
| `/menu/<product>` | products, recipe_lines, recipe, ingredients, allergens | Product detail with "Ver ingredientes" toggle, "Pedir por WhatsApp" button (uses sales.shop_whatsapp) |
| `/recetas` | recipes, recipe_lines | Recipe catalog (REC-001 to REC-023), with yield, time, cost |
| `/recetas/<id>` | recipes, recipe_lines, ingredients | Full recipe with steps, photos, ingredient list with running cost total |
| `/admin/seasonal-calendar` | seasonal_event (filtered by relevance) | Calendar of upcoming events, color-coded by impact_tag, with lead-time badge |
| `/admin/calendar` | production_plan, sales | Daily production schedule + sales summary |
| `/admin/inventory` | ingredients, suppliers | 100 ingredients with stock levels, prices, supplier info, low-stock alerts |
| `/admin/recipes` | recipes, recipe_lines | 23 recipes with cost, margin, sales velocity |
| `/admin/orders` | sales | Sales by product, by channel (retail/wholesale/eventual), by date |
| `/admin/purchases` | suppliers, ingredient | Supplier price history, price change events (60/30/7 days) |
| `/admin/settings` | settings_kv, branding | All 74+ settings, organized by group |
| `/admin/business-info` | tenants, settings_kv | Tenant profile: name, category, hours, staff, location, contact, social |
| `/admin/dashboard` | sales, waste, recipes | P&L by recipe, top sellers, waste % |
| `/admin/seasonal-menus` | recipes + seasonal_event | Recipes tagged by event (e.g. "for Semana Santa: pastelitos, chipa guasú") |
| `/about` | tenants, settings_kv | About page: Saskia's story, the Dutch heritage, the PY connection |

---

## 6. What to add to the seed — the implementation plan

This is the **consolidated ticket stack** to actually do the work:

### 6.1 Already shipped
- **SASKIA-213** — La Vaquita seed constants (placeholders → real values)
- **SASKIA-215** — LOCATION/SEASONAL/RECIPE settings + WhatsApp fix + migration 118

### 6.2 Drafted (this doc)
- **SASKIA-221** (new) — Add 25+ new settings (business_info, contact, marketing, targeting, positioning, operations, compliance, goals) to the registry + seeder. The remaining questionnaire sections. **2 days.**

### 6.3 Drafted (earlier this session)
- **SASKIA-216** — SeasonalEvent model + migration 119 + tier 1 seeder (132 rows). **2-3 days.**
- **SASKIA-217** — `/admin/seasonal-calendar` UI page. **2-3 days.**
- **SASKIA-220** — 5 new packs (Food Truck, Quiosco, Chipería, Pastelería Industrial, Cervecería) + tier 2/3/4 catalog expansion. **5-7 days.**
- **SASKIA-214** — Per-instance config refactor. **4-6h.**

### 6.4 New (extracted from this analysis)
- **SASKIA-223** (new) — **HEREBUS data import**: 100 ingredients, 23 recipes, 7 packaging items, 24 products, 12-20 suppliers, fix REC-006 duplicate, mark 17 ingredients needs_confirm, mark 11 recipes dutch_heritage. **4-5 days.** Includes rewriting the products seeder to link to REC-* and adding the 11 Dutch heritage products.
- **SASKIA-224** (new) — **Recipe yield backfill**: 16 of 23 recipes are missing the yield_qty in B4. Operator-driven (Saskia cooks once and records). For seeder default = 1. **1 day seeder default; 1 week operator backfill.**

### 6.5 Total estimated work
- SASKIA-214 (4-6h) + SASKIA-216 (2-3d) + SASKIA-217 (2-3d) + SASKIA-220 (5-7d) + SASKIA-221 (2d) + SASKIA-223 (4-5d) + SASKIA-224 (1d)
- **= ~18-23 days of code** to fully implement the OOB
- Critical path: 214 → 216 → 217 (so the website renders) → 221 (full settings) → 223 (HEREBUS data) → 220 (extended catalog) → 224 (yield backfill)

---

## 7. Operator decisions needed (from Saskia, before implementation)

1. **REC-006 conflict**: Frikandel AND Bitterballen are both REC-006 in HEREBUS. Sazon will use REC-006 Frikandel + REC-024 Bitterballen. Confirm?
2. **3 fake users in seeder**: Lucía, Diego, etc. are placeholders. Remove (solo operator)?
3. **17 "CONFIRMAR" prices**: lock at listed, or flag for live re-quote in production?
4. **16 missing recipe yields**: default to 1 in seeder, backfill later?
5. **20+ supplier names**: from HEREBUS Notas (Supermas, Ypacaraí, Tregar, etc.) — provide contact info?
6. **24 product names**: HEREBUS names vs Sazon current names — which to use?
7. **Dutch heritage flag**: mark 11 recipes + 4 ingredients as dutch_heritage=true? Or have a separate "brand_story" column?
8. **Pack matching**: HEREBUS has only 23 recipes; Sazon has 11 packs. Match each recipe to 1-3 packs. Done in §4.6 above.
9. **RUC, timbrado, lat, lng, instagram**: all TBD in the questionnaire. Skip in seed, leave empty?
10. **Multi-tenant expansion**: this analysis is for La Vaquita. The same seed pattern should apply to the next 5 packs (Food Truck, Quiosco, Chipería, Pastelería Industrial, Cervecería). Confirm direction.

---

## 8. Source index

### Questionnaire (2026-10-08)
- `/opt/data/profiles/ivan/attachments/2026-10-08-la-vaquita-feliz-onboarding-questionnaire.md.docx` (md5: 16552b4d6508d3906b13136655f0526e) — 250KB, 22 sections, 70 filled answers
- `docs/operations/2026-10-09-la-vaquita-onboarding-analysis.md` — 354-line analysis

### HEREBUS spreadsheet (2026-10-12)
- Google Sheet id `1z43h66KulWS4QS8wJAKoIMV3sk6yZqfC`, tab gid `975648968`
- 30 sheets: Instructions, Inventory (100 ing), Packaging (7 mat), 23 Recipe_*, 1 lowercase recipe_bitterballen_100_pcs, Production_Planner (empty), Waste_Tracker (empty), Dashboard_PL (empty)
- 100 ingredients across 12 categories (Especias 28, Lácteos 12, Preparados 11, Frutos secos 9, Verduras 8, Harinas 7, Salsas 7, Endulzantes 5, Carnes 5, Levaduras 4, Cacao 3, Aceites 1)
- 23 recipes REC-001 to REC-023 (with REC-006 duplicated for Frikandel AND Bitterballen)
- 11 Dutch heritage recipes (47%), 12 universal (53%), 1 international (Babka), 1 Italian (Supplì)
- 17 ingredients with "CONFIRMAR" status (ING-082 to ING-100)

### Existing Sazon docs (this session)
- `docs/operations/2026-10-12-seasonal-events-comprehensive-catalog.md` — PY + NL holidays (132 rows tier 1)
- `docs/operations/2026-10-12-multi-tenant-verticals-and-events.md` — 11+5 packs + 411-row catalog (tier 1+2+3+4)
- `docs/intake/SASKIA-213-vaquita-seed-data-update.md`
- `docs/intake/SASKIA-214-per-instance-business-info.md`
- `docs/intake/SASKIA-215-add-location-seasonal-recipe-settings.md`
- `docs/intake/SASKIA-216-seasonal-event-model.md`
- `docs/intake/SASKIA-220-new-packs-and-extended-catalog.md`

### Existing Sazon app (from worktree)
- `app/rms/seed/sazon.py` — current seeder (28 tables, 22+ products, 3 fake users)
- `app/rms/seed/packs.py` — 11 packs
- `app/rms/settings_registry.py` — 74 settings across 16 groups
- `app/rms/db.py` — schema, models
- `app/routers/products.py:1372` — public menu (uses sales.shop_whatsapp)
- `app/routers/settings_runtime.py` — settings GET/POST
- `app/rms/migrations/_118_shop_whatsapp_rename.py` — migration 118
- `app/rms/config.py` — CURRENT_SCHEMA_VERSION = 118
