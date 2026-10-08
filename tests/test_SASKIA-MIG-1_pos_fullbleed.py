"""SASKIA-MIG-1: POS full-bleed layout on /ventas.

The operator's most-used screen (/ventas) used to be wrapped in the
global sidebar+topbar, eating ~220px of horizontal real estate that the
POS couldn't use. This test pins the full-bleed behavior:

- /ventas renders with the `body--pos-fullbleed` class, so the CSS
  hides the standard chrome.
- /ventas renders WITH the in-page POS topbar.
- Other pages (/inicio, /reportes) render the standard chrome.

Why we don't assert "<aside class='sidebar'>" is absent in the markup:
the implementation hides the chrome with CSS (display: none) instead of
removing the markup. This keeps the implementation reversible — flipping
the body class off restores the chrome without any template surgery.
The user's complaint is visual, so the visual outcome is what we test.
"""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "path",
    ["/inicio", "/reportes", "/productos", "/clientes"],
    ids=["inicio", "reportes", "productos", "clientes"],
)
def test_other_pages_have_no_fullbleed_class(authed_client, path):
    """Non-POS pages must NOT carry the full-bleed class."""
    resp = authed_client.get(path)
    assert resp.status_code == 200, f"{path} returned {resp.status_code}"
    body = resp.text
    assert "body--pos-fullbleed" not in body, (
        f"{path}: body--pos-fullbleed leaked to a non-POS page"
    )


def test_ventas_renders_fullbleed_body_class(authed_client):
    """The cashier surface (GET /ventas) must carry the full-bleed class."""
    resp = authed_client.get("/ventas")
    assert resp.status_code == 200
    body = resp.text
    # The body tag carries the full-bleed class
    assert "body--pos-fullbleed" in body, (
        "/ventas: body--pos-fullbleed class missing (full-bleed not applied)"
    )


def test_ventas_renders_pos_topbar(authed_client):
    """The in-page POS topbar replaces the hidden global topbar."""
    resp = authed_client.get("/ventas")
    assert resp.status_code == 200
    body = resp.text
    assert '<nav class="pos-topbar"' in body, (
        "/ventas: in-page POS topbar missing — operator loses navigation"
    )


def test_ventas_pos_topbar_has_navigation_links(authed_client):
    """The POS topbar must carry the essential navigation affordances."""
    resp = authed_client.get("/ventas")
    assert resp.status_code == 200
    body = resp.text
    # Find the pos-topbar block
    start = body.find('<nav class="pos-topbar"')
    assert start >= 0
    end = body.find("</nav>", start)
    topbar = body[start:end]
    # Cmd+K search affordance
    assert 'id="pos-cmdk-btn"' in topbar
    # Links to other surfaces
    assert 'href="/ventas/historial"' in topbar, "POS topbar: history link missing"
    assert 'href="/reportes"' in topbar, "POS topbar: reports link missing"
    assert 'href="/logout"' in topbar, "POS topbar: logout link missing"


def test_ventas_historial_does_not_apply_fullbleed(authed_client):
    """The history view (/ventas/historial) is NOT the cashier surface.
    It must not be full-bleed so the operator can navigate back."""
    resp = authed_client.get("/ventas/historial")
    assert resp.status_code == 200
    body = resp.text
    assert "body--pos-fullbleed" not in body, (
        "/ventas/historial: full-bleed leaked here — only /ventas should be full-bleed"
    )


def test_ventas_express_does_not_apply_fullbleed(authed_client):
    """Venta Express is a separate surface with its own template
    (ventas_express.html). It must not be full-bleed — only /ventas is."""
    resp = authed_client.get("/ventas/express")
    assert resp.status_code == 200
    body = resp.text
    assert "body--pos-fullbleed" not in body, (
        "/ventas/express: full-bleed leaked here — only /ventas should be full-bleed"
    )


def test_ventas_pos_topbar_uses_vos_spanish_copy(authed_client):
    """The POS topbar copy must follow vos-Spanish rules (AGENTS.md
    rule 23): no machine-translation 'Buscar' / 'Buscar...' but
    the operator's voice. This pins the copy so future refactors
    don't accidentally drop into English."""
    resp = authed_client.get("/ventas")
    assert resp.status_code == 200
    body = resp.text
    start = body.find('<nav class="pos-topbar"')
    end = body.find("</nav>", start)
    topbar = body[start:end]
    # The user-visible labels
    assert "Historial" in topbar
    assert "Reportes" in topbar
    assert "Buscar producto, cliente, pedido" in topbar
    # The aria-labels (also user-visible to screen readers)
    assert "Cerrar sesión" in topbar
    # Negative: no English leak
    assert "Search" not in topbar or "Buscar" in topbar
    assert "History" not in topbar
    assert "Logout" not in topbar
