# 📋 COMPLETE IMPLEMENTATION ITEM LIST — Saskia × HEREBUS Drive

Based on analysis of all 33 files in the HEREBUS Google Drive folder
and the existing Saskia RMS code (25+ ORM models).

Color: 🟢 = drop-in data (existing models), 🆕 = new model needed,
⚙️ = infra/UX work, 📊 = analytics/dashboard, ⚠️ = risk/missing.

---

## 🎯 PART 1 — Direct Data Imports (existing Saskia models)

### 1.1 Ingredients — `Ingredient` model (44 real items)

**Source**: `HEREBUS_Gestion_v1.xlsx → INGREDIENTES` (45 rows, header + 44 ingredients)

**Mapping** (Sheet column → Saskia field):
| Sheet column | Saskia field | Notes |
|---|---|---|
| `ING-001..044` | (no ID field — auto-PK) | Optional external_code |
| `Harina de trigo` | `Ingredient.name` | Spanish name required |
| `Categoría` | `Ingredient.category` | 14 cats found (Harinas, Polvos, Endulzantes…) |
| `Unidad` | `Ingredient.unit` | "g", "ml", "und" |
| `Tamaño de compra` | `Ingredient.package_qty` | (raw, not in model yet — add field) |
| `Precio de compra (₲)` | `Ingredient.purchase_price_gs` | ₲ no decimals |
| `Precio por unidad (₲)` | `Ingredient.unit_price_gs` | computed per g/ml/und |
| `Stock actual` | `Ingredient.stock_qty` | mostly empty (0) |
| `Stock mínimo` | `Ingredient.min_stock_qty` | mostly 10 |
| `Reorder?` | `Ingredient.auto_reorder` (boolean) | True for all |
| `Proveedor` | (no supplier FK yet — needs `Ingredient.preferred_supplier_id`) |
| `Última compra` | (date field missing — needs `Ingredient.last_purchase_date`) |
| `Notas` | `Ingredient.notes` | |

**Work**:
- 🟡 Add 2-3 new fields to `Ingredient`: `package_qty`, `preferred_supplier_id`, `last_purchase_date`, `external_code`
- 🟢 Import script: `/scripts/import_ingredients.py` (reads xlsx → inserts)
- 🧪 Tests: count check, category coverage, no duplicates

**Effort**: 0.5 day

---

### 1.2 Recipes + lines — `Recipe` + `RecipeLine` (7 recipes, 68 lines)

**Source**: `HEREBUS_Gestion_v1.xlsx → RECETAS_MAESTRO` + `RECETAS_DETALLE`
**Source alt**: `RECETAS_ARCHIVE` (same data, "archive" view)
**Source photo**: 14 jpgs of Dutch cookbook (manual data entry later)

**Recipe mapping**:
| Sheet column | Saskia field |
|---|---|
| `REC-001` | `Recipe.external_code` |
| `Chocolate Muffin (20x20 cm)` | `Recipe.name` |
| `12` | `Recipe.yield_qty` (or yield) |
| `∅` | `Recipe.prep_minutes` (no data yet) |
| `∅` | `Recipe.pack_minutes` (no data yet) |
| `Brownie-style. Espresso realza...` | `Recipe.notes` |

**RecipeLine mapping** (per ingredient per recipe):
| Sheet column | Saskia field |
|---|---|
| `Receta ID` | join to Recipe |
| `1.0` | `RecipeLine.position` |
| `ING-001` | join to Ingredient |
| `250.0` | `RecipeLine.qty` |
| `g` | `RecipeLine.unit` |
| `5.5` | (computed at save — no need to import) |
| `1375` | (computed at save — no need to import) |

**Recipes to import** (7):
1. **Chocolate Muffin (20x20 cm)** — 13 lines, yield 12
2. **Cheesecake (20x20 cm)** — 7 lines, yield 10
3. **Stroop Waffle** — 9 lines, yield 8
4. **Ontbijtkoek (700g flour)** — 9 lines, yield 10
5. **Carrot Cake (43x33x1.5 cm)** — 14 lines, yield 30
6. **Frikandel (100 pcs)** — 10 lines, yield 100
7. **Ketjap Manis (Quick)** — 5 lines, yield 3L

