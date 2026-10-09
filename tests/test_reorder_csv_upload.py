"""tests/test_reorder_csv_upload.py — Phase 3 (migration 073) bulk price import.

Covers POST /reorder/upload-prices:

  - Happy path: 2-row CSV imports 2 IngredientPriceEvent rows with
    supplier_id populated.
  - Validation: missing required column → 400.
  - Validation: unknown ingredient → error in response (still 200).
  - Validation: inactive supplier → error in response.
  - Validation: invalid price_gs (non-numeric / negative) → error.
  - Validation: future date → skipped with warning.
  - Dedup: same (ingredient, supplier, date) twice → second is skipped.
  - CSV with BOM (UTF-8-sig) decodes fine.
  - Audit row written for the import.

The endpoint lives on /reorder/* because it's part of the price-tracking
flow, but it accepts ANY CSV — you don't need to be on /reorder to use
it.
"""

from __future__ import annotations

import uuid

from app.rms.models import AuditLog, IngredientPriceEvent
from tests.factories import make_ingredient, make_supplier


def _csv(name_suffix: str) -> str:
    """Build a 2-row CSV using uuid-suffixed names so each test is isolated."""
    return f"""ingredient_name,supplier_name,price_gs,date
harina-{name_suffix},Stock PY-{name_suffix},4200,2026-09-25
harina-{name_suffix},Casa Rica-{name_suffix},4500,2026-09-25
"""


def test_csv_upload_happy_path_imports_two_rows(client, session_factory):
    Session = session_factory
    tag = uuid.uuid4().hex[:6]
    with Session() as s:
        ing = make_ingredient(s, name=f"harina-{tag}", unit="kg")
        sup_a = make_supplier(s, name=f"Stock PY-{tag}")
        sup_b = make_supplier(s, name=f"Casa Rica-{tag}")
        s.commit()
        ing_id = ing.id

    files = {"file": ("prices.csv", _csv(tag).encode("utf-8"), "text/csv")}
    r = client.post("/reorder/upload-prices", files=files)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["ok"] is True
    assert payload["imported"] == 2
    assert payload["skipped"] == 0
    assert payload["errors"] == []

    with Session() as s:
        events = (
            s.query(IngredientPriceEvent).filter(IngredientPriceEvent.ingredient_id == ing_id).all()
        )
        assert len(events) == 2
        suppliers = sorted(e.supplier_id for e in events)
        assert suppliers == sorted([sup_a.id, sup_b.id])
        assert all(e.source == "csv_upload" for e in events)
        assert all(e.supplier_id is not None for e in events)


def test_csv_upload_missing_required_column_returns_400(client, session_factory):
    """CSV without supplier_name column → 400 with helpful message."""
    Session = session_factory
    with Session() as s:
        make_ingredient(s, name=f"harina-{uuid.uuid4().hex[:6]}", unit="kg")
        make_supplier(s, name=f"Stock PY-{uuid.uuid4().hex[:6]}")
        s.commit()

    bad_csv = "ingredient_name,price_gs,date\nharina,4200,2026-09-25\n"
    files = {"file": ("bad.csv", bad_csv.encode("utf-8"), "text/csv")}
    r = client.post("/reorder/upload-prices", files=files)
    assert r.status_code == 400, r.text
    assert "supplier_name" in r.json()["detail"]


def test_csv_upload_unknown_ingredient_errors_but_others_import(client, session_factory):
    """Bad ingredient_name on row 2 → row 2 error, row 1 still imports."""
    Session = session_factory
    tag = uuid.uuid4().hex[:6]
    with Session() as s:
        ing = make_ingredient(s, name=f"harina-{tag}", unit="kg")
        make_supplier(s, name=f"Stock PY-{tag}")
        ing_id = ing.id
        s.commit()

    csv = f"""ingredient_name,supplier_name,price_gs,date
harina-{tag},Stock PY-{tag},4200,2026-09-25
unknown-ingredient-{tag},Stock PY-{tag},5000,2026-09-25
"""
    files = {"file": ("prices.csv", csv.encode("utf-8"), "text/csv")}
    r = client.post("/reorder/upload-prices", files=files)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["imported"] == 1
    assert len(payload["errors"]) == 1
    assert "no encontrado" in payload["errors"][0]["error"]

    with Session() as s:
        events = (
            s.query(IngredientPriceEvent).filter(IngredientPriceEvent.ingredient_id == ing_id).all()
        )
        assert len(events) == 1


def test_csv_upload_inactive_supplier_errors(client, session_factory):
    Session = session_factory
    tag = uuid.uuid4().hex[:6]
    with Session() as s:
        make_ingredient(s, name=f"harina-{tag}", unit="kg")
        make_supplier(s, name=f"Old Shop-{tag}", is_active=False)
        s.commit()

    csv = f"ingredient_name,supplier_name,price_gs,date\nharina-{tag},Old Shop-{tag},4200,2026-09-25\n"
    files = {"file": ("prices.csv", csv.encode("utf-8"), "text/csv")}
    r = client.post("/reorder/upload-prices", files=files)
    payload = r.json()
    assert payload["imported"] == 0
    assert len(payload["errors"]) == 1
    msg = payload["errors"][0]["error"]
    assert "inactivo" in msg or "no encontrado" in msg


