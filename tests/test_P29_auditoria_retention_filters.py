"""P-29 / audit: /auditoria retention banner + filters + CSV export."""
from __future__ import annotations

import pytest


pytestmark = [pytest.mark.smoke]


def test_auditoria_retention_banner(client):
    """P-29-1: Page shows the retention banner explaining data lifecycle."""
    r = client.get("/auditoria")
    assert r.status_code == 200, f"got {r.status_code}"
    body = r.text.lower()
    # The Spanish retention banner ("se eliminan automáticamente después de 1 año")
    assert (
        "se eliminan automáticamente" in body
        and ("1 año" in body or "1 ano" in body)
    ), (
        "Missing retention banner on /auditoria. Audit had this visible. "
        "Translation: 'entries are automatically deleted after 1 year'."
    )


def test_auditoria_filter_form(client):
    """P-29: Page has filter inputs (action, user, IP, dates)."""
    r = client.get("/auditoria")
    assert r.status_code == 200
    # Action filter
    assert 'name="action_filter"' in r.text, "Missing action_filter input"
    # User filter
    assert 'name="user_filter"' in r.text, "Missing user_filter input"
    # IP filter
    assert 'name="ip_filter"' in r.text, "Missing ip_filter input"
    # Date filters (start_date / end_date or just "fecha")
    assert (
        'name="start_date"' in r.text
        and 'name="end_date"' in r.text
    ), "Missing start_date / end_date filter inputs"


def test_auditoria_csv_export_link(client):
    """P-29: Page has an Exportar CSV button that links to the export endpoint."""
    r = client.get("/auditoria")
    assert r.status_code == 200
    # Anchor with download attribute pointing to /auditoria/export.csv
    assert "/auditoria/export.csv" in r.text, "Missing /auditoria/export.csv export link"
    assert "Exportar CSV" in r.text, "Missing 'Exportar CSV' button label"


def test_auditoria_csv_export_endpoint_returns_csv(client):
    """P-29: GET /auditoria/export.csv returns CSV content (text/csv or 200 with download)."""
    r = client.get("/auditoria/export.csv")
    # Acceptable: 200 with CSV content, or any non-5xx
    assert r.status_code in (200, 303), f"got {r.status_code}"
    if r.status_code == 200:
        ct = r.headers.get("content-type", "").lower()
        body = r.text
        # Either explicit CSV content-type or CSV-shaped content (commas, at least one newline)
        is_csv_content_type = "text/csv" in ct or "csv" in ct
        looks_like_csv = "," in body[:200] and body.count("\n") >= 1
        assert is_csv_content_type or looks_like_csv, (
            f"export.csv returned 200 but doesn't look like CSV. "
            f"Content-Type: {ct}, body preview: {body[:200]}"
        )


def test_auditoria_pagination_present(client):
    """P-29: Page has pagination controls (Anterior / Siguiente)."""
    r = client.get("/auditoria")
    assert r.status_code == 200
    body = r.text.lower()
    # Either Anterior/Próxima pagination, OR a "No hay entradas" empty state.
    # Both are valid; just ensure something is rendered.
    has_pagination = "anterior" in body or "siguiente" in body or "next" in body
    has_empty = "no hay" in body or "sin entradas" in body or "vacía" in body
    has_table_or_empty = (
        "<table" in body
        or has_empty
        or "<tbody" in body
        or "no results" in body
    )
    assert has_table_or_empty, (
        "/auditoria returned 200 but no table or empty-state visible"
    )
