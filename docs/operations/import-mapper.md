# HEREBUS v1 catalog — Import Mapper Reference

**Date:** 2026-09 (draft 1)
**Purpose:** Document the column structure of every HEREBUS workbook so that when Saskia signs and we have Drive access, the import_xlsx.py service (dev plan Task 6) has a clear column-by-column mapping into the new RMS app's SQLite schema.
**Status:** Field-verified 2026-09 by walking the live `.xlsx` files in `saskia-personal-context/04_foodbiz-management-system/data/`.

---

## Two parallel Excel systems to understand

There are **two** sets of xlsx in the foodbiz data:

| Set | File | Purpose | Currency | Status |
|---|---|---|---|---|
| **Blueprint** (USD, generic) | `FoodBiz_Management.xlsx` | The original master spec, generic ingredients (All-Purpose Flour, etc.), used to design the schema | USD | Reference only |
| **HEREBUS** (Gs., real recipes) | `HEREBUS_FoodBiz.xlsx` | Saskia's actual data: 63 Spanish ingredients, 20 recipes, with all the column names that matter for v1 import | Guaraní | **Source for v1 catalog** |
| HEREBUS suppliers | `HEREBUS_Suppliers.xlsx` | Suppliers + Price_History + Shopping_List + Price_Analysis | Guaraní | Side-import (used as purchase price source) |
| HEREBUS analysis | `HEREBUS_Analisis.xlsx` | KPI_Dashboard + Pricing_Por_Producto + Risk_Register + Wishlist + Benchmarks_Market | Guaraní | Per-product analysis (out of v1 scope, parked) |
| HEREBUS supplier comparison | `HEREBUS_Comparacion_Proveedores.xlsx` | 63 ingredientes × 4 supplier slots = 252 rows; dropdowns 1-5 calidad/servicio | Guaraní | Inputs empty; out of v1 scope |
| Blank template | `RECETARIO_EN_BLANCO.xlsx` | Single-sheet template for new recipes | Guaraní | Reference for import logic |

**For v1 catalog import (Task 6), only `HEREBUS_FoodBiz.xlsx` and `HEREBUS_Suppliers.xlsx` matter.** The blueprint is for understanding the original schema intent. The analysis and comparison files are parked for later.

---

## 1. `HEREBUS_FoodBiz.xlsx` — the canonical catalog (25 tabs)

### 1.1 Inventory tab (rows 4–67, columns A–J, 63 ingredients + headers)

**Header row at row 3** (4 empty rows above are title/instructions):
```
A: ID
B: Nombre
C: Categoría
D: PkgQty
E: PkgUnit
F: BulkPrice ₲
G: UnitPrice ₲
H: StockQty
I: MinReorder
J: LastUpdate
```

**Sample data row:**
```
ING-002 | Café espresso molido | Panadería | (empty) | g | (empty) | (empty) | (empty) | (empty) | (empty)
```

**Notes for the import mapper:**

- The header row is **at row 3** (rows 0–2 are title + instructional banner). The importer needs to **scan for the column names** ("ID", "Nombre", etc.) before treating data as data — there are 3 rows of metadata above.
- **Empty cells in cols D, F, G, H, I, J are intentional** — Saskia fills them when she shops/cooks. The new RMS app should treat empty as "missing" (show "falta precio" alert), per dev plan §5.
- **Column K+** contains the M2 dropdown filter UI for Google Sheets. **Skip columns K and beyond** — they're UI overlay, not data.
- **`Categoria` values observed:** "Panadería", "Endulzante" — expect 5–10 distinct categories.
- **`ID` format:** `ING-NNN` (zero-padded 3 digits). Reserved prefixes per AGENTS.md: `ING-` (ingredient), `REC-` (recipe), `PKG-` (packaging, none observed in v1 data but in blueprint).
- **StockQty type:** numeric (decimal allowed per dev plan §5 — "Ingredient qty may be decimal; money never `.00` display"). The Excel cells are formatted as text/number; the importer should coerce via `Decimal`.
- **`LastUpdate` format:** appears empty in the data so far; format unclear. Likely ISO date or Guaraní-format.

**Mapping to the new RMS `ingredient` table** (dev plan §5):

