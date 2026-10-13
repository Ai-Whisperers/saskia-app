"""Source locks for the ventas historial, detail, and Express compact layout.

Historial answers what sold, for how much, and when. Detail answers whether
this ticket can be explained. Express stays tap-and-charge.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = REPO_ROOT / "app" / "templates"


def _slice(src: str, start: str, end: str, from_idx: int = 0) -> str:
    begin = src.find(start, from_idx)
    assert begin >= 0, f"Missing {start!r}"
    finish = src.find(end, begin)
    assert finish > begin, f"Missing {end!r} after {start!r}"
    return src[begin:finish]


def test_historial_leads_with_fecha_producto_and_total():
    """L1 is Fecha, Producto, Total, and Ver / Anular.

    Search stays visible. Product, days, channel, and CSV sit under Filtros.
    Cant., unit price, cliente, pago, canal, atendido por, and notas sit
    under Ver detalles, with Recibo and Pedido still reachable there.
    """
    src = TEMPLATES.joinpath("ventas_historial.html").read_text(encoding="utf-8")
    assert "Historial de ventas" in src
    assert "Ventas activas" in src
    assert "Total recaudado" in src
    assert "Ticket promedio" in src
    assert "Ir a Nueva venta" in src

    filtros = src.find("<summary>Filtros</summary>")
    assert filtros > 0
    assert src.find('id="sales-search"') < filtros
    assert 'method="get"' in src[:filtros]
    assert 'action="/ventas/historial"' in src[:filtros]
    for token in (
        "name='product_id'",
        "name='days'",
        "name='channel'",
        "Exportar CSV",
        "include_voided",
        "Imprimir reporte",
    ):
        assert src.find(token) > filtros, token

    table = src.find("<table")
    assert src.find("Exportar CSV") < table
    thead = _slice(src, "<thead>", "</thead>", table)
    for label in ("Fecha", "Producto", "Total (Gs.)", "Acciones", "Ver detalles"):
        assert label in thead, label
    for cls in (
        "sale-list__fecha",
        "sale-list__producto",
        "sale-list__total",
        "sale-list__actions",
        "sale-list__details",
    ):
        assert cls in thead, cls
    for parked in ("Cant.", "Unit.", "Cliente", "Pago", "Canal", "Atendido por", "Notas"):
        assert parked not in thead, parked
        assert parked in src

    tbody = _slice(src, "<tbody>", "</tbody>", table)
    details = tbody.find("<summary>Ver detalles</summary>")
    assert details > 0
    lead = tbody[:details]
    assert 'href="/ventas/{{ s.id }}"' in lead
    assert ">Ver</a>" in lead
    assert "/anular" in lead
    assert "js-confirm-form" in lead
    parked = tbody[details:]
    for label in ("Cant.", "Unit.", "Cliente", "Pago", "Canal", "Atendido por", "Notas"):
        assert label in parked, label
    assert "/recibo" in parked
    assert "/pedidos/nuevo?customer_id={{ s.customer_id }}" in parked
    assert 'action="/ventas/{{ s.id }}/anular"' in src
    assert "UIConfirmModal.show" in src
    assert "sales|sum(attribute='qty')" in src
    assert "sales|sum(attribute='total_gs')" in src


def test_historial_footer_labels_the_qty_sum_in_fecha():
    """The page total's quantity sits in Fecha with a Cant. label.

    An unlabeled number under Producto reads as another product name.
    """
    src = TEMPLATES.joinpath("ventas_historial.html").read_text(encoding="utf-8")
    tfoot = _slice(src, "<tfoot>", "</tfoot>")
    fecha = _slice(tfoot, 'class="sale-list__fecha"', "</div>")
    producto = _slice(tfoot, 'class="sale-list__producto"', "</div>")
    assert "Cant." in fecha
    assert "sales|sum(attribute='qty')" in fecha
    assert "sales|sum(attribute='qty')" not in producto
    assert "sales|sum(attribute='total_gs')" in tfoot


def test_historial_print_shows_parked_columns():
    """Imprimir reporte opens each row, and print CSS shows the panel.

    Closed details hide Cant., unit price, cliente, pago, canal, and notas.
    """
    html = TEMPLATES.joinpath("ventas_historial.html").read_text(encoding="utf-8")
    assert 'onclick="printSaleHistory()"' in html
    opener = html.find("d.open = true")
    printer = html.find("window.print()", opener)
    assert opener > 0
    assert printer > opener
    assert (
        ".sale-list details.sale-list__details"
        in html[html.find("function printSaleHistory()") : printer]
    )

    css = (REPO_ROOT / "app" / "static" / "theme.css").read_text(encoding="utf-8")
    marker = ".sale-list details.sale-list__details::details-content"
    idx = css.find(marker)
    assert idx > 0
    block_start = css.rfind("@media print", 0, idx)
    assert block_start > 0
    content_rule = css[idx : css.find("}", idx)]
    assert "content-visibility: visible" in content_rule
    panel = css.find(".sale-list details.sale-list__details > .inv-list__panel", idx)
    assert panel > idx
    panel_rule = css[panel : css.find("}", panel)]
    assert "display: flex" in panel_rule


def test_detalle_leads_with_total_product_and_recibo():
    """L1 is the total, the product with qty, the voided pill, and the receipt.

    Pago y canal, notes, the stock-move table, and the helpdesk fields sit
    under Ver detalles. Reprint and the voided banner stay in the file.
    """
    src = TEMPLATES.joinpath("ventas_detalle.html").read_text(encoding="utf-8")
    summary = src.find("<summary>Ver detalles</summary>")
    assert summary > 0
    lead = src[:summary]
    assert "sale-detail__total" in lead
    assert "sale-detail__what" in lead
    assert "Ver recibo imprimible" in lead
    assert 'href="/ventas/{{sale.id}}/recibo"' in lead
    assert 'status_pill("Anulada"' in lead
    assert "← Volver al historial" in lead
    parked = src[summary:]
    for token in (
        "Pago y canal",
        "Forma de pago",
        "Notas",
        "Movimientos de stock",
        "ANULADA",
        "Puntos ganados",
        "Pedido asociado",
        "Cliente",
        "Precio unitario",
        "Descuento",
    ):
        assert token in parked, token
    assert 'href="/ventas/{{sale.id}}/recibo"' in src
    assert 'href="/ventas/historial"' in src


def test_express_card_is_name_price_qty_and_cobrar():
    """Each card posts efectivo qty to /ventas/nueva. Volver al POS stays a ghost link."""
    src = TEMPLATES.joinpath("ventas_express.html").read_text(encoding="utf-8")
    assert "express-grid" in src
    assert 'action="/ventas/nueva"' in src
    assert "js-confirm-form" in src
    assert 'data-confirm-title="Registrar venta"' in src
    assert 'name="payment_method" value="efectivo"' in src
    assert 'name="qty"' in src
    assert "Cobrar" in src
    assert "Volver al POS" in src
    assert "btn-ghost" in src
    assert "<summary>Más</summary>" not in src
    assert (
        src.find("express-name")
        < src.find("express-price")
        < src.find('name="qty"')
        < src.find(">Cobrar</button>")
    )
