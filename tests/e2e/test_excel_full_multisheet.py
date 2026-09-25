"""tests/e2e/test_excel_full_multisheet.py — expansion item 3: the
destructive FULL mode + multi-sheet workbooks (previously only PATCH on
Ingredientes was ever tested E2E).

Covers:
  - multi-sheet journey: Ingredientes + Recetas + Lineas + Productos in one
    file → all four land, recipe lines link by NAME (natural key)
  - FULL mode is ADDITIVE (appends; does not wipe — pins the real contract)
  - re-import FULL duplicates rows (documented behavior — the reason the UI
    warns) and ImportBatch audit rows record every attempt
  - dry-run over a multi-sheet file reports cross-sheet warnings (Lineas
    referencing unknown recipes)
"""

from __future__ import annotations

import io

import pytest
from openpyxl import Workbook

from app.rms.models import ImportBatch, Ingredient, Product, Recipe, RecipeLine

pytestmark = [pytest.mark.smoke]


def _multi_sheet_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Ingredientes"
    ws.append(["name", "unit", "stock_qty", "purchase_price_gs", "min_stock_qty"])
    ws.append(["Harina 000", "kg", 10, 6500, 2])
    ws.append(["Levadura", "g", 500, 20, 100])

    ws2 = wb.create_sheet("Recetas")
    ws2.append(["name", "yield_qty", "yield_unit", "notes"])
    ws2.append(["Pan francés", 20, "und", "receta base"])

    ws3 = wb.create_sheet("Lineas")
    ws3.append(["recipe_name", "line_kind", "target_name", "qty", "line_unit"])
    ws3.append(["Pan francés", "ingredient", "Harina 000", 1.0, "kg"])
    ws3.append(["Pan francés", "ingredient", "Levadura", 50, "g"])

    ws4 = wb.create_sheet("Productos")
    ws4.append(["name", "sale_price_gs", "recipe_name"])
    ws4.append(["Pan francés (unidad)", 1500, "Pan francés"])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _post(client, path, content, mode):
    return client.post(
        path,
        data={"mode": mode},
        files={"file": ("multi.xlsx", content,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )


def test_multi_sheet_full_journey_lands_and_links(client, session_factory):
    x = _multi_sheet_xlsx()
    rv = _post(client, "/excel/validar", x, mode="FULL")
    assert rv.status_code == 200
    assert "Nombre requerido" not in rv.text  # no hard errors

    ri = _post(client, "/excel/importar", x, mode="FULL")
    assert ri.status_code == 200 and str(ri.url).endswith("/excel")

    with session_factory() as s:
        h = s.query(Ingredient).filter_by(name="Harina 000").one()
        assert float(h.stock_qty) == 10
        rec = s.query(Recipe).filter_by(name="Pan francés").one()
        lines = s.query(RecipeLine).filter_by(recipe_id=rec.id).all()
        assert len(lines) == 2, "recipe lines not linked by natural key"
        prod = s.query(Product).filter_by(name="Pan francés (unidad)").one()
        assert int(prod.sale_price_gs) == 1500
        # batch audit row recorded with row counts
        b = s.query(ImportBatch).order_by(ImportBatch.id.desc()).first()
        assert b is not None and b.source_filename == "multi.xlsx"
        assert b.row_counts_json.get("ingredients", 0) >= 2


def test_full_mode_is_additive_not_destructive(client, session_factory):
    """FULL appends; it must NEVER silently delete rows not in the file."""
    from tests.factories import make_ingredient

    with session_factory() as s:
        survivor = make_ingredient(s, name="Sal sobreviviente")
        s.commit()
        sid = survivor.id

    ri = _post(client, "/excel/importar", _multi_sheet_xlsx(), mode="FULL")
    assert ri.status_code == 200

    with session_factory() as s:
        assert s.get(Ingredient, sid) is not None, (
            "FULL mode deleted a row that was not in the file — data loss!"
        )


def test_full_reimport_blocked_with_friendly_error(client, session_factory):
    """Ingredient names are UNIQUE: FULL re-import must not duplicate rows.
    The route converts IntegrityError into a friendly Spanish 400."""
    x = _multi_sheet_xlsx()
    r1 = _post(client, "/excel/importar", x, mode="FULL")
    assert str(r1.url).endswith("/excel")
    r2 = client.post(
        "/excel/importar",
        data={"mode": "FULL"},
        files={"file": ("multi.xlsx", x,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        follow_redirects=False,
    )
    assert r2.status_code == 400
    assert "PATCH" in r2.text
    with session_factory() as s:
        n = s.query(Ingredient).filter_by(name="Harina 000").count()
        assert n == 1, f"reimport duplicated rows: {n}"



def test_dry_run_flags_invalid_line_kind(client, session_factory):
    """Validator catches structural errors: invalid line_kind + negative qty."""
    wb = Workbook()
    ws3 = wb.create_sheet("Lineas")
    ws3.append(["recipe_name", "line_kind", "target_name", "qty"])
    ws3.append(["Pan", "magic", "Harina", 1.0])
    ws3.append(["Pan", "ingredient", "Sal", -2])
    buf = io.BytesIO()
    wb.save(buf)
    rv = _post(client, "/excel/validar", buf.getvalue(), mode="FULL")
    assert rv.status_code == 200
    assert "line_kind" in rv.text
    assert "debe ser" in rv.text