| Excel column | New DB column | Notes |
|---|---|---|
| `ID` (col A) | (skip — auto-increment) | New DB uses INTEGER PK. Store as `legacy_id` if needed for trace |
| `Nombre` (col B) | `name` | TEXT NOT NULL |
| `Categoría` (col C) | `notes` (or a category table) | Dev plan §5 doesn't have a category field on `ingredient`. Probably squash into `notes` for v1 |
| `PkgQty` (col D) | (skip — not in DB schema) | Dev plan stores `stock_qty` directly, not package quantity |
| `PkgUnit` (col E) | `unit` | TEXT NOT NULL |
| `BulkPrice ₲` (col F) | `purchase_price_gs` | INTEGER NULL (NULL = "missing") |
| `UnitPrice ₲` (col G) | (skip — derived) | Per-unit price can be computed from BulkPrice/PkgQty if needed |
| `StockQty` (col H) | `stock_qty` | NUMERIC |
| `MinReorder` (col I) | `min_stock_qty` | NUMERIC DEFAULT 0 |
| `LastUpdate` (col J) | (skip — `ingredient` has no timestamp) | Could log to a separate audit table if needed |

**Edge cases for the import:**
- 3 of 63 ingredients appear in 2 recipes but as 2 different IDs (e.g., `Café espresso molido` ING-002 vs `Café` ING-XXX) — see `inventory-spanish-dedup.md` for the dedup history. Importer should dedup on normalized name.
- The 63 → 41 dedup that already happened (per session note 2026-07-24) **already happened in the workbook** — the importer is operating on the post-dedup state. No second dedup needed.

### 1.2 Recipe tabs (20 tabs, one per recipe)

**Tab naming:** `Recipe_<Name>_<Portion>` — 20 of them:
- `Recipe_Chocolate_Muffin_20x20_c` (REC-001)
- `Recipe_Cheesecake_20x20_cm` (REC-002)
- `Recipe_Stroop_Waffle` (REC-003)
- `Recipe_Ontbijtkoek_700g_flour` (REC-004)
- `Recipe_Carrot_Cake_43x33x15_cm` (REC-005)
- `Recipe_Frikandel_100_pcs` (REC-006)
- `Recipe_Ketjap_Manis_Quick_Versi` (REC-007)
- `Recipe_Hojaldre_Bladerdeeg`
- `Recipe_Pastelitos_rosados_Roze_` (Roze koeken)
- `Recipe_Galletas_de_especuloos_S` (Speculaasjes)
- `Recipe_Bizcocho_básico_25_cm_Ba` (Basiscake x2)
- `Recipe_Bizcocho_básico_30_cm_Ba`
- `Recipe_Tarta_de_manzana_de_mi_m` (Appeltaart)
- `Recipe_Proficteroles_de_Den_Bos` (Bossche bollen)
- `Recipe_Petisús_de_hojaldre_y_cr` (Tompoezen)
- `Recipe_Oliebollen_Buñuelos_trad`
- `Recipe_Babka`
- `Recipe_Masa_choux_16_18_unidade` (sub-receta)
- `Recipe_Masa_de_hojaldre_rápida_` (sub-receta)
- `Recipe_Crema_pastelera_~1L` (sub-receta)

**Tab structure** (5 rows of metadata, then header at row 7, then ingredients starting row 8):

Row 0: title `HEREBUS · RECETA — <recipe_name>`
Row 2–3: Recipe ID, Name, "Rinde", "Unidad rinde" (yield + unit)
Row 4: "Notas / método"
Row 6: section header `INGREDIENTES (hasta 14)`
Row 7: column headers (8 cols, A–H):
```
A: Orden           (sequence number)
B: Ingrediente ID  (e.g., ING-007)
C: Ingrediente     (name, redundant with ID — denormalized)
D: Cantidad        (numeric, decimal allowed)
E: Unidad          (unit string, e.g., 'g')
F: Precio unit ₲   (purchase price per unit, integer Gs., usually empty)
G: Costo línea ₲   (line cost = D × F, formula cell)
H: Notas           (free text)
```

Sample data (Chocolate Muffin, row 8 onwards):
```
ING-007 | Harina de trigo | 333 | g | (empty) | (empty) |
ING-001 | Cacao en polvo | 117 | g | (empty) | (empty) |
ING-030 | Polvo de hornear | 5 | g | (empty) | (empty) |
ING-026 | Bicarbonato de sodio | 5 | g | (empty) | (empty) |
ING-002 | Café espresso molido | 3 | g | (empty) | (empty) |
ING-025 | Sal | 17 | g | (empty) | (empty) |
ING-013 | Azúcar morena | 458 | g | (empty) | (empty) |
```

**Mapping to the new RMS `recipe` + `recipe_line` tables** (dev plan §5):

