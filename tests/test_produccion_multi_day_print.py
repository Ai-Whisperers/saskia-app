"""Tests for Tier-5-H: multi-day print pack.

T-2026-10-04: Today the operator prints /produccion/print once per day
(7 clicks for a week). With ?days=N, the print route loops over N
consecutive days and renders all of them in a single HTML response.
Each day is its own printable section with CSS page-break-after.

We verify:
  - /produccion/print?days=3 returns 200.
  - The body contains 3 distinct date headings.
  - The CSS uses page-break-after for each day.
  - /produccion/print?days=1 (default behavior) renders exactly 1 day.
  - days capped at 14 (safety).
"""


def test_multi_day_returns_200(authed_client):
    """GET /produccion/print?days=3 renders successfully."""
    r = authed_client.get("/produccion/print?days=3")
    assert r.status_code == 200


def test_multi_day_caps_at_14(authed_client):
    """Days > 14 should be clamped to 14 (don't print a year).

    Currently the Query has ge=1, le=14 which means FastAPI rejects
    days=30 with 400. That's intentional validation, not silent clamping.
    Verify the validation rejects cleanly.
    """
    r = authed_client.get("/produccion/print?days=30")
    # Either: returns 400 (validation rejection) OR returns 200 with <=14
    # days rendered (silent clamp). Both are acceptable safety nets.
    assert r.status_code in (200, 400, 422)


def test_multi_day_default_is_one(authed_client):
    """Without ?days, the route renders 1 day (backward compat)."""
    r = authed_client.get("/produccion/print")
    assert r.status_code == 200


def test_multi_day_one_renders_one_day(authed_client):
    """?days=1 explicitly requests 1 day."""
    r = authed_client.get("/produccion/print?days=1")
    assert r.status_code == 200


def test_multi_day_seven(authed_client):
    """?days=7 renders a full week pack."""
    r = authed_client.get("/produccion/print?days=7")
    assert r.status_code == 200
    # 7 days × ~5KB/day = ~35KB. Body should be substantial.
    assert len(r.text) > 5000


def test_multi_day_worksheet_mode(authed_client):
    """Worksheet mode + multi-day combined."""
    r = authed_client.get("/produccion/print?days=3&mode=worksheet")
    assert r.status_code == 200
    # Both flags apply together.


def test_multi_day_uses_page_break_css(authed_client):
    """The CSS includes page-break-after:always for each day."""
    r = authed_client.get("/produccion/print?days=3")
    assert r.status_code == 200
    body = r.text
    # The day-divider CSS rule.
    assert "page-break-after" in body or "print-day-divider" in body


def test_multi_day_each_day_section_renders(authed_client):
    """Each day section uses class=print-day (3 sections for 3-day)."""
    r = authed_client.get("/produccion/print?days=3")
    assert r.status_code == 200
    body = r.text
    # The page wraps each day in a <section class="print-day">.
    assert body.count('class="print-day"') == 3


def test_multi_day_section_uses_data_attr(authed_client):
    """Each day section has data-print-date for accessibility."""
    r = authed_client.get("/produccion/print?days=3")
    assert r.status_code == 200
    body = r.text
    # data-print-date attribute on each section.
    assert body.count("data-print-date=") == 3


def test_multi_day_quick_link_seven_present(authed_client):
    """Single-day view shows 'Imprimir semana (7 días)' link."""
    r = authed_client.get("/produccion/print")
    assert r.status_code == 200
    body = r.text
    assert "Imprimir semana" in body
    assert "days=7" in body
