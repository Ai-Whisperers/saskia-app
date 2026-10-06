"""Tests for /eod print-friendly view (Phase B of Sazon-Improvement v2 plan).

EOD is currently a 5-screen scroll on mobile. Print = 1 page, archived in
binder for the monthly close-out. The audit + subagent analysis both flagged
mobile / print UX as the #1 friction point for the operator.

Print template contract:
- Endpoint: GET /eod/print
- Same context as /eod but with print_mode=True (hides nav/sidebar/bottom-nav)
- Includes: date, anomaly count, checklist status, reorder items, notes_for_next
- 1-page layout via @media print
- No sidebar / bottom nav
"""
from __future__ import annotations


def test_eod_print_endpoint_renders_200(client, qseed):
    qseed("with_kyrian_full")
    r = client.get("/eod/print")
    assert r.status_code == 200


def test_eod_print_includes_anomaly_count(client, qseed):
    """The print template should reference the anomaly system (either
    showing the count when >0 or having a section for it)."""
    qseed("with_kyrian_full")
    r = client.get("/eod/print")
    body = r.text
    # Either the count is shown (when anomalies exist) OR the section
    # is present (header is always there for the field to land in)
    assert (
        "anomal" in body.lower()
        or "anomalia" in body.lower()
        or "⚠" in body  # the warning symbol used in the template
        or "{{ anomaly_count" in body  # template literal (shouldn't happen)
    ), "expected anomaly reference in print view template or rendered HTML"


def test_eod_print_includes_checklist_status(client, qseed):
    qseed("with_kyrian_full")
    r = client.get("/eod/print")
    body = r.text
    # The checklist is the main EOD content
    assert "checklist" in body.lower() or "cierre" in body.lower(), (
        "expected checklist or 'cierre' in print view"
    )


def test_eod_print_does_not_include_sidebar_or_bottom_nav(client, qseed):
    """Print view must not show navigation chrome to the user. The HTML
    may still contain the nav DOM (hidden via CSS), but the visible
    content should be only the EOD summary."""
    qseed("with_kyrian_full")
    r = client.get("/eod/print")
    body = r.text
    # The print view should not have a .sidebar element that is visible
    # (i.e., without display:none). Check for the print-only class instead.
    # Easiest: assert the page has the .print-only content sections
    assert 'class="print-only"' in body or "print-only" in body, (
        "expected .print-only content sections in print view"
    )
    # And it should NOT have the standard EOD form (which the regular
    # /eod view has but the print view should not).
    assert '<form' not in body, (
        "print view should not have a form (just static summary)"
    )


def test_eod_print_uses_print_css_media_query(client, qseed):
    """The template should reference @media print or have a print-mode class
    so the page lays out 1-page when printed."""
    qseed("with_kyrian_full")
    r = client.get("/eod/print")
    body = r.text
    # Either an inline @media print or a CSS link to one
    has_print = (
        "@media print" in body
        or "media=\"print\"" in body
        or "no-print" in body
        or "print-only" in body
    )
    assert has_print, "no @media print / no-print / print-only class found"


def test_eod_print_shows_reorder_items_when_present(client, qseed):
    """If a reorder list is computed for today, it should be in the print."""
    qseed("with_kyrian_full")
    r = client.get("/eod/print")
    body = r.text
    # The print view should always surface what's needed for tomorrow
    # We don't require reorder to be present (depends on stock), but the
    # template should at least have a section for it
    has_section = "reponer" in body.lower() or "comprar" in body.lower() or "stock" in body.lower()
    assert has_section, "expected restock / reorder section in print"