**Work**:
- 🟢 Import script: `/scripts/import_recipes.py`
- 🟢 Match Spanish names to existing `Ingredient` table (44 items created above)
- 🧪 Tests: line count match, cost recompute matches sheet
- 📸 Photo upload: 14 jpgs → `/static/recipes/` + Recipe.image_url field

**Effort**: 1 day

---

### 1.3 Customers — `Customer` model (~10 from sales sample)

**Source**: `HEREBUS_Gestion_v1.xlsx → VENTAS` (10 historical sales)

| Sheet column | Saskia field |
|---|---|
| `Fecha` | `Customer.first_purchase_date` (computed) |
| `Cliente` | `Customer.name` |
| `Centro, Villa Morra…` | `Customer.zone` (NEW field) |
| `Pedido doble`, `Repetidora`, etc. | `Customer.notes` |

**Known customers** (dedupe):
1. Lucía Vega (Centro) — 2 sales
2. María José (Villa Morra) — 2 sales
3. Ana Ortiz (Recoleta)
4. Familia Romero (Carmelitas)
5. Cliente casual (Centro)
6. Cliente IG (Luque)
7. Cliente holandés (Centro)
8. Pedido oficina (Villa Morra)
9. Saskia (Responsable on waste sheet — internal user, not customer)

**Work**:
- 🟡 Add `Customer.zone` field to model
- 🟢 Import script: parse VENTAS, dedupe by name → insert

**Effort**: 0.5 day

---

### 1.4 Sales — `Sale` model (10 historical)

**Source**: `VENTAS` sheet (only 10 rows; real importer needs production log later)

| Sheet column | Saskia field |
|---|---|
| `Fecha` (DD/MM/YYYY) | `Sale.created_at` (parse to ISO date) |
| `Receta` (e.g. "Stroop Waffle") | join to Product/Recipe |
| `Unidades` | `Sale.quantity` |
| `Total (₲)` | `Sale.total_gs` |
| `Pago` (Efectivo/Transferencia/MercadoPago) | `Sale.payment_method` |
| `Cliente` | join to Customer (dedupe first) |
| `Zona delivery` | `Sale.delivery_zone` |
| `Notas` | `Sale.notes` |
| `Canal de Venta` (Retail/Wholesale) | `Sale.sale_channel` (NEW field needed) |

**Sample row**:
- 2026-07-18, Cheesecake (20x20 cm), 1 unit, ₲10,743.80, Efectivo, Lucía Vega, Centro, "Repetidora", Retail

**Work**:
- 🟡 Add `Sale.sale_channel` enum (`retail`, `wholesale`, `distributor`, `event`)
- 🟢 Import script: insert 10 with recipe/customer joins, ignore weekends

**Effort**: 0.5 day

---

### 1.5 Waste records — `WasteLog` model (3 sample rows)

**Source**: `MERMAS` sheet (3 visible records + 17 empty rows for daily log)

| Sheet column | Saskia field |
|---|---|
| `Fecha` | `WasteLog.created_at` |
| `Ingrediente` (or Recipe) | join to Ingredient |
| `Cant perdida` | `WasteLog.quantity` |
| `Unidad` | `WasteLog.unit` |
| `Pérdida (₲)` | `WasteLog.cost_loss_gs` |
| `Razón` (quedó fuera de venta / caducó / se quemó / etc) | `WasteLog.reason` |
| `Responsable` (Saskia) | `WasteLog.user_id` |

**Reasons needed**: 5 enum (vencido, quemado, robo, error_prep, cliente_rechaza)

**Work**:
- 🟢 Import script
- 🟢 Add the 5-reason enum to model

**Effort**: 0.25 day

---

### 1.6 Suppliers — `Supplier` model (8+ known)

**Source**: `INGREDIENTES.Proveedor` column names 7 actual suppliers + `HEREBUS_Suppliers.xlsx → Suppliers` (30 placeholder rows but 0 populated)

**Known names** (from INGREDIENTES sheet):
1. **Stock PY** — main wholesale supplier
2. **Casa Rica** — chocolates, special flours
3. **Superseis** — basic dry goods (azúcar, harina, sal)
4. **Mercado Abasto** — fresh produce, meats
5. **Importadora** — Dutch specialty (Ketjap, Koekzoet, Speculaas spices, espresso powder)
6. **Productor Local** — walnuts, honey
7. **Otro** — water, old Ontbijtkoek, bags

