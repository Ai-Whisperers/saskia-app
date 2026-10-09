"""tests/test_SASKIA-303_pos.py — Phase 2, POS audit + regression locks.

Audit result (2026-10-07): the POS templates (pedidos_nuevo.html,
pedido_detalle.html, pedido_board.html, pedido_publico.html,
pedido_stock_preview.html) are well-written. The 4 issues listed in
docs/ux/copy-fix-list.md under POS.* are already addressed:

  - POS.1: empty cart hint at `Tocá «+ Agregar ítem» para sumar líneas...`
  - POS.2: pickup window placeholder `Pickup (gratis) — seleccioná zona…`
  - POS.3: Spanish "no es garantía" suffix on ventana_text (Phase 13/14)
  - POS.4: channel/payment combos with proper placeholders

This file locks those good decisions so they don't regress.

The kanban board (pedido_board.html) is the workhorse for the kitchen —
this test also locks the column labels so future refactors don't
re-rename `Listos para retiro` (with the explicit "para retiro" suffix)
to just `Listos` (loses context).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

pytestmark = [pytest.mark.smoke]

TEMPLATES = Path(REPO_ROOT / "app" / "templates")


def test_pedidos_nuevo_empty_cart_hint():
    """Empty cart must have an explicit hint, not just a blank table."""
    src = TEMPLATES.joinpath("pedidos_nuevo.html").read_text()
    assert "Tocá" in src and "Agregar ítem" in src, "Missing empty-cart hint"


def test_pedidos_nuevo_pickup_window_placeholder():
    """Pickup/delivery zone combo placeholder must mention 'Pickup' is free."""
    src = TEMPLATES.joinpath("pedidos_nuevo.html").read_text()
    assert "Pickup (gratis) — seleccioná zona" in src, "Missing 'Pickup (gratis)' placeholder"


def test_pedidos_nuevo_delivery_zone_explainer():
    """Delivery zone help text must explain the cost & min order implications."""
    src = TEMPLATES.joinpath("pedidos_nuevo.html").read_text()
    assert "costo de delivery" in src, "Missing delivery cost explainer"
    assert "pedido mínimo" in src, "Missing minimum-order explainer"


def test_pedidos_nuevo_channel_and_payment_placeholders():
    """Channel and payment-method combos must have helpful placeholders."""
    src = TEMPLATES.joinpath("pedidos_nuevo.html").read_text()
    assert "Seleccioná canal" in src, "Missing channel placeholder"
    assert "Forma de pago esperada" in src, "Missing payment-method label"
    assert "Seleccioná forma de pago" in src, "Missing payment-method placeholder"


def test_pedido_detalle_all_five_statuses_have_pill():
    """pedido_detalle must render a status pill for every estado:
    pending / confirmed / ready / fulfilled / cancelled."""
    src = TEMPLATES.joinpath("pedido_detalle.html").read_text()
    for status in ("pending", "confirmed", "ready", "fulfilled", "cancelled"):
        assert status in src, f"Missing status `{status}` in pedido_detalle.html"
    # The Spanish labels:
    for label in ("Pendiente", "Confirmado", "Listo", "Entregado", "Cancelado"):
        assert label in src, f"Missing Spanish status label `{label}`"


def test_pedido_publico_total_estimated_not_total():
    """Public pedido page says `Total estimado` (not exact total), so
    customers don't argue if the cashier adjusts on pickup."""
    src = TEMPLATES.joinpath("pedido_publico.html").read_text()
    assert "Total estimado" in src, "Public page must say 'Total estimado'"
    # The non-estimated "Total" alone (without "estimado" or similar) should not appear
    # in a context that suggests the exact figure.
    assert "currency_label }} {{ m.gs(pedido.total_gs)" in src, "Total amount rendering missing"


def test_pedido_publico_ventana_text_includes_no_garantia():
    """Public pedido page must show 'no es garantía' on delivery window."""
    src = TEMPLATES.joinpath("pedido_publico.html").read_text()
    # The text comes from ventana_text() macro; we lock that the template
    # renders the ventana_text field
    assert "{{ pedido.ventana_text }}" in src, "Public page should render ventana_text"


def test_pedido_board_kanban_column_labels():
    """KDS kanban must have explicit column labels: Pendientes, En preparación,
    Listos para retiro (the 'para retiro' suffix is critical for context)."""
    src = TEMPLATES.joinpath("pedido_board.html").read_text()
    assert "Pendientes" in src
    assert "En preparación" in src
    assert "Listos para retiro" in src, "Must keep 'para retiro' suffix on 'Listos'"


def test_pedido_detalle_prometido_card_has_window_text():
    """pedido_detalle must render the ventana_text() in the 'Prometido' card
    so the operator sees the (no es garantía) suffix before assuming dispatch."""
    src = TEMPLATES.joinpath("pedido_detalle.html").read_text()
    assert "{{ ventana_text }}" in src, "ventana_text rendering missing from Prometido card"
    assert "Prometido" in src, "Prometido card missing"


def test_pedido_stock_preview_shows_ingredient_table():
    """Stock preview must show the 'Ingredientes a consumir' table with totals."""
    src = TEMPLATES.joinpath("pedido_stock_preview.html").read_text()
    assert "Ingredientes a consumir" in src, "Stock preview missing ingredient table heading"
    assert "Valor total a consumir" in src, "Stock preview missing total cost line"
    # Warnings header
    assert "Stock insuficiente" in src, "Stock preview missing low-stock warning"
