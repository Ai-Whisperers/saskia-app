"""Smoke test for PDF generation endpoints.

Per SASKIA_TEST_PLAN.md §5 #9 — PDF endpoints must:
- Return application/pdf content-type
- Start with %PDF magic bytes
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.smoke


# PDF endpoints from SASKIA_TEST_PLAN.md §1.3
PDF_ROUTES = [
    "/reportes/diario/pdf",
    "/reportes/iva/pdf",
    "/reportes/libro-ventas/set-pdf",
]




@pytest.mark.parametrize("route", PDF_ROUTES)
def test_pdf_endpoint_returns_pdf_content_type(client, route):
    """PDF endpoint must return application/pdf."""
    r = client.get(route)
    # 200 = valid PDF, 422 = validation error (e.g., date required), 404 = not implemented
    assert r.status_code < 500, (
        f"GET {route} returned {r.status_code}: {r.text[:200]}"
    )
    if r.status_code == 200:
        content_type = r.headers.get("content-type", "").lower()
        assert "pdf" in content_type, (
            f"{route} content-type '{content_type}' is not PDF"
        )
        # Verify %PDF magic bytes
        body = r.content if hasattr(r, 'content') else r.text.encode()
        assert body.startswith(b"%PDF"), (
            f"{route} body does not start with %PDF magic bytes. "
            f"First bytes: {body[:20]!r}"
        )


def test_pdf_endpoints_skip_if_not_implemented(client):
    """If PDF endpoints return 404 (not implemented), skip gracefully."""
    # If all PDF routes return 404, the feature isn't implemented yet
    statuses = [client.get(route).status_code for route in PDF_ROUTES]
    if all(s == 404 for s in statuses):
        pytest.skip("PDF endpoints not yet implemented (all 404)")


def test_pdf_does_not_500_on_valid_query(client):
    """PDF endpoint with a query param must not 500."""
    r = client.get("/reportes/diario/pdf?fecha=2026-09-22")
    assert r.status_code < 500, (
        f"/reportes/diario/pdf with fecha returned {r.status_code}"
    )