**Mapping**:
| Sheet column | Saskia field |
|---|---|
| `Stock PY` | `Supplier.name` |
| (no contact yet) | `Supplier.contact_person` |
| (no phone yet) | `Supplier.phone` |
| (no address yet) | `Supplier.address` |
| (implicit) | `Supplier.category` |

**Work**:
- 🟢 Seed 7 suppliers (no FK from Ingredient yet — covered in 1.1)
- 🟢 Allow editing to add full contact details later

**Effort**: 0.25 day

---

### 1.7 Delivery zones — `Pedido` model (5 zones)

**Source**: `ZONAS_DELIVERY` sheet (5 production zones + business hours config)

| Sheet column | Saskia field |
|---|---|
| `0 - Pickup` to `5 - Fuera` | `Pedido.delivery_zone_id` (FK to new `DeliveryZone` table) |
| `Cobertura` | `DeliveryZone.coverage_text` |
| `Radio (km)` | `DeliveryZone.radius_km` |
| `Costo ₲` | `DeliveryZone.delivery_cost_gs` |
| `Pedido mín ₲` | `DeliveryZone.min_order_gs` |
| `Tiempo (min)` | `DeliveryZone.delivery_minutes` |
| `Notas` | `DeliveryZone.notes` |

**Plus business hours** (rows 8-14):
- Address: Villa Amelia, San Lorenzo (cp 1100)
- Coordinates: -25.316851, -57.515935
- Hours: Mié-Vie 11:00–19:00, Sáb 08:00–13:00
- Closed: Dom, Lun, Mar
- Delivery: Contratado externo (Saskia NO hace la moto)

**Work**:
- 🆕 New model `DeliveryZone` (id, code, coverage_text, radius_km, delivery_cost_gs, min_order_gs, delivery_minutes, notes)
- 🆕 Settings singleton: pickup_address, pickup_coordinates, business_hours_json
- 🟢 Seed 5 zones + business hours from sheet
- 🟢 Wire to Pedido creation flow: validate min_order, auto-calc delivery_cost, auto-suggest time

**Effort**: 1 day

---

## 🎯 PART 2 — New Modules (new models needed in Saskia)

### 2.1 Wishlist / Kitchen Equipment 🆕 — `WishlistItem` model

**Source**: `HEREBUS_Analisis.xlsx → Wishlist` (28 items)

**Mapping**:
| Sheet column | Saskia field |
|---|---|
| `EQ-001` | external_code |
| `Horno eléctrico 60L 2200W` | `WishlistItem.name` |
| `🟢 Must-have` (or Nice-to-have / Opcional) | `WishlistItem.priority` enum |
| `1.0` | `WishlistItem.quantity` |
| `1500000.0` | `WishlistItem.unit_price_gs` |
| `1500000` | (computed: × qty) |
| `Cocción` | `WishlistItem.category` |
| `Matalon, Digi Marketplace...` | `WishlistItem.buy_location` |
| `Lo más caro y crítico...` | `WishlistItem.notes` |
| `En progreso` / `Sí` / `∅` | `WishlistItem.purchased` (boolean) + `purchased_at` |

**Total investment visible**: ₲61,005,000

**Work**:
- 🆕 New route + template: `GET/POST /wishlist`, `POST /wishlist/{id}/mark-purchased`
- 🆕 Pages: list (sortable by priority), detail
- 🆕 Reports: total ₲ pending by category
- 🟢 Seed all 28 items from sheet

**Effort**: 1.5 days

---

### 2.2 Production Planner 🆕 — `ProductionPlan` model + UI

**Source**: `HEREBUS_FoodBiz.xlsx → Production_Planner` (already-empty template) + concept in `HEREBUS_Gestion_v1.xlsx → PRODUCCIÓN`

**Mapping (concept)**:
```
User picks: recipe + batches_count
System reads: recipe_lines × qty × batches_count vs current stock
Output:
  - Each ingredient: qty_needed, stock_available, shortage (red/green)
  - "Generate Shopping List" → auto-open /reponer with shortages pre-filled
```

