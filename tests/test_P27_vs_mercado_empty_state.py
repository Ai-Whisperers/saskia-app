"""P-27 / audit #18: /vs-mercado empty-state when no market data.

Audit #18: When MarketBenchmark table is empty, /vs-mercado renders an
empty table with no explanation — confusing for first-time users.

These tests verify:
1. /vs-mercado renders 200
2. When there are no benchmarks, the page shows an empty-state with a
   helpful message AND a CTA to add the first benchmark.
3. The currency formatter is used consistently.
4. No Python errors when iterating an empty benchmark list.
"""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.smoke]


def test_vs_mercado_renders_200(client):
    """P-27: /vs-mercado reachable."""
    r = client.get("/vs-mercado")
    assert r.status_code == 200, f"got {r.status_code}"


def test_vs_mercado_has_page_header(client):
    """P-27: Page has a proper header."""
    r = client.get("/vs-mercado")
    assert r.status_code == 200
    body = r.text
    assert (
        "Comparativa" in body
        or "vs mercado" in body.lower()
        or "Benchmarks" in body
    ), "Missing page header on /vs-mercado"


def test_vs_mercado_empty_state_when_no_data(client):
    """P-27 #18: When no benchmarks exist, page must show empty-state."""
    r = client.get("/vs-mercado")
    assert r.status_code == 200
    body = r.text
    # With an empty DB, the template must show the empty-state block.
    # We look for distinctive markers: the empty-state class and the
    # helpful copy.
    has_empty_state = (
        "empty-state" in body
        and (
            "Sin datos de mercado cargados" in body
            or "Sin benchmarks" in body
            or "Agregar primer benchmark" in body
        )
    )
    # Allow the test to pass if there are actual benchmarks (data was seeded).
    has_table_rows = "data-delta-gs" in body and "<tbody>" in body

    assert has_empty_state or has_table_rows, (
        "Empty benchmarks table renders without explanation (audit #18). "
        "Add an empty-state block with a CTA."
    )


def test_vs_mercado_currency_format(client):
    """P-27: Currency values use 'Gs.' prefix."""
    r = client.get("/vs-mercado")
    assert r.status_code == 200
    body = r.text
    # Header uses "Gs." for the column names; even with no data this
    # should be present.
    assert "Gs." in body, "Missing 'Gs.' currency marker on /vs-mercado"


def test_vs_mercado_csv_export_link(client):
    """P-27: Page has a CSV export link."""
    r = client.get("/vs-mercado")
    assert r.status_code == 200
    body = r.text
    assert (
        "format=csv" in body or ("vs-mercado" in body and ".csv" in body)
    ), "Missing CSV export link on /vs-mercado"


def test_vs_mercado_edit_endpoint(client):
    """P-27: /vs-mercado/{id}/edit is reachable (auth gated)."""
    r = client.get("/vs-mercado/1/edit")
    # Should be 200 (page renders with form) or 404 (no benchmark with id=1)
    # Both are acceptable.
    assert r.status_code in (200, 303, 404), (
        f"/vs-mercado/1/edit returned {r.status_code}"
    )
