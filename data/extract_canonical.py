"""HEREBUS workbook → JSON canonical data for saskia-app seed reconciliation.

Outputs data/herebus_seed_canonical.json.
"""
import json
import re
import sys
from datetime import date, datetime
from openpyxl import load_workbook

WB_PATH = "/opt/data/profiles/ivan/cache/scratch/saskia-workbook-reconcile/data/herebus.xlsx"
OUT_PATH = "/opt/data/profiles/ivan/cache/scratch/saskia-workbook-reconcile/data/herebus_seed_canonical.json"


def _s(v):
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v)
    return str(v).strip()


wb = load_workbook(WB_PATH, data_only=True)

result = {
    "workbook_sheets": wb.sheetnames,
    "inventory": [],
    "packaging": [],
    "recipes": [],
    "production_planner": [],
    "waste_tracker": [],
    "dashboard_pl": [],
}

# ───── Inventory ─────
sh = wb["Inventory"]
# Real schema from row 4:
#   1=ID, 2=Nombre, 3=Grupo, 4=PkgQty, 5=PkgUnit, 6=BulkPrice ₲,
#   7=UnitPrice ₲, 8=StockQty, 9=MinReorder, 10=LastUpdate, 11=Precio ref, 12=Costo stock estimado
inv = []
for r in range(5, sh.max_row + 1):
    ing_id = _s(sh.cell(r, 1).value)
    name = _s(sh.cell(r, 2).value)
    if not ing_id and not name:
        continue
    grupo = _s(sh.cell(r, 3).value)
    pkg_qty = sh.cell(r, 4).value
    pkg_unit = _s(sh.cell(r, 5).value)
    bulk_price = sh.cell(r, 6).value
    unit_price = sh.cell(r, 7).value
    stock_qty = sh.cell(r, 8).value
    min_reorder = sh.cell(r, 9).value
    last_update = sh.cell(r, 10).value
    if isinstance(last_update, (date, datetime)):
        last_update = last_update.strftime("%Y-%m-%d")
    elif last_update is None:
        last_update = ""
    else:
        last_update = _s(last_update)
    notes = _s(sh.cell(r, 11).value)
    inv.append({
        "ing_id": ing_id, "name": name, "grupo": grupo,
        "pkg_qty": pkg_qty, "pkg_unit": pkg_unit,
        "bulk_price": bulk_price, "unit_price": unit_price,
        "stock_qty": stock_qty, "min_reorder": min_reorder,
        "last_update": last_update, "notes": notes,
    })

result["inventory"] = inv
print(f"Inventory rows: {len(inv)}")

# ───── Packaging ─────
sh = wb["Packaging"]
# Real schema from row 4 (id=ID col1, name col2, desc col3, categoria col4, pkgqty col5, pkgunit col6, bulkprice col7)
pkg = []
for r in range(5, sh.max_row + 1):
    pkg_id = _s(sh.cell(r, 1).value)
    name = _s(sh.cell(r, 2).value)
    if not pkg_id and not name:
        continue
    desc = _s(sh.cell(r, 3).value)
    categoria = _s(sh.cell(r, 4).value)
    pkg_qty = sh.cell(r, 5).value
    pkg_unit = _s(sh.cell(r, 6).value)
    bulk_price = sh.cell(r, 7).value
    pkg.append({
        "pkg_id": pkg_id, "name": name, "desc": desc, "categoria": categoria,
        "pkg_qty": pkg_qty, "pkg_unit": pkg_unit, "bulk_price": bulk_price,
    })
result["packaging"] = pkg
print(f"Packaging rows: {len(pkg)}")

