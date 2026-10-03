"""tests/test_pedido_detalle_split.py — Phase 21 pedido detail split-pane.

Verifies pedido_detalle.html now uses a split-pane layout:
- data column wraps all the read-only sections
- actions column is sticky and contains the Acciones card
- on narrow screens the layout collapses to a single column
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "app" / "templates"


def test_pedido_detalle_uses_split_pane():
    """The template must contain the split-pane wrapper."""
    text = (TEMPLATES_DIR / "pedido_detalle.html").read_text()
    assert "pedido-split" in text, "missing pedido-split container"
    assert "pedido-split__data" in text, "missing data column"
    assert "pedido-split__actions" in text, "missing actions column"


def test_pedido_detalle_actions_column_sticky():
    """The actions column must use position:sticky so it stays in view."""
    # The CSS rule defines it
    css = (TEMPLATES_DIR.parent / "static" / "combobox.css").read_text()
    assert ".pedido-split__actions" in css
    assert "position: sticky" in css.split(".pedido-split__actions")[1].split("}")[0]


def test_pedido_detalle_responsive_breakpoint():
    """The split-pane must collapse to single column on small screens."""
    css = (TEMPLATES_DIR.parent / "static" / "combobox.css").read_text()
    assert "@media (max-width: 900px)" in css
    assert "grid-template-columns: 1fr" in css


def test_pedido_detalle_data_column_wraps_all_cards():
    """The data column should wrap all the read-only sections."""
    text = (TEMPLATES_DIR / "pedido_detalle.html").read_text()
    # The data column opens after the first Cliente+Prometido grid-2
    # and closes before the Acciones card
    data_start = text.find('<div class="pedido-split__data">')
    data_end = text.find('</div>\n  <div class="pedido-split__actions">')
    assert data_start > 0, "data column not found"
    assert data_end > data_start, "actions column not found after data"
    block = text[data_start:data_end]
    # Should contain the major data cards
    for needle in ("Impacto en puntos", "Ventas generadas", "Entrega",
                   "Historial", "Otros pedidos"):
        assert needle in block, f"data column missing section: {needle}"


def test_pedido_detalle_actions_column_contains_acciones():
    """The actions column must wrap the Acciones card + Volver link."""
    text = (TEMPLATES_DIR / "pedido_detalle.html").read_text()
    actions_start = text.find('<div class="pedido-split__actions">')
    assert actions_start > 0
    # The actions column closes after the Volver link
    actions_end = text.find('</div>\n</div>\n\n{% endblock %}')
    assert actions_end > actions_start
    block = text[actions_start:actions_end]
    assert "Acciones" in block
    assert "Volver al listado" in block