**Work**:
- 🆕 `/produccion` route + template
- 🆕 New model `ProductionPlan` (id, recipe_id, batches_qty, planned_at, status) - lightweight
- 🆕 Big interactive form: pick recipe (combo) + batches (number) → live result table
- 🆕 "Send to shopping list" button
- 🟢 Reports: weekly batches, total ₲ of ingredients used

**Effort**: 2 days

---

### 2.3 Dashboard / KPIs 🆕 — analytics dashboard

**Source**: `HEREBUS_Analisis.xlsx → KPI_Dashboard` (16 KPI rows)

**KPIs to compute**:

| KPI | Formula |
|---|---|
| REVENUE TOTALES ₲ | Σ(Sale.total_gs where month=current) |
| PORTIONS VENDIDAS | Σ(Sale.quantity) |
| FOOD COST % | cost of ingredients sold / revenue |
| GROSS MARGIN % | (revenue − cost) / revenue |
| HORAS TRABAJADAS | manual entry (no model yet) |
| REVENUE / HORA | revenue / hours_worked |
| COST TOTAL INGREDIENTES ₲ | Σ(RecipeLine.qty × Ingredient.unit_price) for sold recipes |
| WASTE COST ₲ | Σ(WasteLog.cost_loss_gs) |
| WASTE % | waste_cost / cost_total |
| CLIENTES ÚNICOS | count(distinct Customer.id) this month |
| REPEAT CUSTOMERS | count(customer with >1 Sale this month) |
| REPEAT CUSTOMERS % | repeat / total customers |
| AVG ORDER VALUE | avg(Sale.total_gs) this month |
| TOP RECIPE | groupby(recipe).sum(quantity).top(1) |
| # DE RECIPES COCINADAS | count(distinct recipe in Sales) |

**Status logic**: 🟢 within target / 🟡 within 10% / 🔴 beyond

**Work**:
- 🆕 `/dashboard` route with cards per KPI
- 🆕 New model `BusinessHour` (optional, manual labor tracking)
- 🆕 CSV export per KPI
- 🟢 Live computation on page load (no caching initially)

**Effort**: 2 days

---

### 2.4 Risk Register 🆕 — `RiskItem` model

**Source**: `HEREBUS_Analisis.xlsx → Risk_Register` (12 risks, 5 pre-populated)

**Mapping**:
| Sheet column | Saskia field |
|---|---|
| `RISK-001` | `RiskItem.code` |
| `Suba de precio de harina de trigo` | `RiskItem.description` |
| `Operacional` | `RiskItem.category` |
| `4.0` | `RiskItem.probability` (1-5) |
| `500000.0` | `RiskItem.impact_gs` |
| `2000000` | (computed: p × impact) `RiskItem.severity_gs` |
| `Hedging: comprar 3 meses...` | `RiskItem.mitigation` |
| `Activo` | `RiskItem.status` enum (Activo / Mitigado / Cerrado) |
| `Saskia` | `RiskItem.owner` (string — not User FK to avoid blocking) |

**Work**:
- 🆕 `/riesgos` route + template
- 🆕 Heatmap display: rows=risk, cols=severity, cells colored by status
- 🟢 Seed 12 risks from sheet
- 🟢 Add risk-score formula (auto recalc)

**Effort**: 1 day

---

### 2.5 Pricing per Product 🆕 — `RecipePricing` model + auto-cost engine

**Source**: `HEREBUS_Gestion_v1.xlsx → COSTOS` (7 rows with full pricing) + `HEREBUS_Analisis.xlsx → Pricing_Por_Producto` (template)

**Existing COSTOS rows** (real data):
- Chocolate Muffin: cost ₲22,385 + labor ₲15,000 = total ₲37,385 / 12 units = ₲3,115/unit → wholesale ₲5,192
- Cheesecake: ₲53,719 / 10 = ₲5,372/unit → wholesale ₲8,953
- Stroop Waffle: ₲38,414 / 8 = ₲4,802/unit → wholesale ₲8,003
- Ontbijtkoek: ₲35,940 / 10 = ₲3,594/unit → wholesale ₲5,990
- Carrot Cake: ₲34,437 / 30 = ₲1,148/unit → wholesale ₲1,913
- Frikandel: ₲3,837 / 100 = ₲38/unit (but real cost is from RAW Meats shown)

**Channel margins** (already in MAESTRA):
| Channel | Markup |
|---|---|
| Wholesale | +40% |
| Private label | +25% |
| Distribuidor | +22% |
| Retail | +50% |
| Broker commission | +5% |