# ───── Each Recipe_* ─────
def parse_recipe(sh, sheet_name):
    """Two layouts:
    Sweet recipes (rows 1-7):
      R1: title  R3: Receta ID | REC-XXX | Receta: | <name>
      R4: Rinde (un.) | <qty or empty> | Unidad rinde: | <unit>
      R5: Notas...
      R8: header Orden | ID | Ingrediente | Cantidad | Unidad | Precio unit ₲
      R9-22: 14 ingredients
      R25-28: Packaging
      R30: header Margenes
      R31:  Canal | Descripción | Margen %
      R32/33/34: WHOLESALE / RETAIL / EVENTUAL  (Margen in col 5!)
      R36-42: Prices
      R44-53: Instructions
    Savory recipes (rows 3-...):
      R3: Receta ID ...
      R5: Notas
      R7: INGREDIENTES (hasta 20)
      R8: header Orden | ID | Ingredient...
      R9-30: ~22 lines possible
      R31: TOTAL INGREDIENTES
      R33: PACKAGING
      R36: TOTAL PACKAGING
      R38: Margenes header
      R40/41/42: WHOLESALE/RETAIL/EVENTUAL
    """
    data = {"sheet": sheet_name}
    rec_id, rec_name = "", ""
    yield_qty, yield_unit, yield_notes = None, "", ""
    # Sweet layout: ID=row 3 col 2, name=row 3 col 4
    if "ID" not in _s(sh.cell(3, 1).value).upper() and "RECETA" in _s(sh.cell(3, 1).value).upper():
        # Sweet: row 3 has label "Receta ID:" in col 1, ID in col 2, "Receta:" in col 3, name in col 4
        rec_id = _s(sh.cell(3, 2).value)
        rec_name = _s(sh.cell(3, 4).value)
        yield_qty = sh.cell(4, 2).value
        yield_unit = _s(sh.cell(4, 4).value)
        yield_notes = _s(sh.cell(5, 2).value)
        ing_header_row = 8
    else:
        # Savory: row 3
        rec_id = _s(sh.cell(3, 2).value)
        rec_name = _s(sh.cell(3, 4).value)
        yield_qty = sh.cell(4, 2).value
        yield_unit = _s(sh.cell(4, 4).value)
        yield_notes = _s(sh.cell(5, 2).value)
        ing_header_row = 8

    data.update({
        "rec_id": rec_id, "rec_name": rec_name,
        "yield_qty": yield_qty, "yield_unit": yield_unit,
        "yield_notes": yield_notes,
    })

    ings = []
    for r in range(ing_header_row + 1, ing_header_row + 25):
        ing_ref = _s(sh.cell(r, 2).value)
        name = _s(sh.cell(r, 3).value)
        if not ing_ref or ing_ref.upper() in ("ING", "INGREDIENTE", "INGREDIENTES"):
            continue
        if not (ing_ref.upper().startswith("ING-") or ing_ref.isdigit()):
            continue
        qty = sh.cell(r, 4).value
        unit = _s(sh.cell(r, 5).value)
        try:
            ings.append({
                "ing_ref": ing_ref, "name": name,
                "qty": qty, "unit": unit,
            })
        except Exception:
            pass
    data["ingredients"] = ings

    # Margins are at fixed rows: 32/33/34 sweet, 40/41/42 savory.
    # The label is at column 3 ("Canal" col), value at column 5.
    margins = {}
    for r in range(30, 45):
        canal = _s(sh.cell(r, 3).value).upper()
        for label in ("WHOLESALE", "RETAIL", "EVENTUAL"):
            if canal.startswith(label):
                margins[label] = sh.cell(r, 5).value
                break
    data["margins"] = margins

    # Packaging (where it's filled - only savory for now)
    packaging = []
    for r in range(20, 35):
        v = _s(sh.cell(r, 1).value).upper()
        if v.startswith("PACKAGING") and r < 33:
            for rr in range(r + 1, r + 4):
                name = _s(sh.cell(rr, 4).value)
                qty = sh.cell(rr, 5).value
                unit_price = sh.cell(rr, 6).value
                if name and qty:
                    packaging.append({"name": name, "qty": qty, "unit_price": unit_price})
            break
    # Sweet-recipe packaging: row 25 col 3 / col 4 etc
    if not packaging:
        for r in range(24, 29):
            v = _s(sh.cell(r, 1).value).upper()
            if v.startswith("PACKAGING"):
                for rr in range(r + 1, r + 4):
                    name = _s(sh.cell(rr, 3).value)
                    qty = sh.cell(rr, 4).value
                    unit_price = sh.cell(rr, 5).value
                    if name and qty:
                        packaging.append({"name": name, "qty": qty, "unit_price": unit_price})
                break
    data["packaging"] = packaging

    return data


recipe_sheets = sorted([s for s in wb.sheetnames if s.lower().startswith("recipe_")])
for sheet in recipe_sheets:
    sh = wb[sheet]
    rec = parse_recipe(sh, sheet)
    if rec.get("rec_id") or rec.get("rec_name") or rec.get("ingredients"):
        result["recipes"].append(rec)

print(f"Recipe sheets parsed: {len(result['recipes'])}")

with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2, default=str)

print(f"Wrote {OUT_PATH}")
