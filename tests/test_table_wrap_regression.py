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


def test_pedidos_list_leads_with_who_when_next_status():
    """L1 is checkbox, Cliente, Fecha prometida, Estado + Cumplir.

    Period chips and Exportar CSV sit under Filtros. Search and the
    Pendientes / Terminados / Todos lens stay visible. Nuevo pedido
    stays in the page header.
    """
    src = _read("app/templates/pedidos.html")
    assert "<summary>Filtros</summary>" in src
    assert "<summary>Ver detalles</summary>" in src
    assert "<summary>Más</summary>" not in src

    header = src[: src.find("pedidos-filter-bar")]
    assert "Nuevo pedido" in header
    assert "<summary>" not in header

    filtros = src.find("<summary>Filtros</summary>")
    assert src.find('id="pedidos-search"') < filtros
    assert src.find('data-state="pendientes"') < filtros
    assert src.find('data-state="terminados"') < filtros
    assert src.find('data-state="todos"') < filtros
    assert src.find("data-period=") > filtros
    assert src.find('"hoy_manana"') > filtros
    assert src.find('"esta_semana"') > filtros
    assert src.find('"pendientes_viejos"') > filtros
    assert src.find("Exportar CSV") > filtros
    assert "/pedidos/export-csv" in src

    table = src.find('class="table is-hoverable is-striped sortable"')
    assert table > 0
    thead = src[src.find("<thead>", table) : src.find("</thead>", table)]
    for label in ("Cliente", "Fecha prometida", "Estado", "Ver detalles"):
        assert label in thead, label
    for parked in ("Canal", "Pago", "Líneas", "Total", "Acciones"):
        assert parked not in thead, parked
        assert parked in src
    assert 'data-sort-key="customer"' in thead
    assert 'data-sort-key="promised_at"' in thead
    assert 'data-sort-key="status"' in thead
    assert 'data-sort-key="total_gs"' in src
    assert "data-no-sort" in thead
    assert "table-sticky-wrap" in src
    assert 'id="bulk-pedidos-actions"' in src
    assert 'id="select-all"' in src
    assert 'id="pedidos-search"' in src

    tbody = src[src.find("<tbody", table) : src.find("</tbody>", table)]
    details = tbody.find("<details")
    assert details > 0
    assert 'data-period="{{ key }}"' in tbody
    assert 'data-status="{{ p.status }}"' in tbody
    assert tbody.find(">Cumplir<") < details
    assert tbody.find("/cancel") > details
    assert tbody.find("/compartir") > details
    assert tbody.find('href="/pedidos/{{ p.id }}"') > details
    assert "/pedidos/bulk-fulfill" in src
    assert "/pedidos/bulk-cancel" in src


def test_pedido_board_parks_chrome_keeps_columns():
    """Board L1 is the customer, the promised time, and the status column.

    Sound, a-tiempo/atrasados, and the revenue strip open in one click.
    Auto-refresh, the chime, and the three columns stay.
    """
    src = _read("app/templates/pedido_board.html")
    assert "<summary>Filtros</summary>" in src
    assert "<summary>Más</summary>" in src
    assert "<summary>Ver detalles</summary>" in src
    assert 'http-equiv="refresh"' in src
    assert 'id="new-order-chime"' in src
    assert 'id="clock-live"' in src
    assert "kds-kanban" in src
    assert "Pendientes" in src
    assert "En preparación" in src
    assert "Listos para retiro" in src
    assert 'class="card-id"' in src
    assert 'href="tel:' in src
    assert "order-card" in src

    mas = src.find("<summary>Más</summary>")
    filtros = src.find("<summary>Filtros</summary>")
    assert src.find("Auto-refresh") < mas
    assert src.find('id="sound-toggle"') > mas
    assert src.find("Sin audio") > mas
    assert src.find('data-filter="on-time"') > filtros
    assert src.find('data-filter="overdue"') > filtros
    assert src.find('id="board-revenue"') > filtros

    kanban = src[src.find('class="kds-kanban') : src.find("{{ render_group(")]
    card = kanban[kanban.find("kds-card") : kanban.find("{% else %}")]
    details = card.find("<details")
    assert card.find("k.customer") < details
    assert card.find("k.promised") < details
    assert card.find(">Abrir<") < details
    assert card.find("k.lines") > card.find("<summary>Ver detalles</summary>")
    assert card.find("k.ventana_text") > details


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