**Work**:
- 🆕 `RecipePricing` model (recipe_id, channel, multiplier_pct, fixed_labor_gs, packaging_gs)
- 🆕 `RecipeCostSnapshot` model: store frozen cost at sale time
- 🆕 `/pricing` route: edit per-channel margins, recalc all 7 recipes
- 🟢 Use real COSTOS values as defaults
- 🟢 Wire `Product.price_gs` to `RecipePricing.channel=retail.unit_price_gs`

**Effort**: 2 days

---

### 2.6 Price History + Price Analysis 🆕 — `PriceHistory` model

**Source**: `HEREBUS_Suppliers.xlsx → Price_History` (empty template) + `Price_Analysis` (empty)

**Mapping**:
| Sheet column | Saskia field |
|---|---|
| `Fecha` | `PriceHistory.purchase_date` |
| `Supplier ID` | join Supplier |
| `Ingredient ID` | join Ingredient |
| `Cantidad comprada` | `PriceHistory.qty_purchased` |
| `Unidad` | `PriceHistory.unit` |
| `Precio total ₲` | `PriceHistory.total_gs` |
| `Precio unitario ₲` | (computed) |
| `Precio prom. histórico ₲` | (computed avg all history for this ing) |
| `Variación %` | (computed: current vs avg) |
| `Notas` | `PriceHistory.notes` |

**Auto-side effect**: when a PurchaseOrder is created → write PriceHistory row → trigger recompute on `Ingredient.unit_price_gs`

**Work**:
- 🆕 PriceHistory model
- 🆕 Auto-trigger on PurchaseOrder creation
- 🆕 `/analisis-precios` page: per-ingredient variability heatmap, recommendation per ingredient
- 🟢 Seed empty / blank

**Effort**: 2 days

---

### 2.7 Shopping List 🆕 — `ShoppingListItem` model

**Source**: `HEREBUS_Suppliers.xlsx → Shopping_List` (empty template)

**Mapping**:
| Sheet column | Saskia field |
|---|---|
| `Ingredient ID` | join Ingredient |
| `Cantidad a comprar` | `ShoppingListItem.qty_to_buy` |
| `Unidad` | `ShoppingListItem.unit` |
| `Precio unit prom. ₲` | (lookup from PriceHistory.avg) |
| `Costo estimado ₲` | (computed) |
| `Para receta / uso` | `ShoppingListItem.purpose_text` |
| `Comprado? (Sí/No)` | `ShoppingListItem.purchased` boolean |
| `Notas` | `ShoppingListItem.notes` |

**Auto-triggers**:
- From production planner (shortages → list)
- From reorder page (user)
- From "Ingredient.stock_qty < min_stock_qty" cron job (background)

**Work**:
- 🆕 ShoppingListItem model (linked to optional ProductionPlan)
- 🆕 `/shopping-list` route: merge view, mark-purchased
- 🆕 Hook into `/reponer` POST handler: when restock → convert ShoppingListItem to PriceHistory
- 🟢 Pre-populate from production shortfall

**Effort**: 1.5 days

---

### 2.8 Benchmarks vs Market 🆕 — `MarketBenchmark` model

**Source**: `HEREBUS_Analisis.xlsx → Benchmarks_Market` (17 rows, all empty 0 in our price col + CompA/B/Avg also empty)

**Mapping**:
| Sheet column | Saskia field |
|---|---|
| `Muffin de chocolate (und)` | `MarketBenchmark.product_label` |
| `Nuestro wholesale ₲` | (lookup from `RecipePricing.wholesale`) |
| `Nuestro retail ₲` | (lookup from `RecipePricing.retail`) |
| `Competidor A (mín) ₲` | `MarketBenchmark.comp_min_gs` (manual) |
| `Competidor B (prom) ₲` | `MarketBenchmark.comp_avg_gs` (manual) |
| `Mercado promedio ₲` | `MarketBenchmark.market_avg_gs` (manual) |
| `Posición` | (computed: '+20% caro' / 'competitivo' / etc) |
| `Notas / Fuente` | `MarketBenchmark.source` |

**Work**:
- 🆕 MarketBenchmark model
- 🆕 `/benchmarks` route: position badges, color-coded
- 🟢 Manual entry page (mostly human — Ivan or Saskia fills competitor prices)

