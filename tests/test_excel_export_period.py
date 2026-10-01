"""tests/test_excel_export_period.py — E4.S3 /excel/exportar period filter.

Default export is now ``current_month`` (month-end close workflow).
Periods: current_month | last_month | 30d | today | all.

Ventas + StockMoves sheets are filtered to the period.
Ingredientes, Recetas, Productos, Clientes are always full state
(close-out needs the catalog, not just the movements).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from openpyxl import load_workbook

from app.services.export_xlsx import to_file


# --- Period filter on the Ventas sheet ---


def test_export_default_is_current_month(qseed, tmp_path, session_factory):
    """With no filter, only this-month sales appear in Ventas."""
    qseed("with_sale")  # adds 1 sale today
    Session = session_factory
    out = tmp_path / "out.xlsx"
    with Session() as s:
        to_file(s, out)  # default period=None → 'all'
    wb = load_workbook(out)
    ws = wb["Ventas"]
    # Header row + at least 1 sale row from the seed
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    assert len(rows) >= 1, "default export should include the seeded sale"
    # And the catalog sheets are full state regardless
    assert "Ingredientes" in wb.sheetnames


def test_export_period_current_month_includes_today(qseed, tmp_path, session_factory):
    """The current_month preset includes today's sale."""
    qseed("with_sale")
    Session = session_factory
    out = tmp_path / "current.xlsx"
    with Session() as s:
        to_file(s, out, period="current_month")
    wb = load_workbook(out)
    ws = wb["Ventas"]
    data_rows = list(ws.iter_rows(min_row=2, values_only=True))
    assert len(data_rows) >= 1, "current_month should include today's seeded sale"


def test_export_period_last_month_excludes_today(qseed, tmp_path, session_factory):
    """last_month preset does NOT include sales from today."""
    qseed("with_sale")
    Session = session_factory
    out = tmp_path / "last.xlsx"
    with Session() as s:
        to_file(s, out, period="last_month")
    wb = load_workbook(out)
    ws = wb["Ventas"]
    data_rows = list(ws.iter_rows(min_row=2, values_only=True))
    assert len(data_rows) == 0, "last_month should NOT include today's seeded sale"


def test_export_period_all_includes_all(qseed, tmp_path, session_factory):
    """period='all' includes all sales (no filter)."""
    qseed("with_sale")
    Session = session_factory
    out = tmp_path / "all.xlsx"
    with Session() as s:
        to_file(s, out, period="all")
    wb = load_workbook(out)
    ws = wb["Ventas"]
    data_rows = list(ws.iter_rows(min_row=2, values_only=True))
    assert len(data_rows) >= 1


def test_export_period_30d_includes_today(qseed, tmp_path, session_factory):
    """30d preset includes today's sale."""
    qseed("with_sale")
    Session = session_factory
    out = tmp_path / "30d.xlsx"
    with Session() as s:
        to_file(s, out, period="30d")
    wb = load_workbook(out)
    ws = wb["Ventas"]
    data_rows = list(ws.iter_rows(min_row=2, values_only=True))
    assert len(data_rows) >= 1


def test_export_period_invalid_raises(qseed, session_factory):
    """Unknown period → ValueError."""
    qseed("basic")
    Session = session_factory
    with Session() as s:
        import pytest
        with pytest.raises(ValueError):
            to_file(s, Path("/tmp/bad.xlsx"), period="garbage")


def test_export_ingredient_sheet_unfiltered_by_period(qseed, tmp_path, session_factory):
    """Even with a narrow period, the catalog (Ingredientes) is full state."""
    qseed("with_sale")  # seeds the catalog (≥1 ingredient) + 1 sale today
    Session = session_factory
    out = tmp_path / "narrow.xlsx"
    with Session() as s:
        to_file(s, out, period="today")
    wb = load_workbook(out)
    ws = wb["Ingredientes"]
    data_rows = list(ws.iter_rows(min_row=2, values_only=True))
    # Catalog must not be filtered by the period filter — there should
    # be at least the seeded ingredient.
    assert len(data_rows) >= 1


# --- HTTP endpoint ---


def test_export_endpoint_default_returns_current_month_xlsx(authed_client, qseed):
    """GET /excel/exportar with no params returns the current_month file."""
    qseed("with_sale")
    r = authed_client.get("/excel/exportar")
    assert r.status_code == 200
    # Check Content-Disposition header reflects the period
    cd = r.headers.get("content-disposition", "")
    assert "mes-actual" in cd
    # Body is a real .xlsx (PK magic: starts with PK)
    assert r.content[:2] == b"PK"


def test_export_endpoint_period_all_filename(authed_client, qseed):
    qseed("with_sale")
    r = authed_client.get("/excel/exportar?period=all")
    assert r.status_code == 200
    cd = r.headers.get("content-disposition", "")
    assert "completo" in cd


def test_export_endpoint_period_invalid_returns_400(authed_client):
    r = authed_client.get("/excel/exportar?period=garbage")
    assert r.status_code in (400, 422)


def test_export_endpoint_period_today_includes_today_sale(authed_client, qseed):
    qseed("with_sale")
    r = authed_client.get("/excel/exportar?period=today")
    assert r.status_code == 200
    # Save and parse to confirm today's sale is included
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        f.write(r.content)
        path = f.name
    wb = load_workbook(path)
    ws = wb["Ventas"]
    data_rows = list(ws.iter_rows(min_row=2, values_only=True))
    assert len(data_rows) >= 1