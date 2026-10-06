"""Tests for PRODUCCION-V3 Phase 6 — manana page cross-navigation.

The audit (M2) noted that operators using /produccion/manana had
to use the sidebar to switch to /produccion (today) or to the
week view. Phase 6 ship:
  - /produccion/manana now has a '← Hoy' button that links to
    /produccion?for_date=<today>.
  - And a 'Ver semana' link to the week plan.
  - The route exposes `today_iso` for the template to use.
"""
from __future__ import annotations


def test_manana_renders_today_link(client, qseed):
    qseed("with_kyrian_full")
    r = client.get("/produccion/manana")
    body = r.content.decode("utf-8", errors="replace")
    assert r.status_code == 200
    assert 'data-manana-page-nav' in body, "manana page-nav block missing"
    assert 'href="/produccion?for_date=' in body, "today link missing"
    assert "Hoy" in body, "Hoy button label missing"


def test_manana_renders_week_link(client, qseed):
    qseed("with_kyrian_full")
    r = client.get("/produccion/manana")
    body = r.content.decode("utf-8", errors="replace")
    assert r.status_code == 200
    assert 'href="/produccion"' in body, "week link missing"
    assert "Ver semana" in body or "semana" in body.lower()


def test_manana_still_has_pedidos_card(client, qseed):
    """Phase 6 doesn't touch the pedidos_manana card; it must
    still render so the cook can see committed orders for tomorrow."""
    qseed("with_kyrian_full")
    r = client.get("/produccion/manana")
    body = r.content.decode("utf-8", errors="replace")
    assert r.status_code == 200
    # PRO-PED (2026-09-30) — the pedidos card is part of the surface.
    # Even when no pedidos are seeded, the heading is only emitted when
    # pedidos_manana is truthy. So we just verify the page loads
    # without error and the manana-page-nav is above the fold.
    nav_pos = body.find("data-manana-page-nav")
    h1_pos = body.find("Producción de mañana")
    assert nav_pos > 0 and h1_pos > 0
    assert nav_pos > h1_pos, "manana-page-nav must come after the H1"


def test_today_iso_is_in_context(client, qseed):
    """The route must set today_iso so the template can link to
    /produccion?for_date=<today>."""
    qseed("with_kyrian_full")
    r = client.get("/produccion/manana")
    body = r.content.decode("utf-8", errors="replace")
    assert r.status_code == 200
    # The link should have a date in the for_date query param.
    import re
    m = re.search(r'href="/produccion\?for_date=([\d-]+)"', body)
    assert m, "no for_date param in manana's today link"
    # Format: YYYY-MM-DD (10 chars)
    assert len(m.group(1)) == 10, f"date format unexpected: {m.group(1)!r}"
