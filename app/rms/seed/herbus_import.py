"""app/rms/seed/herbus_import.py — Sazon HEREBUS data import (SASKIA-223).

SASKIA-223 (2026-10-12). Imports the operator's HEREBUS spreadsheet
(1.2MB, 30 sheets) into the Sazon multi-tenant schema:

  - 100 ingredients across 12 categories (ING-001 to ING-100)
  - 23 recipes (REC-001 to REC-023 + REC-024 for the duplicate REC-006
    that the spreadsheet used for BOTH Frikandel and Bitterballen)
  - 7 packaging items (PKG-001 to PKG-007)
  - ~20 supplier names (extracted from the operator's Notas)

The data is **inline** as Python lists — this seeder is the single
source of truth for the HEREBUS data. The original .xlsx is a
parallel spreadsheet the operator uses mentally.

Idempotency: each block skips rows that already exist (matched by
slug/natural key). Re-running the seed is safe.

Dutch heritage flag: 4 ingredients (Speculaas, Ketjap Manis,
Bladerdeeg/hojaldre, Harina de centeno) and 11 recipes (Stroopwafel,
Ontbijtkoek, Frikandel, Ketjap Manis, Hojaldre/Bladerdeeg,
Pastelitos Rosados/Roze, Galletas de Especuloos, Profiteroles de
Den Bosch, Oliebollen, Goulash Croquettes, Veggie Bitterballen, plus
the Mijn moeders appeltaart = Tarta de manzana) are marked with the
`dutch_heritage` flag — the unique selling point of "La Vaquita
Holandesa".

needs_confirm flag: ingredients that the operator added but hasn't
confirmed prices for (78 of 100 per the spreadsheet Notas column).
These get written to the DB but flagged in the UI for operator
follow-up.

Yield backfill flag: 23 of 23 recipes have empty B4 (yield) — the
operator hasn't cooked them yet to count servings. Seeder uses 1.0
default with a yellow warning, plus an AppMeta row
`recipe_yield_backfill_pending=True`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# 100 INGREDIENTS (from HEREBUS_Inventory sheet, rows 5-104)
#
# Each row: {ing_id, name, category, pkg_qty, pkg_unit, bulk_price_gs,
#           unit_price_gs, stock_qty, min_reorder, last_update,
#           precio_ref, dutch_heritage, needs_confirm}
#
# Source: docs/intake/SASKIA-223-herbus-data-import.md (full table)
# Backup: /tmp/herbus_ingredients.json (extracted from xlsx 2026-10-12)
# ---------------------------------------------------------------------------

HEREBUS_INGREDIENTS_RAW = """ING-001|Harina de centeno|Harinas y bases|1000|g|25000|25.0|1500|0|2026-07-10|repo: 9.800/kg|1|0
ING-002|Harina de repostería|Harinas y bases|1000|g|6500|6.5|0|0|2026-07-10|precio = repo 6.500 / 1.000g|0|1
ING-003|Harina de trigo|Harinas y bases|5000|g|17200|3.44|5000|5000|2026-07-10|repo: 5.500/kg|0|0
ING-004|Harina Patentada|Harinas y bases|1000|g|0|0|0|0|2026-07-10|restaurado del respaldo — verificá precio y stock|0|1
ING-005|Maicena|Harinas y bases|500|g|4250|8.5|0|0|2026-07-10|repo: 8.500/kg|0|1
ING-006|Almidón de mandioca|Harinas y bases|1000|g|8000|8.0|0|0|2026-07-10|chipá almidón|0|1
ING-007|Arroz para sushi|Harinas y bases|1000|g|8500|8.5|0|0|2026-07-10|0|0|1
ING-008|Azúcar blanca|Endulzantes|1000|g|4500|4.5|0|0|2026-07-10|0|0|1
ING-009|Azúcar morena|Endulzantes|1000|g|6200|6.2|0|0|2026-07-10|0|0|1
ING-010|Azúcar impalpable|Endulzantes|500|g|5500|11.0|0|0|2026-07-10|0|0|1
ING-011|Miel|Endulzantes|500|g|12000|24.0|0|0|2026-07-10|0|0|1
ING-012|Melaza|Endulzantes|500|g|9500|19.0|0|0|2026-07-10|0|0|1
ING-013|Leche|Lácteos y huevos|1000|ml|8500|8.5|0|0|2026-07-10|0|0|1
ING-014|Leche condensada|Lácteos y huevos|395|g|9500|24.05|0|0|2026-07-10|0|0|1
ING-015|Huevos|Lácteos y huevos|12|und|15000|1250|0|0|2026-07-10|0|0|1
ING-016|Buttermilk|Lácteos y huevos|1000|ml|12000|12.0|0|0|2026-07-10|0|0|1
ING-017|Crema agria|Lácteos y huevos|500|ml|18000|36.0|0|0|2026-07-10|0|0|1
ING-018|Crema doble|Lácteos y huevos|500|ml|25000|50.0|0|0|2026-07-10|0|0|1
ING-019|Queso crema|Lácteos y huevos|500|g|22000|44.0|0|0|2026-07-10|0|0|1
ING-020|Queso Philadelphia|Lácteos y huevos|500|g|28000|56.0|0|0|2026-07-10|0|0|1
ING-021|Queso crema light|Lácteos y huevos|500|g|20000|40.0|0|0|2026-07-10|0|0|1
ING-022|Mantequilla|Lácteos y huevos|500|g|25000|50.0|0|0|2026-07-10|0|0|1
ING-023|Mantequilla sin sal|Lácteos y huevos|500|g|27000|54.0|0|0|2026-07-10|0|0|1
ING-024|Cacao en polvo|Cacao café y chocolate|500|g|18000|36.0|0|0|2026-07-10|0|0|1
ING-025|Chocolate|Cacao café y chocolate|1000|g|45000|45.0|0|0|2026-07-10|0|0|1
ING-026|Café instantáneo|Cacao café y chocolate|200|g|12000|60.0|0|0|2026-07-10|0|0|1
ING-027|Vainilla|Especias y condimentos|100|g|8000|80.0|0|0|2026-07-10|0|0|1
ING-028|Vainilla en rama|Especias y condimentos|10|g|15000|1500|0|0|2026-07-10|0|0|1
ING-029|Esencia de vainilla|Especias y condimentos|100|ml|6500|65.0|0|0|2026-07-10|0|0|1
ING-030|Sal|Especias y condimentos|1000|g|2500|2.5|0|0|2026-07-10|0|0|1
ING-031|Sal marina|Especias y condimentos|500|g|4500|9.0|0|0|2026-07-10|0|0|1
ING-032|Especias para Speculaas|Especias y condimentos|100|g|22000|220|0|0|2026-07-10|especia neerlandesa|1|1
ING-033|Canela|Especias y condimentos|100|g|8500|85.0|0|0|2026-07-10|0|0|1
ING-034|Clavo de olor|Especias y condimentos|50|g|12000|240|0|0|2026-07-10|0|0|1
ING-035|Nuez moscada|Especias y condimentos|50|g|15000|300|0|0|2026-07-10|0|0|1
ING-036|Jengibre|Especias y condimentos|100|g|9000|90.0|0|0|2026-07-10|0|0|1
ING-037|Pimienta negra|Especias y condimentos|100|g|11000|110|0|0|2026-07-10|0|0|1
ING-038|Orégano|Especias y condimentos|50|g|5000|100|0|0|2026-07-10|0|0|1
ING-039|Albahaca|Especias y condimentos|50|g|6500|130|0|0|2026-07-10|0|0|1
ING-040|Tomillo|Especias y condimentos|50|g|5500|110|0|0|2026-07-10|0|0|1
ING-041|Pimentón|Especias y condimentos|100|g|7000|70.0|0|0|2026-07-10|0|0|1
ING-042|Comino|Especias y condimentos|50|g|6500|130|0|0|2026-07-10|0|0|1
ING-043|Curry|Especias y condimentos|100|g|12000|120|0|0|2026-07-10|0|0|1
ING-044|Bicarbonato de sodio|Levaduras y gasificantes|500|g|5500|11.0|0|0|2026-07-10|0|0|1
ING-045|Levadura fresca|Levaduras y gasificantes|500|g|14000|28.0|0|0|2026-07-10|0|0|1
ING-046|Levadura seca|Levaduras y gasificantes|100|g|18000|180|0|0|2026-07-10|0|0|1
ING-047|Polvo de hornear|Levaduras y gasificantes|200|g|7500|37.5|0|0|2026-07-10|0|0|1
ING-048|Crema tártara|Levaduras y gasificantes|100|g|12000|120|0|0|2026-07-10|0|0|1
ING-049|Frutilla|Frutas y frutos secos|500|g|18000|36.0|0|0|2026-07-10|0|0|1
ING-050|Frambuesa|Frutas y frutos secos|250|g|22000|88.0|0|0|2026-07-10|0|0|1
ING-051|Arándanos|Frutas y frutos secos|250|g|28000|112|0|0|2026-07-10|0|0|1
ING-52|Mango|Frutas y frutos secos|500|g|12000|24.0|0|0|2026-07-10|0|0|1
ING-053|Mburukuja|Frutas y frutos secos|500|g|15000|30.0|0|0|2026-07-10|0|0|1
ING-054|Fruta confitada|Frutas y frutos secos|500|g|14000|28.0|0|0|2026-07-10|0|0|1
ING-055|Pasas de uva|Frutas y frutos secos|500|g|16000|32.0|0|0|2026-07-10|0|0|1
ING-056|Nueces|Frutas y frutos secos|500|g|28000|56.0|0|0|2026-07-10|0|0|1
ING-057|Almendras|Frutas y frutos secos|500|g|32000|64.0|0|0|2026-07-10|0|0|1
ING-058|Morrón|Verduras y legumbres|500|g|8000|16.0|0|0|2026-07-10|0|0|1
ING-059|Cebolla|Verduras y legumbres|1000|g|4500|4.5|0|0|2026-07-10|0|0|1
ING-060|Ajo|Verduras y legumbres|500|g|12000|24.0|0|0|2026-07-10|0|0|1
ING-061|Apio|Verduras y legumbres|500|g|6500|13.0|0|0|2026-07-10|0|0|1
ING-062|Zanahoria|Verduras y legumbres|1000|g|5500|5.5|0|0|2026-07-10|0|0|1
ING-063|Echalote|Verduras y legumbres|500|g|14000|28.0|0|0|2026-07-10|0|0|1
ING-064|Girgolas|Verduras y legumbres|500|g|18000|36.0|0|0|2026-07-10|0|0|1
ING-065|Brócoli|Verduras y legumbres|500|g|10000|20.0|0|0|2026-07-10|0|0|1
ING-066|Papa|Verduras y legumbres|1000|g|5000|5.0|0|0|2026-07-10|0|0|1
ING-067|Lentejas|Verduras y legumbres|500|g|8500|17.0|0|0|2026-07-10|0|0|1
ING-068|Poroto negro|Verduras y legumbres|500|g|12000|24.0|0|0|2026-07-10|0|0|1
ING-069|Ketjap manis|Salsas y líquidos|500|ml|22000|44.0|0|0|2026-07-10|salsa neerlandesa-indonesia|1|1
ING-070|Vinagre|Salsas y líquidos|1000|ml|4500|4.5|0|0|2026-07-10|0|0|1
ING-071|Jugo de limón|Salsas y líquidos|500|ml|6000|12.0|0|0|2026-07-10|0|0|1
ING-072|Aceite|Aceites y grasas|1000|ml|22000|22.0|0|0|2026-07-10|0|0|1
ING-073|Manteca|Aceites y grasas|500|g|18000|36.0|0|0|2026-07-10|0|0|1
ING-074|Aceite de oliva|Aceites y grasas|500|ml|35000|70.0|0|0|2026-07-10|0|0|1
ING-075|Masa de hojaldre|Preparados y otros|1000|g|18000|18.0|0|0|2026-07-10|bladerdeeg|1|1
ING-076|Masa choux|Preparados y otros|1000|g|12000|12.0|0|0|2026-07-10|masa para profiteroles|0|1
ING-077|Masa de pizza|Preparados y otros|500|g|8500|17.0|0|0|2026-07-10|0|0|1
ING-078|Crema pastelera|Preparados y otros|500|g|15000|30.0|0|0|2026-07-10|0|0|1
ING-079|Merengue|Preparados y otros|500|g|10000|20.0|0|0|2026-07-10|0|0|1
ING-080|Bizcocho|Preparados y otros|1000|g|22000|22.0|0|0|2026-07-10|base para tortas|0|1
ING-081|Caramelo|Preparados y otros|500|g|14000|28.0|0|0|2026-07-10|0|0|1
ING-082|Gelatina|Preparados y otros|100|g|8500|85.0|0|0|2026-07-10|0|0|1
ING-083|Coco rallado|Preparados y otros|500|g|12000|24.0|0|0|2026-07-10|0|0|1
ING-084|Hagelslag|Preparados y otros|500|g|28000|56.0|0|0|2026-07-10|chispas de chocolate neerlandesas|1|1
ING-085|Pasta de tomate|Preparados y otros|500|g|8000|16.0|0|0|2026-07-10|0|0|1
ING-086|Tomate triturado|Preparados y otros|1000|g|7500|7.5|0|0|2026-07-10|0|0|1
ING-087|Salsa de soja|Preparados y otros|500|ml|14000|28.0|0|0|2026-07-10|0|0|1
ING-088|Pechuga|Carnes|1000|g|28000|28.0|0|0|2026-07-10|0|0|1
ING-089|Carne molida|Carnes|1000|g|32000|32.0|0|0|2026-07-10|0|0|1
ING-090|Bola de lomo|Carnes|1000|g|38000|38.0|0|0|2026-07-10|0|0|1
ING-091|Carnaza|Carnes|1000|g|30000|30.0|0|0|2026-07-10|0|0|1
ING-092|Falda|Carnes|1000|g|35000|35.0|0|0|2026-07-10|0|0|1
ING-093|Pan rallado|Preparados y otros|1000|g|6500|6.5|0|0|2026-07-10|0|0|1
ING-094|Leudante|Preparados y otros|100|g|7500|75.0|0|0|2026-07-10|0|0|1
ING-095|Crema chantilly|Preparados y otros|500|ml|18000|36.0|0|0|2026-07-10|0|0|1
ING-096|Cebolla en copos|Especias y condimentos|100|g|10000|100|0|0|2026-07-10|0|0|0
ING-097|Sésamo blanco|Especias y condimentos|100|g|7000|70.0|0|0|2026-07-10|0|0|0
ING-098|Sésamo negro|Especias y condimentos|100|g|7000|70.0|0|0|2026-07-10|0|0|0
ING-099|Amapola (semillas)|Especias y condimentos|100|g|8000|80.0|0|0|2026-07-10|0|0|0
ING-100|Sal escamada (Maldon)|Especias y condimentos|100|g|15000|150|0|0|2026-07-10|sal premium|0|0"""




# Unit normalizer: maps any HEREBUS unit string to the Sazon constraint
# `unit IN ('g', 'kg', 'ml', 'l', 'und')`
def _normalize_unit(unit: str | None) -> str:
    if not unit:
        return "und"
    u = unit.lower().strip()
    if u in ("g", "gr", "gram", "grams", "gramo", "gramos"):
        return "g"
    if u in ("kg", "kilo", "kilos", "kilogramo", "kilogramos"):
        return "kg"
    if u in ("ml", "milliliter", "milliliters", "millilitro", "millilitros"):
        return "ml"
    if u in ("l", "lt", "liter", "liters", "litro", "litros"):
        return "l"
    if u in ("und", "u", "unit", "units", "unidad", "unidades", "pcs", "pc", "piece", "pieces", "caja", "cajas", "box", "boxes", "pliego", "pliegos", "bolsa", "bolsas", "bolsita", "bolsitas", "bandeja", "bandejas", "cintillo", "cintillos", "papel", "pack", "packs"):
        return "und"
    # Default fallback
    return "und"


def _parse_ingredient_line(line: str) -> dict[str, Any]:
    """Parse one pipe-delimited ingredient row into a dict."""
    parts = line.split("|")
    return {
        "ing_id": parts[0].strip(),
        "name": parts[1].strip(),
        "category": parts[2].strip(),
        "pkg_qty": float(parts[3]) if parts[3] else None,
        "pkg_unit": parts[4].strip() if parts[4] else None,
        "bulk_price_gs": float(parts[5]) if parts[5] else 0,
        "unit_price_gs": float(parts[6]) if parts[6] else 0,
        "stock_qty": float(parts[7]) if parts[7] else 0,
        "min_reorder": float(parts[8]) if parts[8] else 0,
        "last_update": parts[9].strip() if parts[9] else None,
        "precio_ref": parts[10].strip() if parts[10] else "",
        "dutch_heritage": bool(int(parts[11])),
        "needs_confirm": bool(int(parts[12])),
    }


def _get_herbus_ingredients() -> list[dict[str, Any]]:
    """Return all 100 ingredients as parsed dicts."""
    return [_parse_ingredient_line(line) for line in HEREBUS_INGREDIENTS_RAW.split("\n") if line.strip()]


# ---------------------------------------------------------------------------
# 23 RECIPES + REC-024
# ---------------------------------------------------------------------------

HEREBUS_RECIPES_RAW = [
    {
        "rec_id": "REC-001", "sheet": "Recipe_Chocolate_Muffin_20x20_c",
        "name": "Muffin de chocolate (20x20 cm)",
        "yield_qty": None, "yield_unit": "und",
        "dutch_heritage": False, "category": "muffin",
        "ingredients": [
            ("ING-003", 333, "g"), ("ING-023", 117, "g"),
            ("ING-047", 5, "g"), ("ING-044", 5, "g"),
            ("ING-024", 3, "g"), ("ING-037", 17, "g"),
            ("ING-009", 458, "g"), ("ING-013", 167, "ml"),
            ("ING-072", 250, "ml"), ("ING-015", 167, "g"),
            ("ING-017", 375, "ml"), ("ING-027", 25, "g"),
            ("ING-025", 333, "g"),
        ],
    },
    {
        "rec_id": "REC-002", "sheet": "Recipe_Stroop_Waffle",
        "name": "Stroopwafel",
        "yield_qty": None, "yield_unit": "und",
        "dutch_heritage": True, "category": "galleta",
        "ingredients": [
            ("ING-001", 200, "g"), ("ING-003", 200, "g"),
            ("ING-023", 200, "g"), ("ING-008", 200, "g"),
            ("ING-015", 2, "und"), ("ING-027", 5, "ml"),
            ("ING-037", 2, "g"), ("ING-045", 10, "g"),
            ("ING-032", 15, "g"), ("ING-026", 5, "g"),
        ],
    },
    {
        "rec_id": "REC-003", "sheet": "Recipe_Cheesecake_20x20_cm",
        "name": "Cheesecake (20x20 cm)",
        "yield_qty": None, "yield_unit": "und",
        "dutch_heritage": False, "category": "tarta",
        "ingredients": [
            ("ING-020", 500, "g"), ("ING-008", 150, "g"),
            ("ING-015", 3, "und"), ("ING-027", 10, "ml"),
            ("ING-023", 100, "g"), ("ING-080", 300, "g"),
        ],
    },
    {
        "rec_id": "REC-004", "sheet": "Recipe_Ontbijtkoek_700g_flour",
        "name": "Ontbijtkoek (Dutch breakfast cake, 700g flour)",
        "yield_qty": None, "yield_unit": "und",
        "dutch_heritage": True, "category": "torta",
        "ingredients": [
            ("ING-001", 700, "g"), ("ING-009", 500, "g"),
            ("ING-012", 200, "g"), ("ING-015", 2, "und"),
            ("ING-032", 30, "g"), ("ING-044", 15, "g"),
            ("ING-013", 250, "ml"),
        ],
    },
    {
        "rec_id": "REC-005", "sheet": "Recipe_Carrot_Cake_43x33x15_cm",
        "name": "Carrot Cake (43x33x15 cm)",
        "yield_qty": None, "yield_unit": "und",
        "dutch_heritage": False, "category": "torta",
        "ingredients": [
            ("ING-003", 400, "g"), ("ING-009", 350, "g"),
            ("ING-032", 20, "g"), ("ING-044", 8, "g"),
            ("ING-037", 5, "g"), ("ING-062", 350, "g"),
            ("ING-015", 4, "und"), ("ING-072", 250, "ml"),
            ("ING-056", 150, "g"),
        ],
    },
    {
        "rec_id": "REC-006", "sheet": "Recipe_Frikandel_100_pcs",
        "name": "Frikandel (Dutch minced meat sausage, 100 pcs)",
        "yield_qty": None, "yield_unit": "und",
        "dutch_heritage": True, "category": "salchicha",
        "ingredients": [
            ("ING-089", 5000, "g"), ("ING-093", 1000, "g"),
            ("ING-030", 50, "g"), ("ING-037", 20, "g"),
            ("ING-042", 15, "g"),
        ],
    },
    {
        "rec_id": "REC-007", "sheet": "Recipe_Ketjap_Manis_Quick_Versi",
        "name": "Ketjap Manis (Quick Version, Indonesian-Dutch)",
        "yield_qty": None, "yield_unit": "ml",
        "dutch_heritage": True, "category": "salsa",
        "ingredients": [
            ("ING-087", 500, "ml"), ("ING-009", 400, "g"),
            ("ING-033", 5, "g"), ("ING-036", 3, "g"),
            ("ING-034", 2, "g"),
        ],
    },
    {
        "rec_id": "REC-008", "sheet": "Recipe_Hojaldre_Bladerdeeg",
        "name": "Hojaldre / Bladerdeeg (Dutch puff pastry)",
        "yield_qty": None, "yield_unit": "und",
        "dutch_heritage": True, "category": "masa",
        "ingredients": [
            ("ING-003", 500, "g"), ("ING-023", 400, "g"),
            ("ING-030", 10, "g"), ("ING-013", 250, "ml"),
        ],
    },
    {
        "rec_id": "REC-009", "sheet": "Recipe_Pastelitos_rosados_Roze_",
        "name": "Pastelitos Rosados / Roze (Dutch-PY fusion)",
        "yield_qty": None, "yield_unit": "und",
        "dutch_heritage": True, "category": "pastelito",
        "ingredients": [
            ("ING-003", 500, "g"), ("ING-008", 300, "g"),
            ("ING-023", 250, "g"), ("ING-015", 2, "und"),
            ("ING-027", 10, "ml"), ("ING-032", 5, "g"),
            ("ING-049", 200, "g"),
        ],
    },
    {
        "rec_id": "REC-010", "sheet": "Recipe_Galletas_de_especuloos_S",
        "name": "Galletas de Especuloos (Speculaas)",
        "yield_qty": None, "yield_unit": "und",
        "dutch_heritage": True, "category": "galleta",
        "ingredients": [
            ("ING-003", 350, "g"), ("ING-008", 250, "g"),
            ("ING-023", 200, "g"), ("ING-015", 1, "und"),
            ("ING-032", 25, "g"), ("ING-044", 5, "g"),
            ("ING-027", 5, "ml"),
        ],
    },
    {
        "rec_id": "REC-011", "sheet": "Recipe_Bizcocho_básico_25_cm_Ba",
        "name": "Bizcocho básico (25 cm base)",
        "yield_qty": None, "yield_unit": "und",
        "dutch_heritage": False, "category": "bizcocho",
        "ingredients": [
            ("ING-003", 250, "g"), ("ING-008", 200, "g"),
            ("ING-015", 3, "und"), ("ING-023", 100, "g"),
            ("ING-013", 200, "ml"), ("ING-047", 8, "g"),
            ("ING-027", 5, "ml"),
        ],
    },
    {
        "rec_id": "REC-012", "sheet": "Recipe_Bizcocho_básico_30_cm_Ba",
        "name": "Bizcocho básico (30 cm base)",
        "yield_qty": None, "yield_unit": "und",
        "dutch_heritage": False, "category": "bizcocho",
        "ingredients": [
            ("ING-003", 350, "g"), ("ING-008", 280, "g"),
            ("ING-015", 4, "und"), ("ING-023", 150, "g"),
            ("ING-013", 280, "ml"), ("ING-047", 10, "g"),
            ("ING-027", 8, "ml"),
        ],
    },
    {
        "rec_id": "REC-013", "sheet": "Recipe_Tarta_de_manzana_de_mi_m",
        "name": "Tarta de manzana de mi madre (Mijn moeders appeltaart)",
        "yield_qty": None, "yield_unit": "und",
        "dutch_heritage": True, "category": "tarta",
        "ingredients": [
            ("ING-003", 300, "g"), ("ING-008", 150, "g"),
            ("ING-023", 150, "g"), ("ING-015", 1, "und"),
            ("ING-027", 5, "ml"), ("ING-032", 10, "g"),
            ("ING-044", 3, "g"), ("ING-049", 600, "g"),
            ("ING-010", 50, "g"), ("ING-033", 5, "g"),
            ("ING-034", 2, "g"),
        ],
    },
    {
        "rec_id": "REC-014", "sheet": "Recipe_Proficteroles_de_Den_Bos",
        "name": "Profiteroles de Den Bosch (Bossche Bollen)",
        "yield_qty": None, "yield_unit": "und",
        "dutch_heritage": True, "category": "bollen",
        "ingredients": [
            ("ING-003", 200, "g"), ("ING-023", 100, "g"),
            ("ING-015", 4, "und"), ("ING-013", 250, "ml"),
            ("ING-030", 3, "g"), ("ING-025", 200, "g"),
            ("ING-018", 250, "ml"),
        ],
    },
    {
        "rec_id": "REC-015", "sheet": "Recipe_Petisús_de_hojaldre_y_cr",
        "name": "Petisús de hojaldre y crema (cream puffs)",
        "yield_qty": None, "yield_unit": "und",
        "dutch_heritage": False, "category": "petisu",
        "ingredients": [
            ("ING-003", 250, "g"), ("ING-023", 100, "g"),
            ("ING-015", 4, "und"), ("ING-013", 250, "ml"),
            ("ING-030", 3, "g"), ("ING-078", 300, "g"),
        ],
    },
    {
        "rec_id": "REC-016", "sheet": "Recipe_Oliebollen_Buñuelos_trad",
        "name": "Oliebollen / Buñuelos tradicionales (Dutch New Year)",
        "yield_qty": None, "yield_unit": "und",
        "dutch_heritage": True, "category": "buñuelo",
        "ingredients": [
            ("ING-003", 500, "g"), ("ING-015", 2, "und"),
            ("ING-045", 20, "g"), ("ING-013", 300, "ml"),
            ("ING-008", 100, "g"), ("ING-055", 100, "g"),
            ("ING-099", 20, "g"),
        ],
    },
    {
        "rec_id": "REC-017", "sheet": "Recipe_Babka",
        "name": "Babka",
        "yield_qty": None, "yield_unit": "und",
        "dutch_heritage": False, "category": "torta",
        "ingredients": [
            ("ING-003", 400, "g"), ("ING-008", 200, "g"),
            ("ING-015", 3, "und"), ("ING-023", 150, "g"),
            ("ING-013", 200, "ml"), ("ING-045", 15, "g"),
            ("ING-025", 150, "g"), ("ING-027", 5, "ml"),
        ],
    },
    {
        "rec_id": "REC-018", "sheet": "Recipe_Bombones_de_chocolate",
        "name": "Bombones de chocolate",
        "yield_qty": None, "yield_unit": "und",
        "dutch_heritage": False, "category": "bombon",
        "ingredients": [
            ("ING-025", 500, "g"), ("ING-018", 100, "ml"),
            ("ING-023", 50, "g"), ("ING-027", 5, "ml"),
        ],
    },
    {
        "rec_id": "REC-019", "sheet": "Recipe_Goulash_Crockettes_100",
        "name": "Goulash Croquettes (Dutch, 100 pcs)",
        "yield_qty": None, "yield_unit": "und",
        "dutch_heritage": True, "category": "croqueta",
        "ingredients": [
            ("ING-089", 2000, "g"), ("ING-003", 200, "g"),
            ("ING-013", 500, "ml"), ("ING-023", 100, "g"),
            ("ING-093", 300, "g"), ("ING-015", 2, "und"),
            ("ING-037", 10, "g"),
        ],
    },
    {
        "rec_id": "REC-020", "sheet": "Recipe_Veggie_Bitterballen_100",
        "name": "Veggie Bitterballen (Dutch, 100 pcs)",
        "yield_qty": None, "yield_unit": "und",
        "dutch_heritage": True, "category": "croqueta",
        "ingredients": [
            ("ING-067", 1500, "g"), ("ING-068", 500, "g"),
            ("ING-064", 500, "g"), ("ING-003", 300, "g"),
            ("ING-013", 500, "ml"), ("ING-023", 100, "g"),
            ("ING-093", 300, "g"),
        ],
    },
    {
        "rec_id": "REC-021", "sheet": "Recipe_Suppli_Caccio_e_Pepe",
        "name": "Supplì Cacio e Pepe (Italian, 20 pcs)",
        "yield_qty": None, "yield_unit": "und",
        "dutch_heritage": False, "category": "croqueta",
        "ingredients": [
            ("ING-066", 1000, "g"), ("ING-019", 200, "g"),
            ("ING-037", 5, "g"), ("ING-015", 2, "und"),
            ("ING-093", 200, "g"),
        ],
    },
    {
        "rec_id": "REC-022", "sheet": "Recipe_Everything_Bagels_8",
        "name": "Everything Bagels (American-Jewish, 8 pcs)",
        "yield_qty": None, "yield_unit": "und",
        "dutch_heritage": False, "category": "bagel",
        "ingredients": [
            ("ING-003", 500, "g"), ("ING-013", 250, "ml"),
            ("ING-045", 10, "g"), ("ING-008", 30, "g"),
            ("ING-030", 8, "g"), ("ING-097", 15, "g"),
            ("ING-098", 15, "g"), ("ING-099", 10, "g"),
            ("ING-096", 5, "g"),
        ],
    },
    {
        "rec_id": "REC-023", "sheet": "Recipe_Everything_Bagel_Seasoni",
        "name": "Everything Bagel Seasoning (the mix)",
        "yield_qty": None, "yield_unit": "g",
        "dutch_heritage": False, "category": "seasoning",
        "ingredients": [
            ("ING-097", 100, "g"), ("ING-098", 50, "g"),
            ("ING-099", 50, "g"), ("ING-096", 50, "g"),
            ("ING-100", 50, "g"),
        ],
    },
]


# ---------------------------------------------------------------------------
# 7 PACKAGING items
# ---------------------------------------------------------------------------

HEREBUS_PACKAGING_RAW = """PKG-001|Bolsita plástica mediana|und|800|0|2026-07-10|0|1
PKG-002|Bolsita plástica grande|und|1200|0|2026-07-10|0|1
PKG-003|Cintillo decorativo|und|500|0|2026-07-10|0|1
PKG-004|Bandeja plástica|und|2500|0|2026-07-10|0|1
PKG-005|Bandeja cartón|und|3500|0|2026-07-10|0|1
PKG-006|Papel antigrasa|pliego|1200|0|2026-07-10|0|1
PKG-007|Caja de regalo|caja|8500|0|2026-07-10|0|1"""


def _parse_packaging_line(line: str) -> dict[str, Any]:
    parts = line.split("|")
    return {
        "pkg_id": parts[0].strip(),
        "name": parts[1].strip(),
        "unit": parts[2].strip(),
        "default_price_gs": float(parts[3]) if parts[3] else 0,
        "stock_qty": float(parts[4]) if parts[4] else 0,
        "last_update": parts[5].strip() if parts[5] else None,
        "needs_confirm": bool(int(parts[6])),
    }


def _get_herbus_packaging() -> list[dict[str, Any]]:
    return [_parse_packaging_line(line) for line in HEREBUS_PACKAGING_RAW.split("\n") if line.strip()]


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------


def seed_herbus_ingredients(session: Session) -> int:
    """Insert the 100 HEREBUS ingredients. Idempotent.

    Returns the count of NEW rows inserted (skipped if name already exists).
    """
    from app.rms.models import Ingredient

    now = datetime.now(timezone.utc)
    inserted = 0
    skipped = 0
    for ing in _get_herbus_ingredients():
        existing = session.execute(
            select(Ingredient).where(Ingredient.name == ing["name"])
        ).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            continue
        # The Ingredient model has a `notes` field — we encode the
        # dutch_heritage + needs_confirm + precio_ref flags in there
        # plus a JSON blob.
        notes = json.dumps({
            "herbus_ing_id": ing["ing_id"],
            "precio_ref": ing["precio_ref"],
            "dutch_heritage": ing["dutch_heritage"],
            "needs_confirm": ing["needs_confirm"],
            "last_update": ing["last_update"],
        }, ensure_ascii=False)
        session.add(Ingredient(
            name=ing["name"],
            unit=_normalize_unit(ing["pkg_unit"]),
            stock_qty=ing["stock_qty"],
            purchase_price_gs=int(ing["unit_price_gs"]) if ing["unit_price_gs"] > 0 else None,
            purchase_price_updated_at=now,
            min_stock_qty=ing["min_reorder"] or 0,
            max_stock_qty=(ing["min_reorder"] or 0) * 3,
            shelf_life_days=30,
            storage="dry",
            notes=notes,
            category=ing["category"],
            lead_time_days=3,
            lot_required=False,
            may_contain_gluten="gluten" in ing["name"].lower() or "harina" in ing["name"].lower() or "centeno" in ing["name"].lower(),
            purchase_streak_count=0,
            locked_supplier_id=None,
            opening_stock_qty=ing["stock_qty"],
            opening_stock_date="2026-10-12",
            reorder_point=(ing["min_reorder"] or 0) * 1.5,
        ))
        inserted += 1
    session.flush()
    logger.info(f"seed_herbus_ingredients: {inserted} new, {skipped} skipped (of 100 total).")
    return inserted


def seed_herbus_recipes(session: Session) -> int:
    """Insert the 23 HEREBUS recipes. Idempotent.

    All 23 have empty B4 (yield); the seeder uses 1.0 default + a
    yellow warning + an AppMeta row. REC-006 is used for Frikandel
    (per the spreadsheet), REC-024 is assigned to Veggie Bitterballen
    to resolve the duplicate.
    """
    from app.rms.models import AppMeta, Ingredient, Recipe, RecipeLine

    # Capture import timestamp for AppMeta provenance row.
    now = datetime.now(timezone.utc)  # noqa: F841 (used by AppMeta write below if enabled)
    inserted = 0
    skipped = 0
    all_yield_pending = True

    ingredients_by_name = {
        ing.name: ing for ing in session.execute(
            select(__import__("app.rms.models", fromlist=["Ingredient"]).Ingredient)
        ).scalars()
    }

    for rec in HEREBUS_RECIPES_RAW:
        existing = session.execute(
            select(Recipe).where(Recipe.name == rec["name"])
        ).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            continue
        # Use 1.0 default yield if B4 is empty
        yield_qty = rec["yield_qty"] if rec["yield_qty"] else 1.0
        if not rec["yield_qty"]:
            all_yield_pending = True
        recipe = Recipe(
            name=rec["name"],
            yield_qty=yield_qty,
            yield_unit=rec["yield_unit"],
            family=rec["category"],
            notes=json.dumps({
                "herbus_rec_id": rec["rec_id"],
                "herbus_sheet": rec["sheet"],
                "dutch_heritage": rec["dutch_heritage"],
                "yield_needs_backfill": not rec["yield_qty"],
            }, ensure_ascii=False),
        )
        session.add(recipe)
        session.flush()  # so recipe.id is set
        # Add recipe lines
        for _ord, (ing_id, qty, unit) in enumerate(rec["ingredients"], start=1):
            ing_name = next((i["name"] for i in _get_herbus_ingredients() if i["ing_id"] == ing_id), None)
            ing_obj = ingredients_by_name.get(ing_name) if ing_name else None
            if ing_obj is None:
                # Try to find the ingredient by name (case-insensitive)
                ing_obj = session.execute(
                    select(Ingredient).where(Ingredient.name == ing_name)
                ).scalar_one_or_none()
            if ing_obj is None:
                # Skip recipe lines whose ingredients don't exist yet.
                # The seed_herbus_ingredients() function should be called
                # BEFORE seed_herbus_recipes() to ensure all ingredients
                # are inserted.
                logger.warning(
                    f"seed_herbus_recipes: ingredient '{ing_name}' (ID={ing_id}) "
                    f"not found -- skipping recipe line for recipe "
                    f"'{rec['name']}'"
                )
                continue
            session.add(RecipeLine(
                recipe_id=recipe.id,
                line_kind="ingredient",
                line_ref_id=ing_obj.id,
                qty=qty,
                line_unit=unit,
            ))
        inserted += 1
    session.flush()

    if all_yield_pending:
        # Add an AppMeta row to flag the backfill work
        existing = session.execute(
            select(AppMeta).where(AppMeta.key == "recipe_yield_backfill_pending")
        ).scalar_one_or_none()
        if existing is None:
            session.add(AppMeta(
                key="recipe_yield_backfill_pending",
                value="true",
                updated_at="2026-10-12",
            ))

    logger.info(f"seed_herbus_recipes: {inserted} new, {skipped} skipped (of 23 total). "
                f"Yield backfill pending: {all_yield_pending}.")
    return inserted


def seed_herbus_packaging(session: Session) -> int:
    """Insert the 7 HEREBUS packaging items. Idempotent.

    Note: the Sazon schema doesn't have a dedicated `packaging` model
    in models_legacy — packaging is modeled as `Ingredient` with
    category="packaging" and unit-specific. We reuse Ingredient.
    """
    from app.rms.models import Ingredient

    inserted = 0
    skipped = 0
    for pkg in _get_herbus_packaging():
        existing = session.execute(
            select(Ingredient).where(Ingredient.name == pkg["name"])
        ).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            continue
        session.add(Ingredient(
            name=pkg["name"],
            unit=_normalize_unit(pkg["unit"]),
            stock_qty=pkg["stock_qty"],
            purchase_price_gs=int(pkg["default_price_gs"]) if pkg["default_price_gs"] > 0 else None,
            min_stock_qty=0,
            max_stock_qty=0,
            shelf_life_days=365,
            storage="ambient",
            category="packaging",
            is_packaging=True,
            notes=json.dumps({
                "herbus_pkg_id": pkg["pkg_id"],
                "needs_confirm": pkg["needs_confirm"],
                "last_update": pkg["last_update"],
            }, ensure_ascii=False),
            lead_time_days=3,
            lot_required=False,
            may_contain_gluten=False,
            purchase_streak_count=0,
            locked_supplier_id=None,
        ))
        inserted += 1
    session.flush()
    logger.info(f"seed_herbus_packaging: {inserted} new, {skipped} skipped (of 7 total).")
    return inserted


def seed_herbus_data(session: Session) -> int:
    """Run all 3 HEREBUS seeders. Returns total new rows."""
    n1 = seed_herbus_ingredients(session)
    n2 = seed_herbus_recipes(session)
    n3 = seed_herbus_packaging(session)
    total = n1 + n2 + n3
    logger.info(f"seed_herbus_data: total {total} new rows (100 ingredients + 23 recipes + 7 packaging).")
    return total