def test_csv_upload_invalid_price_errors(client, session_factory):
    Session = session_factory
    tag = uuid.uuid4().hex[:6]
    with Session() as s:
        make_ingredient(s, name=f"harina-{tag}", unit="kg")
        make_supplier(s, name=f"Stock PY-{tag}")
        s.commit()

    csv = (
        f"ingredient_name,supplier_name,price_gs,date\nharina-{tag},Stock PY-{tag},abc,2026-09-25\n"
    )
    files = {"file": ("prices.csv", csv.encode("utf-8"), "text/csv")}
    r = client.post("/reorder/upload-prices", files=files)
    payload = r.json()
    assert payload["imported"] == 0
    assert len(payload["errors"]) == 1
    assert "price_gs" in payload["errors"][0]["error"]


def test_csv_upload_negative_price_errors(client, session_factory):
    Session = session_factory
    tag = uuid.uuid4().hex[:6]
    with Session() as s:
        make_ingredient(s, name=f"harina-{tag}", unit="kg")
        make_supplier(s, name=f"Stock PY-{tag}")
        s.commit()

    csv = f"ingredient_name,supplier_name,price_gs,date\nharina-{tag},Stock PY-{tag},-100,2026-09-25\n"
    files = {"file": ("prices.csv", csv.encode("utf-8"), "text/csv")}
    r = client.post("/reorder/upload-prices", files=files)
    payload = r.json()
    assert payload["imported"] == 0
    assert any(">" in e["error"] for e in payload["errors"])


def test_csv_upload_future_date_skipped_with_warning(client, session_factory):
    """Dates in the future are skipped (warned in preview)."""
    Session = session_factory
    tag = uuid.uuid4().hex[:6]
    with Session() as s:
        make_ingredient(s, name=f"harina-{tag}", unit="kg")
        make_supplier(s, name=f"Stock PY-{tag}")
        s.commit()

    csv = f"ingredient_name,supplier_name,price_gs,date\nharina-{tag},Stock PY-{tag},4200,2099-01-01\n"
    files = {"file": ("prices.csv", csv.encode("utf-8"), "text/csv")}
    r = client.post("/reorder/upload-prices", files=files)
    payload = r.json()
    assert payload["imported"] == 0
    assert payload["skipped"] == 1
    skipped_entries = [p for p in payload["preview"] if "warning" in p]
    assert len(skipped_entries) == 1
    assert "fecha futura" in skipped_entries[0]["warning"]


def test_csv_upload_dedupes_same_day(client, session_factory):
    """Two rows for (ingredient, supplier, same_date) → first imports,
    second skipped."""
    Session = session_factory
    tag = uuid.uuid4().hex[:6]
    with Session() as s:
        make_ingredient(s, name=f"harina-{tag}", unit="kg")
        make_supplier(s, name=f"Stock PY-{tag}")
        s.commit()

    csv = f"""ingredient_name,supplier_name,price_gs,date
harina-{tag},Stock PY-{tag},4200,2026-09-25
harina-{tag},Stock PY-{tag},4300,2026-09-25
"""
    files = {"file": ("prices.csv", csv.encode("utf-8"), "text/csv")}
    r = client.post("/reorder/upload-prices", files=files)
    payload = r.json()
    assert payload["imported"] == 1
    assert payload["skipped"] == 1
    skipped_entries = [p for p in payload["preview"] if "warning" in p]
    assert len(skipped_entries) == 1, (
        f"expected exactly one warning in preview; got: {payload['preview']}"
    )
    assert "duplicado" in skipped_entries[0]["warning"]


def test_csv_upload_handles_bom(client, session_factory):
    """Excel often saves CSVs with a BOM. Endpoint must accept it."""
    Session = session_factory
    tag = uuid.uuid4().hex[:6]
    with Session() as s:
        make_ingredient(s, name=f"harina-{tag}", unit="kg")
        make_supplier(s, name=f"Stock PY-{tag}")
        make_supplier(s, name=f"Casa Rica-{tag}")
        s.commit()

    csv_bytes = b"\xef\xbb\xbf" + _csv(tag).encode("utf-8")
    files = {"file": ("prices.csv", csv_bytes, "text/csv")}
    r = client.post("/reorder/upload-prices", files=files)
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 2


def test_csv_upload_writes_audit_row(client, session_factory):
    Session = session_factory
    tag = uuid.uuid4().hex[:6]
    with Session() as s:
        make_ingredient(s, name=f"harina-{tag}", unit="kg")
        make_supplier(s, name=f"Stock PY-{tag}")
        make_supplier(s, name=f"Casa Rica-{tag}")
        s.commit()

    files = {"file": ("prices.csv", _csv(tag).encode("utf-8"), "text/csv")}
    r = client.post("/reorder/upload-prices", files=files)
    assert r.status_code == 200
    assert r.json()["imported"] == 2

    with Session() as s:
        audits = s.query(AuditLog).filter(AuditLog.action == "write.reorder.csv_upload").all()
        assert len(audits) == 1
        assert audits[0].detail["imported"] == 2
        assert audits[0].detail["filename"] == "prices.csv"
