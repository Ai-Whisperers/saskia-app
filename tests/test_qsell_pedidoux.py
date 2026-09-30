"""tests/test_qsell_pedidoux.py — PRO-QS + PRO-PED-UX (2026-09-30).

PRO-QS: tap en quick-sell agrega al carrito SIN recargar (AJAX).
  El form del grid ahora es interceptado por JS; sin JS sigue el submit
  nativo. Tests: el listener está en el grid (delegación) + el form sigue
  siendo POST válido como fallback + endpoint /ventas/nueva intacto.

PRO-PED-UX: seleccionar cliente en /pedidos/nuevo prellena teléfono/hint.
  Root cause: pedido-combos.js buscaba .saskia-customer-combo (clase que no
  existe en ningún template) → el hook nunca enganchaba. Ahora matchea
  saskia-combo[name=customer_id] + delega en el evento change del elemento.
"""
from __future__ import annotations


# ── PRO-QS: quick-sell agrega al carrito sin recargar ────────────────────────
def test_quick_sell_grid_tiene_listener_ajax(authed_client, session_factory):
    r = authed_client.get("/ventas")
    assert r.status_code == 200
    # el listener delegado en el grid existe
    assert 'onQsSubmit' in r.text
    # agrega al carrito existente en vez de dejar pasar el submit
    assert "qsAddToCart(form)" in r.text
    # quickAddToCart vive en el IIFE del carrito (siempre presente)
    assert "window.quickAddToCart = function" in r.text


def test_quick_sell_endpoint_sigue_creando_venta(authed_client, session_factory):
    """El submit nativo (sin JS) debe seguir vendiendo en 1 tap."""
    from sqlalchemy.orm import sessionmaker

    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        from tests.factories import make_product

        p = make_product(s, sale_price_gs=7000)
        s.commit()
        pid = p.id
    finally:
        s.close()
    r = authed_client.post(
        "/ventas/nueva",
        data={"product_id": pid, "qty": "1", "channel": "mostrador",
              "payment_method": "efectivo"},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text[:300]
    s2 = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        from app.rms.models_legacy import Sale

        sale = s2.query(Sale).order_by(Sale.id.desc()).first()
        assert sale is not None and sale.payment_method == "efectivo"
    finally:
        s2.close()


# ── PRO-PED-UX: el hook del cliente matchea el combo real ────────────────────
def test_pedidos_nuevo_carga_pedido_combos_y_combo_correcto(authed_client):
    r = authed_client.get("/pedidos/nuevo")
    assert r.status_code == 200
    # el combo de cliente con el name que el JS ahora busca
    assert 'name="customer_id"' in r.text or "name='customer_id'" in r.text
    # el JS con el fix está referenciado
    assert "pedido-combos.js" in r.text
    # el input de teléfono que debe prellenarse existe
    assert 'id="customer_phone"' in r.text


def test_pedido_combos_js_matchea_customer_id(tmp_path=None):
    """El JS del repo contiene el selector corregido (no la clase fantasma)."""
    import pathlib

    js = pathlib.Path("app/static/pedido-combos.js").read_text()
    assert "saskia-combo[name=\"customer_id\"]" in js
    # el handler prellena teléfono fill-if-empty
    assert "phoneInput.value = item.phone" in js
    # y actualiza el hint de cliente seleccionado
    assert "customer_picked_hint" in js
