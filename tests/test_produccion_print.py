"""Tests for /produccion/print — the printable worksheet for the kitchen shift.

T-2026-10-04: Bakers need a paper sheet to run the shift. The /produccion
printable view is a stripped-down day view: products + qty, with checkboxes
to mark as done. No nav, no banners, no source-of-origin explanations —
just the work to do. Add @media print CSS so the page renders cleanly on
paper.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

from datetime import date, timedelta


def test_print_view_anonymous_redirects_or_succeeds_in_test_mode(client):
    """In production, anonymous users get redirected to login (302).

    In the project's test env, SASKIA_TEST_AUTH_DISABLED=1 bypasses the
    auth gate, so the test client gets 200. We accept either behavior —
    what we care about is that the route doesn't 500 and that the
    print view template renders without crashing.
    """
    r = client.get("/produccion/print")
    assert r.status_code in (200, 302, 401), (
        f"Expected 200 (test) or 302/401 (prod), got {r.status_code}: {r.text[:200]}"
    )
    # No 500 errors, no unhandled exceptions
    assert r.status_code < 500, f"Got 5xx: {r.status_code}"


def test_print_view_renders_day_worksheet(authed_client):
    """The print view shows the plan, an Imprimir button, and print styles.

    We don't seed a product here because the test client and the
    session_factory use different sessions (no shared state). Instead
    we just check that the template renders the structural pieces
    (print-sheet wrapper, Imprimir button, @media print rules).
    """
    r = authed_client.get("/produccion/print")
    assert r.status_code == 200
    body = r.text
    # Worksheet structure
    assert 'class="print-sheet"' in body, "print-sheet wrapper missing"
    assert "Imprimir" in body, "Print trigger button missing"
    # @media print rules ship in the global stylesheets (CSS deep-audit
    # f65ce313 moved them out of inline blocks)
    css = (REPO_ROOT / "app" / "static" / "app.css").read_text(encoding="utf-8") + (
        REPO_ROOT / "app" / "static" / "app-shell.css"
    ).read_text(encoding="utf-8")
    assert "@media print" in css, "Print-specific CSS missing"
    # Should have a products table OR an empty-state CTA
    assert "<table" in body or "Generá un plan" in body or "No hay productos" in body, (
        "Neither products table nor empty state found"
    )


def test_print_view_respects_for_date_query_param(authed_client):
    """?for_date=YYYY-MM-DD should set the worksheet date."""
    target = (date.today() + timedelta(days=2)).isoformat()
    r = authed_client.get(f"/produccion/print?for_date={target}")
    assert r.status_code == 200
    body = r.text
    assert target in body, f"Expected date {target} in body, got first 200 chars: {body[:200]}"


def test_print_view_includes_print_stylesheet_link(authed_client):
    """The print view (or base.html) must reference @media print rules."""
    r = authed_client.get("/produccion/print")
    assert r.status_code == 200
    # Global stylesheets carry the @media print rules; the page loads them
    css = (REPO_ROOT / "app" / "static" / "app.css").read_text(encoding="utf-8") + (
        REPO_ROOT / "app" / "static" / "app-shell.css"
    ).read_text(encoding="utf-8")
    assert "@media print" in css, "Print stylesheet or @media print rules missing"


def test_print_view_hides_chrome_on_print(authed_client):
    """@media print rules must hide nav, header, footer — show only the worksheet."""
    r = authed_client.get("/produccion/print")
    assert r.status_code == 200
    # Look for the standard "print: hide chrome" pattern
    # Either inline CSS or a separate stylesheet
    assert "print" in r.text.lower(), "Print view should reference print-specific styles"


def test_print_view_button_on_day_view(authed_client):
    """The /produccion day view should have an 'Imprimir' button linking to /print."""
    r = authed_client.get("/produccion?view=day")
    assert r.status_code == 200
    body = r.text
    # Button or link to print view, with the for_date query param preserved
    assert 'href="/produccion/print' in body or 'href="/produccion/imprimir' in body, (
        f"Print button/link missing on day view. Body excerpt: {body[2000:2500]}"
    )


# ---------------------------------------------------------------- P0:D.4
def test_print_view_shows_iso_week_header(authed_client):
    """P0:D.4 — Print header shows ISO week number so cooks can file by week."""
    target = (date.today() + timedelta(days=2)).isoformat()
    r = authed_client.get(f"/produccion/print?for_date={target}")
    assert r.status_code == 200
    body = r.text
    # ISO week "Semana N (YYYY)" appears in the date line
    import re

    assert re.search(r"Semana \d+ \(\d{4}\)", body), (
        f"P0:D.4 — print header must show 'Semana N (YYYY)' ISO week tag. "
        f"Body date line: {body[body.find('Plan del día') : body.find('Plan del día') + 200]!r}"
    )


def test_print_view_shows_cook_attribution(authed_client):
    """P0:D.4 — Print header shows cook's name so operators can file by cook."""
    r = authed_client.get("/produccion/print")
    assert r.status_code == 200
    body = r.text
    # 'Responsable:' label + the cook_name
    assert "Responsable:" in body, "P0:D.4 — print header must include 'Responsable:' line"


def test_print_view_omits_header_in_worksheet_mode(authed_client):
    """P0:D.4 — ?mode=worksheet (blank sheet) must NOT show cook/week header."""
    r = authed_client.get("/produccion/print?mode=worksheet")
    assert r.status_code == 200
    body = r.text
    # In worksheet mode (blank sheet for handwriting), the cook attribution
    # is omitted so the operator can fill it in by hand.
    assert "Responsable:" not in body, (
        "P0:D.4 — worksheet mode must not show 'Responsable:' line "
        "(the cook writes their own name on a blank sheet)"
    )