**Effort**: 1 day

---

### 2.9 Channels 🆕 — `SaleChannel` enum (referenced but not modeled)

**Source**: `VENTAS` sheet has `Canal de Venta` column with `Retail / Wholesale / Eventual / Distribuidor`

**Work**:
- 🟡 Add `Sale.channel` enum to model
- 🟡 Update `/ventas` form to include channel combo
- 🟡 Channel filter on /reportes + dashboard

**Effort**: 0.5 day

---

## 🎯 PART 3 — Production data + Bank statements (parse and store)

### 3.1 Dutch bank TAB — 307 transactions, EUR

**Source**: `TXT260711013722.TAB` (Sept 2025 → Jun 2026)

**Mapping**:
| TAB field | Saskia field |
|---|---|
| Date (YYYYMMDD) | `BankTransaction.posted_at` |
| Amount delta (EUR) | `BankTransaction.amount_eur` |
| Description (SEPA Overboeking / Betaalpas / etc) | `BankTransaction.description` |
| Counterparty IBAN / Name | `BankTransaction.counterparty_*` |
| Balance run | `BankTransaction.balance_after` |
| Reference | `BankTransaction.reference` |

**Known patterns** found:
- **SEPA Overboeking** × 2+ — large incoming transfers (€300, €1,855, €1,439)
- **ONTV AAB USD 2,200.00** — incoming USD, gift for sister (Iván funding his sister/parent?)
- **C. Campbell pay back** — loans/IOUs to Saskia Ivan returning money to a third party
- **Geldmaat/Eindhoven recurring** — Dutch personal expenses (cash withdrawals, groceries)
- **KAARTNUMMER: **5365** — single card, fully traceable

**Work**:
- 🆕 `BankTransaction` model
- 🆕 `/bank` route: upload .TAB file, parse + dedupe + store
- 🆕 Reconciliation: manually tag each row → category (IVA-fuel, supplier-purchase, wage, food, etc)
- 🟢 Seed from TAB (only the 307 rows, imported once)

**Effort**: 1.5 days

---

### 3.2 WhatsApp bank image — Savings account June 2026

**Source**: `WhatsApp Image 2026-07-10 at 8.30.06 PM (2).jpeg`
**Holder**: SASKIA WEISS VANDER (Banco Familiar, Asunción PY)
**Cuenta**: 81-6209660 (savings)
**Saldo Actual**: 13,780,440 ₲
**Saldo Retenido**: 0

