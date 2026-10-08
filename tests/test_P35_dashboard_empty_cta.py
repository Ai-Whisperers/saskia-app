"""P-35.2: /dashboard empty state should have a 'load demo' CTA.

Currently the empty state (line 15-23 of dashboard.html) only has
'Registrar venta' and 'Ver catálogo' buttons. A first-run admin who
wants to see the app working can't load demo data from here.

Fix: add a third button 'Cargar datos demo' linking to /admin/load-demo.
If the route doesn't exist yet, the test skips.

Acceptance:
  - GET /dashboard for an empty DB returns 200.
  - Body contains the empty-state heading.
  - Body contains a 'Cargar datos demo' button/link OR pytest.skip if
    the underlying route doesn't exist.
"""

from __future__ import annotations

import pytest


def test_dashboard_empty_state_demo_cta(client):
    """P-35.2: empty state shows 'Cargar datos demo' link if route exists."""
    r = client.get("/dashboard")
    assert r.status_code == 200
    body = r.text

    # The empty state heading must be present.
    assert "Sin datos este mes todavía" in body, "empty-state heading missing"

    # Check if a 'Cargar datos demo' link exists.
    if "Cargar datos demo" in body or "Cargar demo" in body:
        # The link is present. Verify it points to a real route.
        import re

        link = re.search(r'href="([^"]*)"[^>]*>[^<]*(?:Cargar datos demo|Cargar demo)', body)
        if link:
            href = link.group(1)
            # If it's an internal route, GET it to confirm 200/302.
            if href.startswith("/"):
                r2 = client.get(href)
                if r2.status_code in (404, 405):
                    pytest.skip(f"demo route {href} not yet implemented ({r2.status_code})")
    else:
        # The link is NOT in the page. Check if the route exists at all.
        r2 = client.get("/admin/load-demo")
        if r2.status_code in (404, 405):
            pytest.skip("/admin/load-demo not implemented yet")
        else:
            pytest.fail(
                "dashboard empty state has no 'Cargar datos demo' link "
                "but the route exists. P0.8 fix not applied."
            )
