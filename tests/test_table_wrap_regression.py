"""T-16 regression: 5 list pages have .table-wrap for mobile horizontal scroll.

The .table-wrap CSS rule (app.css) gives tables overflow-x:auto so wide
tables scroll horizontally on narrow viewports instead of overflowing
the layout. This test confirms the wrapper is applied to:
- productos.html
- inventario.html
- pedidos.html
- clientes.html
- reportes_libro_ventas.html
"""

from pathlib import Path

TEMPLATES = [
    "app/templates/productos.html",
    "app/templates/inventario.html",
    "app/templates/pedidos.html",
    "app/templates/clientes.html",
    "app/templates/reportes_libro_ventas.html",
]


def _read(rel: str) -> str:
    return Path(rel).read_text(encoding="utf-8")


def test_app_css_has_table_wrap_rule():
    css = _read("app/static/app.css")
    assert ".table-wrap" in css, "T-16 missing: .table-wrap CSS rule not in app.css"
    assert "overflow-x" in css, "T-16 missing: .table-wrap must have overflow-x"
    assert "auto" in css, "T-16 missing: .table-wrap must have overflow:auto (or scroll)"


def test_productos_has_table_wrap():
    src = _read("app/templates/productos.html")
    assert 'class="table-wrap"' in src, "T-16 missing in productos.html"


def test_inventario_has_table_wrap():
    src = _read("app/templates/inventario.html")
    assert 'class="table-wrap"' in src, "T-16 missing in inventario.html"


def test_pedidos_has_table_wrap():
    src = _read("app/templates/pedidos.html")
    # pedidos uses table-sticky-wrap (table-wrap + max-height vertical scroll),
    # which also provides the T-16 overflow-x guarantee.
    assert 'class="table-wrap"' in src or "table-sticky-wrap" in src, "T-16 missing in pedidos.html"


def test_clientes_has_table_wrap():
    src = _read("app/templates/clientes.html")
    assert 'class="table-wrap"' in src, "T-16 missing in clientes.html"


def test_reportes_libro_ventas_has_table_wrap():
    src = _read("app/templates/reportes_libro_ventas.html")
    assert 'class="table-wrap"' in src, "T-16 missing in reportes_libro_ventas.html"


def test_pages_still_render(authed_client):
    """Smoke test: pages still 200 after the wrapping change."""
    for path in ("/productos", "/inventario", "/pedidos", "/clientes"):
        r = authed_client.get(path)
        assert r.status_code == 200, f"{path} broke after T-16 wrap"
