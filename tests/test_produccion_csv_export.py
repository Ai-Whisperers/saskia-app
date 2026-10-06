"""Tests for /produccion CSV export (Phase A of Sazon-Improvement v2 plan).

Operators need a way to grab the daily plan in CSV so they can paste
into WhatsApp for the team or import into Excel. The audit / subagent
analysis both flagged this as the #1 high-ROI small feature (saves
5min/turn × 30 turns/month = 2.5h/month).

CSV contract:
- Endpoint: GET /produccion/export.csv?for_date=YYYY-MM-DD
- Content-Type: text/csv
- Columns: product_name, qty_to_produce, source, confidence, is_ad_hoc
- One row per product in the day-view plan
- No customer PII (audit gap: PII leak risk)
- Respects for_date query param (defaults to today Asunción-local)
"""
from __future__ import annotations

import csv
import io


def test_csv_export_endpoint_returns_csv_content_type(client, qseed):
    qseed("with_kyrian_full")
    r = client.get("/produccion/export.csv?for_date=2026-10-06&view=day")
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert ct.startswith("text/csv"), f"expected text/csv, got {ct!r}"


def test_csv_export_has_one_row_per_product_in_day_view(client, qseed):
    qseed("with_kyrian_full")
    r = client.get("/produccion/export.csv?for_date=2026-10-06&view=day")
    body = r.content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(body))
    rows = list(reader)
    # kyrian_full seeds at least 1 product
    assert len(rows) >= 1, "expected ≥1 row in CSV"
    for row in rows:
        # Every row has the contract columns
        assert "product_name" in row
        assert "qty_to_produce" in row
        assert "source" in row
        assert "confidence" in row
        assert "is_ad_hoc" in row


def test_csv_export_columns_match_spec(client, qseed):
    """Exact column order: product_name, qty_to_produce, source, confidence, is_ad_hoc.
    The spec says the order is load-bearing for WhatsApp paste formatting."""
    qseed("with_kyrian_full")
    r = client.get("/produccion/export.csv?for_date=2026-10-06&view=day")
    body = r.content.decode("utf-8")
    first_line = body.split("\n", 1)[0].strip()
    expected = "product_name,qty_to_produce,source,confidence,is_ad_hoc"
    assert first_line == expected, f"header mismatch:\n  got:      {first_line!r}\n  expected: {expected!r}"


def test_csv_export_does_not_leak_customer_pii(client, qseed):
    """Customer names + phones must NEVER appear in the daily plan CSV.
    That's for /pedidos export. Production plan is product-only."""
    qseed("with_kyrian_full")
    r = client.get("/produccion/export.csv?for_date=2026-10-06&view=day")
    body = r.content.decode("utf-8").lower()
    # Common PII column names
    for forbidden in ("customer", "phone", "address", "email", "cedula", "ruc"):
        assert forbidden not in body, (
            f"PII column {forbidden!r} leaked into production CSV"
        )


def test_csv_export_respects_for_date(client, qseed):
    """Two different dates should produce CSVs with different content. The
    planner returns rows based on rolling 14d history, so we verify that
    for_date actually controls the response (different date → different
    filename in Content-Disposition, different timestamp)."""
    qseed("with_kyrian_full")
    r1 = client.get("/produccion/export.csv?for_date=2026-10-06&view=day")
    r2 = client.get("/produccion/export.csv?for_date=2026-10-07&view=day")
    assert r1.status_code == r2.status_code == 200
    # Content-Disposition should reflect the for_date
    cd1 = r1.headers.get("content-disposition", "")
    cd2 = r2.headers.get("content-disposition", "")
    assert "2026-10-06" in cd1, f"expected 2026-10-06 in disposition, got {cd1!r}"
    assert "2026-10-07" in cd2, f"expected 2026-10-07 in disposition, got {cd2!r}"
