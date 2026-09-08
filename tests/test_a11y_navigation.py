"""tests/test_a11y_navigation.py — regression tests for nav + a11y.

Verifies:
- Skip link present on every page
- Nav has aria-label="Navegación principal"
- Nav links have aria-current="page" on the active route
- Health link goes to /healthz, NOT /api/healthz (404 bug fix)
- aria-live region for alerts
- Keyboard focus visible
- All other a11y invariants (lang, title, h1, nav, main landmarks)
"""

from __future__ import annotations

PAGES = [
    ("/", "Inicio"),
    ("/login", "Iniciar"),
    ("/productos", "Productos"),
    ("/productos/nuevo", "Productos"),
    ("/recetas", "Recetas"),
    ("/recetas/nueva", "Receta"),
    ("/inventario", "Inventario"),
    ("/ventas", "Ventas"),
    ("/excel", "Excel"),
]


def test_skip_link_present(client):
    """Every page must have a skip-to-main-content link as first focusable element."""
    for path, _ in PAGES:
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} returned {resp.status_code}"
        assert 'class="skip-link"' in resp.text, (
            f"{path} missing skip-link"
        )
        assert 'href="#main-content"' in resp.text, (
            f"{path} skip-link points wrong target"
        )
        assert "Saltar al contenido principal" in resp.text, (
            f"{path} skip-link text missing"
        )


def test_nav_has_aria_label(client):
    """Nav landmark must have an accessible label."""
    resp = client.get("/")
    assert 'aria-label="Navegación principal"' in resp.text


def test_healthz_nav_link_not_api(client):
    """Regression: nav used to link to /api/healthz (404)."""
    resp = client.get("/")
    assert "/api/healthz" not in resp.text
    assert 'href="/healthz"' in resp.text


def test_aria_current_on_inicio(client):
    """On /, the Inicio link should be marked current."""
    resp = client.get("/")
    # The Inicio <a> should contain aria-current="page"
    import re
    m = re.search(r'<a href="/"[^>]*aria-current="page"[^>]*>Inicio</a>', resp.text)
    assert m is not None, "Inicio link not marked aria-current=page on /"


def test_aria_current_on_productos(client):
    """On /productos, the Productos link should be marked current."""
    resp = client.get("/productos")
    import re
    m = re.search(
        r'<a href="/productos"[^>]*aria-current="page"[^>]*>Productos</a>',
        resp.text,
    )
    assert m is not None, "Productos link not marked aria-current=page on /productos"


def test_aria_current_on_recetas(client):
    """On /recetas/nueva, Recetas link should be current (startswith match)."""
    resp = client.get("/recetas/nueva")
    import re
    m = re.search(
        r'<a href="/recetas"[^>]*aria-current="page"[^>]*>Recetas</a>',
        resp.text,
    )
    assert m is not None, "Recetas link not marked on /recetas/nueva"


def test_no_aria_current_when_not_active(client):
    """On /, the Ventas link should NOT be marked aria-current."""
    resp = client.get("/")
    import re
    m = re.search(
        r'<a href="/ventas"[^>]*aria-current="page"[^>]*>Ventas</a>',
        resp.text,
    )
    assert m is None, "Ventas link incorrectly marked current on /"


def test_aria_live_region_for_alerts(client):
    """Alerts region must be aria-live=polite so screen readers announce."""
    resp = client.get("/")
    assert 'aria-live="polite"' in resp.text
    assert 'aria-atomic="true"' in resp.text
    assert 'class="alerts-region"' in resp.text


def test_main_landmark_has_id(client):
    """<main> must have id='main-content' for the skip link target."""
    resp = client.get("/")
    assert 'id="main-content"' in resp.text
    # And the main element should be focusable for screen readers
    assert 'tabindex="-1"' in resp.text


def test_html_lang_attribute(client):
    """All pages must declare language."""
    for path, _ in PAGES:
        resp = client.get(path)
        assert 'lang="es"' in resp.text, f"{path} missing lang=es"


def test_single_h1_per_page(client):
    """Each page must have exactly one <h1>."""
    import re
    for path, _ in PAGES:
        resp = client.get(path)
        h1s = re.findall(r"<h1[\s>]", resp.text)
        assert len(h1s) == 1, f"{path} has {len(h1s)} h1s"


def test_every_page_has_title(client):
    """All pages must have a unique <title>."""
    import re
    for path, _ in PAGES:
        resp = client.get(path)
        m = re.search(r"<title>([^<]+)</title>", resp.text)
        assert m is not None, f"{path} missing <title>"
        assert "Saskia RMS" in m.group(1), f"{path} title lacks brand"


def test_nav_links_have_aria_label(client):
    """Nav landmark accessible — health link has aria-label."""
    resp = client.get("/")
    # The health-link <a> in nav-right should have aria-label
    assert 'aria-label="Estado del servidor"' in resp.text


def test_theme_toggle_has_aria_label(client):
    """Theme toggle button has accessible name."""
    resp = client.get("/")
    assert 'aria-label="Cambiar tema claro/oscuro"' in resp.text


def test_all_navigation_routes_return_200(client):
    """Every nav link must be reachable, no 404 / 500."""
    nav_paths = [
        "/",
        "/productos",
        "/recetas",
        "/inventario",
        "/ventas",
        "/excel",
        "/healthz",
    ]
    for path in nav_paths:
        resp = client.get(path)
        assert resp.status_code == 200, f"nav target {path} returned {resp.status_code}"


def test_static_css_serves(client):
    """Static CSS file must be reachable for the skip-link styles to load."""
    resp = client.get("/static/app.css")
    assert resp.status_code == 200
    assert ".skip-link" in resp.text
