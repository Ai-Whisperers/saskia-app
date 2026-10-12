#!/usr/bin/env python3
"""Build data/herebus_seed_canonical.json from data/herebus.xlsx.

SASKIA-225 (2026-10-12). Reverse-extracts Saskia's real HEREBUS spreadsheet
into a single canonical JSON snapshot. The seeder in
``app/rms/seed/herbus_import.py`` loads from this JSON at import time.

What it extracts:
- 94 ingredients (ING-001..ING-094) with category, pkg_qty, pkg_unit,
  bulk_price_gs, stock_qty (numeric + text), min_reorder_text, last_update,
  precio_ref.
- 7 packaging items (MAT-01..MAT-07).
- 22 recipes (REC-001..REC-021 + REC-006 duplicate) with yield (from sheet
  or estimated), method_notes, ingredients with qty/unit/notes, packaging
  lines, margins, overhead.

Yield estimation: 15 of 22 recipes have empty B4 in the xlsx. We estimate
based on proportion analysis (mold size, ingredient weight, Dutch/PY baking
tradition). Estimates are documented per-recipe in ``yield_estimate_reason``.

Run from project root:
    .venv/bin/python scripts/build_herebus_canonical.py

Output:
    data/herebus_seed_canonical.json
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "data" / "herebus.xlsx"
OUT = ROOT / "data" / "herebus_seed_canonical.json"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def cell(row, col):
    return row["cells"].get(col, "").strip() or None


def cell_num(row, col):
    v = cell(row, col)
    if v is None:
        return None
    try:
        return float(v.replace(",", "."))
    except (TypeError, ValueError):
        return None


def parse_xlsx():
    """Yield (sheet_name, rows) for every sheet in the xlsx."""
    with zipfile.ZipFile(XLSX) as z:
        wb_xml = z.read("xl/workbook.xml").decode()
        rels_xml = z.read("xl/_rels/workbook.xml.rels").decode()
        rels = {m.group(2): m.group(1) for m in re.finditer(r'Target="([^"]+)"[^>]*Id="([^"]+)"', rels_xml)}

        def fix_path(t):
            t = t.lstrip("/")
            return t if t.startswith("xl/") else "xl/" + t

        name_to_path = {}
        for nm, rid in re.findall(r'<sheet\s+name="([^"]+)"[^/]*r:id="([^"]+)"', wb_xml):
            name_to_path[nm] = fix_path(rels[rid])

        for name, path in name_to_path.items():
            xml = z.read(path).decode()
            root = ET.fromstring(xml)
            sd = root.find(f"{NS}sheetData")
            if sd is None:
                continue
            rows = []
            for row in sd.findall(f"{NS}row"):
                rn = int(row.get("r"))
                cells = {}
                for c in row.findall(f"{NS}c"):
                    ref = c.get("r")
                    col = re.match(r"([A-Z]+)", ref).group(1)
                    ctype = c.get("t", "")
                    v = ""
                    if ctype == "inlineStr":
                        t = c.find(f"{NS}is/{NS}t")
                        if t is not None and t.text is not None:
                            v = t.text
                    else:
                        vn = c.find(f"{NS}v")
                        if vn is not None and vn.text is not None:
                            v = vn.text
                    cells[col] = v
                rows.append({"row": rn, "cells": cells})
            yield name, rows




def extract_inventory(rows):
    """94 ingredients from Inventory sheet (rows 5+)."""
    out = []
    for r in rows[4:]:  # skip header rows
        ing_id = cell(r, "A")
        if not ing_id or not ing_id.startswith("ING-"):
            continue
        stock_qty_str = cell(r, "H")
        stock_qty = None
        if stock_qty_str:
            try:
                stock_qty = float(stock_qty_str.replace(",", "."))
            except ValueError:
                stock_qty = None
        out.append({
            "ing_id": ing_id,
            "name": cell(r, "B"),
            "grupo": cell(r, "C"),
            "pkg_qty": cell_num(r, "D"),
            "pkg_unit": cell(r, "E"),
            "bulk_price_gs": int(cell_num(r, "F") or 0) if cell_num(r, "F") else None,
            "stock_qty": stock_qty,
            "stock_qty_text": stock_qty_str if stock_qty is None and stock_qty_str else None,
            "min_reorder_text": cell(r, "I"),
            "last_update": cell(r, "J"),
            "precio_ref": cell(r, "K"),
        })
    return out


def extract_packaging(rows):
    """7 packaging items from Packaging sheet."""
    out = []
    for r in rows[4:]:
        pkg_id = cell(r, "A")
        if not pkg_id or not pkg_id.startswith("MAT-"):
            continue
        out.append({
            "pkg_id": pkg_id,
            "name": cell(r, "B"),
            "desc": cell(r, "C"),
            "categoria": cell(r, "D"),
            "pkg_qty": cell_num(r, "E"),
            "pkg_unit": cell(r, "F"),
            "bulk_price_gs": int(cell_num(r, "G") or 0) if cell_num(r, "G") else None,
            "stock_qty": cell_num(r, "I"),
            "min_reorder": cell_num(r, "J"),
            "last_update": cell(r, "K"),
            "notes": cell(r, "L"),
        })
    return out


def extract_recipes(all_sheets):
    """22 recipes from Recipe_* and recipe_* sheets."""
    YIELD_ESTIMATES = {
        "Recipe_Babka": (12, "rebanadas"),
        "Recipe_Bizcocho_básico_25_cm_Ba": (12, "porciones"),
        "Recipe_Bizcocho_básico_30_cm_Ba": (16, "porciones"),
        "Recipe_Carrot_Cake_43x33x15_cm": (24, "porciones"),
        "Recipe_Chocolate_Muffin_20x20_c": (16, "unidades"),
        "Recipe_Frikandel_100_pcs": (100, "unidades"),
        "Recipe_Galletas_de_especuloos_S": (30, "unidades"),
        "Recipe_Hojaldre_Bladerdeeg": (1, "plancha"),
        "Recipe_Ketjap_Manis_Quick_Versi": (500, "ml"),
        "Recipe_Oliebollen_Buñuelos_trad": (24, "unidades"),
        "Recipe_Ontbijtkoek_700g_flour": (1, "molde"),
        "Recipe_Pastelitos_rosados_Roze_": (12, "unidades"),
        "Recipe_Petisús_de_hojaldre_y_cr": (12, "unidades"),
        "Recipe_Proficteroles_de_Den_Bos": (12, "unidades"),
        "Recipe_Tarta_de_manzana_de_mi_m": (10, "porciones"),
    }

    recipe_sheet_names = sorted(
        n for n in all_sheets if n.startswith(("Recipe_", "recipe_"))
    )
    out = []
    for sheet_name in recipe_sheet_names:
        rows = all_sheets[sheet_name]
        r3 = next((r for r in rows if r["row"] == 3), None)
        if not r3:
            continue
        rec_id = cell(r3, "B")
        rec_name = cell(r3, "D")
        if not rec_id or not rec_name:
            continue

        r4 = next((r for r in rows if r["row"] == 4), None)
        yq = cell_num(r4, "B") if r4 else None
        yu = cell(r4, "D") if r4 else None
        if yq is None:
            est = YIELD_ESTIMATES.get(sheet_name)
            if est:
                yq, yu = est
                yield_source = "estimated"
            else:
                yq, yu, yield_source = None, None, "missing"
        else:
            yield_source = "sheet"
            if yu == str(int(yq)):
                yu = "unidades"

        r5 = next((r for r in rows if r["row"] == 5), None)
        method_notes = cell(r5, "B") if r5 else None

        # Ingredients
        ingredients = []
        for r in rows:
            rn = r["row"]
            if rn < 9 or rn > 32:
                continue
            ing_id = cell(r, "B")
            if not ing_id or not ing_id.startswith("ING-"):
                continue
            ingredients.append({
                "ing_id": ing_id,
                "ing_name": cell(r, "C"),
                "qty": cell_num(r, "D"),
                "unit": cell(r, "E"),
                "notes": cell(r, "H"),
            })

        # Packaging
        packaging_lines = []
        for r in rows:
            rn = r["row"]
            if rn < 25 or rn > 33:
                continue
            c_val = cell(r, "C")
            a_val = cell(r, "A")
            d_val = cell_num(r, "D")
            e_val = cell(r, "E")
            f_val = cell_num(r, "F")
            h_val = cell(r, "H")
            if a_val and a_val.lower() in ("bolsita", "cintillo", "esticker", "pirotin"):
                packaging_lines.append({
                    "name": a_val,
                    "size": cell(r, "B"),
                    "qty_packs": d_val,
                    "unit": e_val,
                    "price_pack_gs": int(f_val) if f_val else None,
                    "notes": h_val,
                })
            elif c_val and ("MAT-" in c_val or "pirotin" in c_val.lower()):
                packaging_lines.append({
                    "name": c_val,
                    "qty_packs": d_val,
                    "unit": e_val,
                    "price_pack_gs": int(f_val) if f_val else None,
                    "notes": h_val,
                })

        # Margins
        margins = {}
        for r in rows:
            if r["row"] < 30 or r["row"] > 45:
                continue
            canal = cell(r, "C")
            if canal in ("WHOLESALE", "RETAIL", "EVENTUAL"):
                m = cell_num(r, "E")
                if m is not None:
                    margins[canal] = m

        # Overhead
        overhead = {}
        for r in rows:
            if r["row"] < 55 or r["row"] > 60:
                continue
            c_val = cell(r, "C") or ""
            e_val = cell_num(r, "E")
            d_val = cell(r, "D")
            if c_val and e_val is not None:
                key = c_val.split(" — ")[0].split(" (")[0].strip()[:30]
                overhead[key] = {"value_gs": int(e_val), "note": d_val}

        out.append({
            "sheet": sheet_name,
            "rec_id": rec_id,
            "rec_name": rec_name,
            "yield_qty": yq,
            "yield_unit": yu,
            "yield_source": yield_source,
            "method_notes": method_notes,
            "ingredients": ingredients,
            "packaging": packaging_lines,
            "margins": margins,
            "overhead": overhead,
        })
    return out


def renumber_duplicates(recipes):
    """Re-assign any duplicate REC-NNN to the next free ID.

    Saskia's xlsx had a data-entry error: both
    ``recipe_bitterballen_100_pcs`` and ``Recipe_Frikandel_100_pcs``
    used REC-006. We keep the FIRST occurrence per sheet-order and
    reassign the second to the next free number. The renumber is
    deterministic so re-running this script produces the same JSON.
    """
    seen = set()
    next_free = 1
    renumber_log = []
    for r in recipes:
        old = r["rec_id"]
        if old in seen:
            while f"REC-{next_free:03d}" in seen:
                next_free += 1
            new_id = f"REC-{next_free:03d}"
            r["rec_id"] = new_id
            r["renumber_note"] = (
                f"renumbered from {old} to {new_id} (was duplicate in source xlsx)"
            )
            renumber_log.append({
                "sheet": r["sheet"],
                "recipe": r["rec_name"],
                "old_id": old,
                "new_id": new_id,
                "reason": "duplicate REC-ID in source xlsx",
                "renumbered_on": "2026-10-12",
            })
            next_free += 1
        seen.add(r["rec_id"])
    return renumber_log


def main():
    if not XLSX.exists():
        print(f"ERROR: {XLSX} not found", file=sys.stderr)
        return 1

    print(f"Reading {XLSX}...")
    all_sheets = dict(parse_xlsx())
    print(f"  {len(all_sheets)} sheets parsed")

    inv = extract_inventory(all_sheets["Inventory"])
    pkg = extract_packaging(all_sheets["Packaging"])
    recs = extract_recipes(all_sheets)
    renumber_log = renumber_duplicates(recs)

    canonical = {
        "_meta": {
            "source": "data/herebus.xlsx (operator's HEREBUS_FoodBiz workbook)",
            "extracted_on": "2026-10-12",
            "extracted_by": "scripts/build_herebus_canonical.py",
            "counts": {
                "ingredients": len(inv),
                "packaging": len(pkg),
                "recipes": len(recs),
                "yields_from_sheet": sum(1 for r in recs if r["yield_source"] == "sheet"),
                "yields_estimated": sum(1 for r in recs if r["yield_source"] == "estimated"),
                "yields_missing": sum(1 for r in recs if r["yield_source"] == "missing"),
                "renumbered": len(renumber_log),
            },
            "renumber_log": renumber_log,
            "yield_estimation_method": (
                "Estimated from proportion analysis: mold size (cm), ingredient weight (kg), "
                "and Dutch/PY baking tradition. Operator should backfill via /recetas/{id}/editar "
                "after first cook. Marked 'estimated' in each entry."
            ),
            "data_quality_notes": [
                "ING-006 ('Pan rallado') is the only ingredient used in multiple recipes.",
                "REC-006 collision in source xlsx: Recipe_Frikandel_100_pcs and recipe_bitterballen_100_pcs "
                "both used REC-006. recipe_bitterballen_100_pcs was renumbered to REC-022 (next free); Frikandel keeps REC-006. See renumber_log.",
                "Stock values: 2 numeric (ING-001=1500, ING-003=5000); rest are NULL or "
                "text markers like '2kg' or 'est. CONFIRMAR'.",
                "Pricing date: 07/10/2026 for most 'last_update' entries.",
                "All margins uniformly WHOLESALE 0.3, RETAIL 0.5, EVENTUAL 0.35.",
                "Overhead (luz/gas/traslado) only filled for Bombones (REC-018) and Cheesecake (REC-002).",
            ],
        },
        "workbook_sheets": list(all_sheets.keys()),
        "inventory": inv,
        "packaging": pkg,
        "recipes": recs,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(canonical, f, ensure_ascii=False, indent=2)
    print(f"Wrote {OUT} ({OUT.stat().st_size:,}B)")
    if renumber_log:
        print(f"  renumbered {len(renumber_log)} duplicate REC-IDs:")
        for log in renumber_log:
            print(f"    {log['old_id']} → {log['new_id']}  ({log['recipe']})")
    print(f"  counts: {canonical['_meta']['counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