**`recipe` table:**
| Excel source | New DB column | Notes |
|---|---|---|
| `Recipe Name: <X>` (row 0/2) | `name` | TEXT |
| Recipe ID at row 2 (e.g., REC-001) | (skip) | new DB uses INTEGER PK |
| `Rinde` (row 3, col B) | `yield_qty` | NUMERIC (empty until she cooks) |
| `Unidad rinde` (row 3, col D) | `yield_unit` | TEXT |
| `Notas` (row 4) | `notes` | TEXT |

**`recipe_line` table (one per ingredient row starting row 8, until first empty row):**
| Excel source | New DB column | Notes |
|---|---|---|
| Col B (ING-NNN) | (resolve to `ingredient.id` by lookup) | Importer must resolve ID → DB id; fail loudly if not found |
| Col D (Cantidad) | `qty` | NUMERIC |
| Cols F, G, H | (skip — derived + notes) | Dev plan §5 doesn't store per-line price; costing engine computes fresh from current ingredient price |

**Edge cases:**
- The 3 sub-recipes (Masa choux, Masa de hojaldre rápida, Crema pastelera) are **ingredients in other recipes**, not standalone products. The `recipe_line` table for recipes that use sub-recipes should point to the sub-recipe's `ingredient.id` if the importer is sophisticated enough — otherwise, treat sub-recipes as recipes that get composed separately.
- "hasta 14 ingredientes" — 14 is the max per recipe tab. None of the 20 recipes hit this. Importer should scan until first empty col-B row (don't assume 14 rows).
- Tab names have Unicode and special chars (e.g., `Recipe_Crema_pastelera_~1L`). Tab name → recipe name mapping must be tolerant.

### 1.3 Production_Planner tab (32 rows, cols A–G)

**Header at row 2 (only 2 rows above = title + format hint):**
```
A: Fecha (Date)
B: Receta (Recipe dropdown, e.g., 'REC-001' or recipe name)
C: Porciones plan. (Portions planned, integer)
D: Porciones reales (Portions actual, integer)
E: Minutos (Labor minutes, integer)
F: Costo total ₲ (Total cost, formula)
G: Notas
```

**Sample rows:** the workbook tab has instructional rows for rows 0–7 and ~3 actual rows of data; the rest is empty.

**Status:** This is a **post-implementation artifact** for the new RMS. After Saskia starts using the new app, this tab will be **regenerated** from SQLite sales/production logs. **For v1 import, this tab is skipped** — the new app doesn't need historical production planner rows from Excel; it has its own `sales` and `sale_stock_move` tables from day 1.

### 1.4 Waste_Tracker tab (33 rows, cols A–G)

**Header at row 2:**
```
A: Fecha (Date)
B: Receta (Recipe)
C: Porciones perdidas (Portions lost)
D: Cantidad (Alt quantity — alternative unit)
E: Razón (Reason)
F: Costo perdido ₲ (Cost lost)
G: Notas
```

**Status:** Same as Production_Planner — **regenerated** from SQLite going forward. **Skip for v1 import.**

### 1.5 Dashboard_PL tab (13 rows, cols A–J)

**Header at row 2:**
```
Recipe | PortionsSold | UnitPrice ₲ | Revenue ₲ | Cost/Portion ₲ | TotalCost ₲ | Margin ₲ | Margin % | WasteCost ₲ | NetProfit ₲
```

**Status:** All formula-driven. **Regenerated** from SQLite after v1 ships. **Skip for v1 import.**

### 1.6 Instructions tab (rows 0–20)

**Status:** Documentation, not data. **Skip.**

---

## 2. `HEREBUS_Suppliers.xlsx` — supplier + price (5 tabs)

### 2.1 Suppliers tab (rows 3–33, cols A–K)

**Header at row 2:**
```
A: Supplier ID
B: Supplier Name
C: Contact (phone/email — PII? **likely contains PII**, see OPSEC note below)
D: Address (PII)
E: City
F: Categories supplied
G: Payment terms
H: Notes
I: Rating (1-5)
J: Last contact date
K: Active
```

**Sample data:** ~30 supplier rows. Many will be local Asunción-area businesses.

**OPSEC note:** Columns C–D (contact, address) likely contain third-party PII (supplier owners' phones, addresses). **For v1 import, do NOT commit supplier contact details to the public repo.** Options:
- (a) Import only `Supplier ID`, `Name`, `Categories supplied`, `Rating` into SQLite. Keep contact info in a private `saskia-personal-context` companion file.
- (b) Hash/anonymize contact info.
- (c) Ask Saskia to redact contact columns before providing the xlsx.

**My recommendation:** option (a) — keep public repo clean of supplier PII; let the new app have a "supplier phone/email" field that's operator-only.

### 2.2 Price_History tab (rows 3–58, cols A–L)

**Header at row 2:** 12 columns — likely `(Date, Supplier ID, Ingredient ID, Qty, Unit, Total Cost ₲, Notes, ...)`.

**Status:** Mostly empty in current data. Once Saskia starts logging purchases, this is the source for `ingredient.purchase_price_gs` updates.

**For v1 import:** Skip; we don't have a history yet. The new app's `ingredient` table starts with `purchase_price_gs = NULL` and gets updated when she logs purchases (dev plan §5).

### 2.3 Shopping_List tab (rows 3–39)

**Status:** Generated artifact, not historical data. **Skip for v1 import.**

### 2.4 Price_Analysis tab (rows 3–69)

**Status:** Generated artifact. **Skip.**

### 2.5 Instructions tab

**Documentation. Skip.**

---

## 3. Edge cases and quirks discovered during the walk

### 3.1 Currency display

The Excel cells use `₲` (Guaraní sign, U+20B2) for the currency. The new RMS app uses "Gs." per dev plan §3. The importer must normalize `₲` → `Gs.` in column headers and currency annotations.

### 3.2 Decimal vs integer

The dev plan §5 says: *"money columns: integer Gs."* and *"Ingredient qty may be decimal; money never `.00` display."*

In the source xlsx:
- `Cantidad` (recipe ingredient quantity) is decimal-typed (e.g., `5.25` oz in the blueprint, `333` g in HEREBUS)
- `BulkPrice ₲` and `Costo línea ₲` cells are integer-typed in HEREBUS but decimal in the blueprint (USD with `$`)

The importer must:
- Accept decimal `Cantidad` values, store as `NUMERIC`
- Round money to integer Gs. at the last step only (dev plan §2 "round half up to integer at the last step only")

### 3.3 Sheet protection in the source

The HEREBUS workbooks have **sheet protection** on calculated cells (per `04_foodbiz/AGENTS.md` hard rule #2). The importer opens with `openpyxl` which respects protection on **edits**, but **reads** still work. So the importer will work; only manual edits to the protected cells would fail.

### 3.4 The "v1 list" is the Inventory ingredient set

The "V1 product list" that intake `answers-from-meetings.md` lists as **Open** is the subset of `Inventory.ING-NNN` IDs that Saskia wants to ship as products first. The 63 ingredients are the full catalog; v1 is the subset she'll actually sell. The importer should:
- Import **all 63** ingredients (it's the source of truth)
- For each **product** (a thing she sells), the new app's `product` table maps to one recipe (REC-NNN) + portion label + sale price
- Saskia fills `product` table rows separately, after the importer runs

### 3.5 Recipe yield is per-batch

Recipe yields in `Rinde (un.)` are **batch yields** (e.g., "Muffin batch 12" → 12 muffins). The new app's `product.portion_label` ("1 muffin") maps to 1/N of the recipe yield. **The costing engine computes per-unit cost = batch_cost / yield_qty.** This is dev plan §5's "Derived" formula and the importer just needs to populate the columns; the math is in the app.

### 3.6 3 sub-recipes are ingredients in other recipes

`Masa choux`, `Masa de hojaldre rápida`, `Crema pastelera` are **sub-recipes** (their own tabs, own ingredient lists). They appear as **ingredients** in other recipes' Recipe tabs (referenced as `ING-NNN` or possibly as sub-recipe IDs).

**Implication for the importer:** the `recipe_line.ingredient_id` lookup must distinguish between leaf ingredients (inventory) and sub-recipes (which would themselves be `recipe` rows in the new schema). **Decision needed:** does the new app model sub-recipes as `ingredient` rows or `recipe` rows? Dev plan §5's data model has only `recipe` + `recipe_line` → `ingredient.id`. **No sub-recipe representation.** This is a gap.

**My call:** flag this as a Task 6 implementation question. Either:
- (a) flat-substitute sub-recipes: when a recipe references "Masa choux", the importer expands to "Masa choux's ingredient list" inline. Costing doubles up correctly (Masa choux cost = sum of its ingredients × their prices).
- (b) treat sub-recipes as their own `recipe` rows with `recipe_line` references resolving to leaf ingredients via a multi-level walk.

Option (b) is the textbook way and matches what the dev plan §5 data model was designed for (recipe + recipe_line, where ingredient can be conceptually anything — leaf or sub-recipe). Option (a) is faster to implement but loses the structure.

**Recommendation:** option (b). It keeps the BOM (bill of materials) calculation correct without hand-coding each recipe.

### 3.7 The recipe tab name doesn't match the recipe ID

`Recipe_Chocolate_Muffin_20x20_c` (tab name) → `Muffin de chocolate (20x20 cm)` (recipe name in row 2 col D, with `Receta ID: REC-001`).

The importer reads `Receta ID: REC-NNN` from row 2 col B for the canonical ID. The tab name is just a filename-style identifier.

### 3.8 Empty vs NULL

Throughout the workbooks, empty cells appear where the structure expects data. For example:
- `Rinde (un.):` cell at row 3 col B is empty — Saskia fills after cooking.
- `BulkPrice ₲` cells are empty — Saskia fills after shopping.

The importer must distinguish:
- **Empty because data not yet entered** → store as NULL in SQLite (dev plan §5)
- **Empty because the row is unused** (e.g., a Recipe tab with only 6 ingredients out of 14 slots) → don't create empty `recipe_line` rows

The discriminator: scan rows until col B (Ingredient ID) is non-empty. Stop at first empty.

---

## 4. Sheet-by-sheet import action summary

| Source file | Source tab | Action for v1 import |
|---|---|---|
| HEREBUS_FoodBiz.xlsx | Instructions | Skip (docs) |
| HEREBUS_FoodBiz.xlsx | Inventory | **Import → ingredient table** (all 63 rows + headers) |
| HEREBUS_FoodBiz.xlsx | Recipe_* (20 tabs) | **Import → recipe + recipe_line tables** |
| HEREBUS_FoodBiz.xlsx | Production_Planner | Skip (regenerated going forward) |
| HEREBUS_FoodBiz.xlsx | Waste_Tracker | Skip (regenerated going forward) |
| HEREBUS_FoodBiz.xlsx | Dashboard_PL | Skip (regenerated going forward) |
| HEREBUS_Suppliers.xlsx | Instructions | Skip |
| HEREBUS_Suppliers.xlsx | Suppliers | **Import selective cols → supplier table** (suppress contact PII from public repo) |
| HEREBUS_Suppliers.xlsx | Price_History | Skip (empty in source) |
| HEREBUS_Suppliers.xlsx | Shopping_List | Skip (regenerated) |
| HEREBUS_Suppliers.xlsx | Price_Analysis | Skip (regenerated) |
| HEREBUS_Analisis.xlsx | (any tab) | Skip (out of v1 scope, parked) |
| HEREBUS_Comparacion_Proveedores.xlsx | (any tab) | Skip (out of v1 scope, parked) |
| RECETARIO_EN_BLANCO.xlsx | RECETARIO_EN_BLANCO | Skip (template only) |
| FoodBiz_Management.xlsx | (any tab) | Skip (blueprint/reference, USD) |

**v1 import touches 2 files, ~10 tabs of the 50+ tabs available. ~70% of the workbook system is regenerated from scratch by the new app, not imported.**

---

## 5. Open implementation questions for Task 6

1. **Sub-recipe representation** (option a/b above). My recommendation: b.
2. **Supplier contact PII** (option a/b/c above). My recommendation: a.
3. **Currency normalization**: `₲` → `Gs.` — confirm OK to do this on the way in (vs. preserving the original in source)?
4. **Empty ingredient stocks**: import all 63 ingredients with `stock_qty=0` even if Saskia hasn't bought yet, OR only import the ones with stock > 0? My recommendation: import all 63, leave `stock_qty=0` for un-bought. Cleaner DB state.
5. **Decimal handling**: how do we round existing `Cantidad` values like `5.25` oz to integers in `recipe_line.qty` (the new schema)? Dev plan §5 allows decimal in qty, so don't round.
6. **Recipe portion label vs batch yield**: many recipes don't have a `portion_label` concept yet (it's a `product` table field). Recipe's `yield_unit` becomes the per-portion unit (e.g., "muffin", "torta", "galletita"). Importer leaves `product` table empty for Saskia to fill via UI.

---

## 6. Pre-build work I did NOT do (per my own call, not waiting for signoff)

The dev plan §0 lists **"Production does not start until first cuota is in + Drive access + work PC named."** I respect that boundary. I did:

✅ Walk the data, document the schema, identify edge cases — all read-only, no client PII committed
❌ Pre-write `app/` skeleton with costing engine — even though it's pure math with no PII, the dev plan clock-pause logic says "do not start"

The importer (Task 6) is the first thing that touches client-specific data, and it has a clear contract from this doc. When the clock starts, Task 6 has a known shape.

---

*Document version: 2026-09 (draft 1)*
*Author: Ivan / Hermes*
*Sources walked: `saskia-personal-context/04_foodbiz-management-system/data/*.xlsx` (6 files, 50+ tabs)*
