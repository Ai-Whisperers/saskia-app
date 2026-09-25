"""tests/e2e/test_excel_import_journey.py — Gaby's real ops path E2E.

Journey: vendor .xlsx (built in-test with openpyxl, same sheet contract as
app/services/export_xlsx.py) → /excel/validar (dry-run) → /excel/importar
→ stock/prices actually land → PATCH re-run is idempotent (no dupes).

Also covers the guardrails: wrong extension 400, empty file 400, corrupt
rows caught by validation (never reach the DB).
"""

from __future__ import annotations

import io

import pytest
from openpyxl import Workbook

from app.rms.models import Ingredient

pytestmark = [pytest.mark.smoke]


def _vendor_xlsx(rows: list[dict]) -> bytes:
    """Build a vendor sheet matching the import contract: sheet
    'Ingredientes' with headers name/unit/stock_qty/purchase_price_gs."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Ingredientes"
    ws.append(["name", "unit", "stock_qty", "purchase_price_gs"])
    for r in rows:
        ws.append([r["name"], r.get("unit", "kg"), r.get("stock_qty", 0),
                   r.get("purchase_price_gs", 0)])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _post(client, path, content, filename="vendor.xlsx", mode=None):
    data = {}
    if mode:
        data["mode"] = mode
    return client.post(
        path,
        data=data,
        files={"file": (filename, content,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )


def test_full_journey_validate_import_lands_idempotent(client, session_factory):
    from tests.factories import make_ingredient

    # Gaby's catalog already has these rows (PATCH = update-by-name, no
    # auto-create — unknown names land in warnings)
    with session_factory() as s:
        make_ingredient(s, name="Harina 000", unit="kg", stock_qty=2.0,
                        purchase_price_gs=5000)
        make_ingredient(s, name="Sal fina", unit="kg", stock_qty=1.0,
                        purchase_price_gs=2000)
        s.commit()
    rows = [
        {"name": "Harina 000", "unit": "kg", "stock_qty": 25, "purchase_price_gs": 6500},
        {"name": "Sal fina", "unit": "kg", "stock_qty": 4, "purchase_price_gs": 3000},
    ]
    x = _vendor_xlsx(rows)

    # 1. dry-run validation — no errors
    rv = _post(client, "/excel/validar", x)
    assert rv.status_code == 200, rv.text[:300]
    assert "vendor.xlsx" in rv.text

    # 2. real import (PATCH) — 303 redirect (client follows to /excel → 200)
    ri = _post(client, "/excel/importar", x, mode="PATCH")
    assert ri.status_code == 200  # followed redirect to /excel
    assert str(ri.url).endswith("/excel")

    # 3. data landed
    with session_factory() as s:
        h = s.query(Ingredient).filter_by(name="Harina 000").one_or_none()
        assert h is not None, "imported ingredient missing"
        assert float(h.stock_qty) == 25
        assert int(h.purchase_price_gs) == 6500

    # 4. idempotency: PATCH re-run must not duplicate
    ri2 = _post(client, "/excel/importar", x, mode="PATCH")
    assert ri2.status_code == 200
    with session_factory() as s:
        count = s.query(Ingredient).filter_by(name="Harina 000").count()
        assert count == 1, f"PATCH re-run created {count} rows — not idempotent"

    # 5. audit trail was written
    with session_factory() as s:
        from app.rms.models import AuditLog

        n = s.query(AuditLog).filter_by(action="excel.import").count()
        assert n == 2, f"expected 2 excel.import audit rows, got {n}"


def test_validation_catches_bad_rows_before_db(client, session_factory):
    x = _vendor_xlsx([
        {"name": "", "stock_qty": 1},  # name required
        {"name": "Azucar", "stock_qty": -5},  # negative stock
    ])
    rv = _post(client, "/excel/validar", x)
    assert rv.status_code == 200
    assert "Nombre requerido" in rv.text
    assert "negativo" in rv.text
    # nothing landed
    with session_factory() as s:
        assert s.query(Ingredient).filter_by(name="Azucar").count() == 0


def test_import_rejects_wrong_extension(client):
    r = _post(client, "/excel/importar", b"data", filename="vendor.csv")
    assert r.status_code == 400


def test_import_rejects_empty_file(client):
    r = _post(client, "/excel/importar", b"")
    assert r.status_code == 400