**12 transactions visible** (June 2026):
- 01/06 Transfers to many cards/services (couldn't read all)
- 15/06 -₲282,240 NETTOPIA → personal transfer
- 30/06 last visible row

**Work**:
- 🆕 Same `BankTransaction` model
- 🟢 Manual entry (image is small, OCR needed) OR attach as PDF-image reference
- 🟢 Mark as "Verificado (foto)" source vs "TAB formal"

**Effort**: 0.5 day

---

### 3.3 Recipe photos (14 jpgs)

**Source**: `20260728_221016.jpg` to `20260728_221930.jpg` (Dutch cookbook photos, hand-photographed)

**Identified recipes in photos**:
- Oliebollen / Buñuelos tradicionales (Dutch donuts) — recipe visible
- Basiscake 25cm (sponge cake 25cm)
- Basiscake 30cm (sponge cake 30cm)
- ~(12 more jpgs identified as Dutch cookbook pages with recipes)

**Work**:
- 🆕 Bucket: `/static/recipes/` (rename photos to recipe-NNN.jpg)
- 🆕 `Recipe.cover_image_url` field
- 🆕 Link photo → Recipe (manually map each photo in admin)
- 🟢 Display thumbnails on `/recetas` list

**Effort**: 0.5 day

---

## 🎯 PART 4 — UX/UI work (no new models, just improvements)

### 4.1 Configuration: business hours + pickup address ⚙️

**Source**: ZONAS_DELIVERY rows 8-14
- Address: Villa Amelia, San Lorenzo (cp 1100)
- Map: maps.app.goo.gl/nh54h4Az3pVRyovG7
- Coords: -25.316851, -57.515935
- Hours: Mié-Vie 11:00–19:00, Sáb 08:00–13:00
- Closed: Dom, Lun, Mar

**Work**:
- 🆕 `AppMeta` settings singleton with hours_json + pickup_address
- 🟢 `/settings` page to edit
- 🟢 Validate pedido delivery_date against hours

**Effort**: 0.5 day

---

### 4.2 Color palette ⚙️

**Source**: MAESTRA rows 19-25 (already in v1 spreadsheet, not yet in app.css)

| Hex | Name | Purpose |
|---|---|---|
| `#E8784A` | Acento | CTA, alertas |
| `#5C3D2A` | Neutro | Texto principal |
| `#FFB894` | Realce | Datos secundarios |
| `#B14E22` | Advertencia | Atención |
| `#1B5E20` | Operativo | Producción |
| `#DC2626` | Crítico | Riesgo/mermas |
| `#2A1A0E` | Marca | Ink900 |

**Work**:
- 🟢 Add CSS vars to app.css (or new vendor/saskia.css)
- 🟢 Apply by component (combos, badges, alerts)

**Effort**: 0.5 day

---

### 4.3 Supplier column on ingredients (FK migration) ⚙️

**Source**: INGREDIENTES.Proveedor column (every ingredient references one)

**Work**:
- 🟡 Migration: add `Ingredient.preferred_supplier_id` column
- 🟡 UI: supplier combo on `/inventario/nuevo` and `/inventario/{id}/editar`
- 🟢 When ingredient restocked → auto-record PriceHistory row

**Effort**: 0.5 day (already partially covered in 1.6)

---

## 📅 PART 5 — Phased delivery

### Phase A (week 1) — Core data ingest
- 1.1 ingredients (44) — 0.5d
- 1.2 recipes + lines (7, 68) — 1d
- 1.3 customers (8) — 0.5d
- 1.4 sales (10) — 0.5d
- 1.5 waste (3) — 0.25d
- 1.6 suppliers (7) — 0.25d
- 1.7 delivery zones (5) + business hours — 1d
- Tests + deploy — 0.5d

**Total Phase A**: 4.5 days

---

### Phase B (week 2) — New modules
- 2.1 Wishlist — 1.5d
- 2.4 Risk register — 1d
- 2.9 Channels enum — 0.5d
- 2.5 Pricing/Cost engine — 2d
- 2.6 Price History — 2d
- Tests — 0.5d

**Total Phase B**: 7.5 days

---

### Phase C (week 3) — Killer features
- 2.2 Production Planner — 2d
- 2.7 Shopping List — 1.5d
- 2.3 KPI Dashboard — 2d
- Tests — 0.5d

**Total Phase C**: 6 days

---

### Phase D (week 4) — Polish + ops
- 2.8 Benchmarks — 1d
- 3.1 Dutch bank parser — 1.5d
- 3.2 PY bank manual — 0.5d
- 3.3 Recipe photos — 0.5d
- 4.1 Settings UI — 0.5d
- 4.2 Color palette — 0.5d
- Tests — 0.5d

**Total Phase D**: 5.5 days

---

## 📊 TOTAL EFFORT

| Phase | Days | What unlocks |
|---|---|---|
| A | 4.5 | Saskia boots up with real HEREBUS data + delivery zones |
| B | 7.5 | Pricing engine + risk + wishlist + purchase tracking |
| C | 6.0 | **Production planner + shopping list + KPI dashboard** ← the killer apps |
| D | 5.5 | Bank reconciliation + benchmarks + photos + polish |

**Grand total: ~24 days of focused work = 5 weeks**

---

## 🏆 Priority ordering for biggest bang-for-buck

1. **1.7 Delivery zones + 1.1 Ingredients + 1.2 Recipes** = basic business operational immediately
2. **2.2 Production Planner** = the #1 tool Saskia is missing that spreadsheets clearly need
3. **2.5 Pricing engine + 2.9 Channels** = enable 4 sale channels (retail/wholesale/distributor/event)
4. **2.3 KPI Dashboard** = visible monthly health score
5. **3.1/3.2 Bank reconciliation** = know cashflow across 2 currencies
6. **2.4 Risk Register + 2.1 Wishlist** = operational/financial planning
7. **2.6 Price History + 2.7 Shopping List** = supply chain loop
8. **2.8 Benchmarks** = positioning vs competitors
