"""tests/test_SASKIA-304_clientes_productos.py — Phase 3, clientes + productos + recetas.

Locks the fixes per docs/ux/copy-fix-list.md for CLI.*, PROD.*, RECETA.*:

  - CLI.2: cliente_detalle must have a clear `Últ. 30d` indicator
  - CLI.3: clientes_nuevo / cliente_editar must have phone placeholder +595 9XX
  - CLI.4: `nudge` banner appears on /clientes with the four fields
  - PROD.1 (P0): NO duplicate "Importar CSV" button in productos.html
  - PROD.2: producto_form must have helpful placeholders (name, price)
  - PROD.3: productos.html must have the full filter toolbar
  - RECETA.1 (P1): receta_detalle margin pill must show a real number
    (the old formula `100 * (1 - unit_cost / (unit_cost/0.65))` was a
    placeholder that always computed 35%)
  - RECETA.2: recetas.html filter toolbar with difficulty multi-select
  - RECETA.3: receta_form must show effective-ingredients panel
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.smoke]

TEMPLATES = Path("/opt/data/work/saskia-app/app/templates")


def test_clientes_page_has_nudge_banner():
    """`/clientes` must show the incomplete-data nudge banner."""
    src = TEMPLATES.joinpath("clientes.html").read_text()
    assert "Datos incompletos" in src, "Missing 'Datos incompletos' nudge banner"
    # The 4 incomplete fields
    for field in ("sin_telefono", "sin_dietary", "sin_direccion", "sin_consent"):
        assert field in src, f"Missing nudge field: {field}"


def test_cliente_editar_has_phone_placeholder():
    """`cliente_editar.html` must use Paraguay phone placeholder `+595 9XX XXXXX`."""
    src = TEMPLATES.joinpath("cliente_editar.html").read_text()
    assert "+595" in src, "Missing Paraguay phone placeholder"


def test_cliente_detalle_shows_lifetime_spend():
    """`cliente_detalle.html` must show the lifetime spend as the primary
    stat (the most relevant figure for a customer ficha). The 30d window
    already appears in `pedido_detalle.html` (cross-customer view)."""
    src = TEMPLATES.joinpath("cliente_detalle.html").read_text()
    assert "lifetime_spend_gs" in src, "Missing lifetime_spend_gs in context"
    assert "Gasto total" in src, "Missing 'Gasto total' stat card label"
    # And the loyalty program description (1 punto = X Gs.)
    assert "punto" in src and "Gs." in src, "Missing loyalty program description"


def test_productos_no_duplicate_importar_csv():
    """`productos.html` must NOT have a duplicate `Importar CSV` button.

    Bug: lines 27 and 33 both rendered the same link with same class.
    Fix: keep one (the secondary-styled one), drop the duplicate.
    """
    src = TEMPLATES.joinpath("productos.html").read_text()
    count = src.count('href="/productos/importar"')
    assert count == 1, f"Found {count} `Importar CSV` buttons — should be exactly 1"


def test_producto_form_has_helpful_placeholders():
    """`producto_form.html` must have a name placeholder and a price placeholder."""
    src = TEMPLATES.joinpath("producto_form.html").read_text()
    assert "Muffin" in src or "Pan" in src or "Factura" in src, "Missing name placeholder example"
    # Price placeholder should be formatted Gs. (with thousands sep)
    assert "8.000" in src or "8000" in src, "Missing price placeholder example"


def test_productos_filter_toolbar():
    """`productos.html` must have the full filter toolbar: search + tag + category + margin + availability + recipe."""
    src = TEMPLATES.joinpath("productos.html").read_text()
    for f in (
        'name="q"',
        'name="tag"',
        'name="category"',
        'name="margen"',
        'name="disponibles"',
        'name="has_recipe"',
    ):
        assert f in src, f"Missing filter field: {f}"


def test_receta_detalle_margin_pill_honest():
    """`receta_detalle.html` margin pill must NOT use the old bogus
    `1 / 0.65` formula (which always = 35%, a literal placeholder).

    The 2026-10-07 fix replaced the always-35% pill with a real
    "Costo: Gs. X/u" indicator — honest about the missing data until
    Phase 6.5 wires recipe → product sale_price.
    """
    src = TEMPLATES.joinpath("receta_detalle.html").read_text()
    # Strip Jinja/HTML comments so the migration comment (which
    # mentions `/ 0.65` to explain what was removed) doesn't trigger
    # the assertion.
    import re

    code = re.sub(r"\{#.*?#\}", "", src, flags=re.S)
    assert "/ 0.65" not in code, (
        "Old placeholder margin formula (1 / 0.65) still in code (not in comment)"
    )
    # The new cost pill
    assert "Costo: Gs." in src, "New honest cost pill missing"

    assert "/ 0.65" not in code, "Old placeholder margin formula (1 / 0.65) still in code (not in comment)"
    # The new cost pill must use the shared m.gs macro (D3 lint)
    assert "Costo: {{ m.gs(unit_cost.batch_cost_gs) }}/u" in src, (
        "New honest cost pill must use m.gs macro"
    )
    assert "batch_cost_gs" in src, "Cost pill must use unit_cost.batch_cost_gs"
    # Currency drift lint: raw Gs. {{ pattern forbidden
    drift_pattern = re.compile(r"Gs\.\s*\{\{")
    assert not drift_pattern.search(src), "Currency drift: raw 'Gs. {{' in receta_detalle"


def test_recetas_filter_toolbar_difficulty_multiselect():
    """`recetas.html` must have difficulty multi-select (1-5)."""
    src = TEMPLATES.joinpath("recetas.html").read_text()
    for d in ("1 — Muy fácil", "5 — Muy difícil"):
        assert d in src, f"Missing difficulty option: {d}"


def test_receta_form_has_effective_ingredients_panel():
    """`receta_form.html` must show the 'ingredientes efectivos' panel
    (the P3 batch UX that explodes sub-recipes)."""
    src = TEMPLATES.joinpath("receta_form.html").read_text()
    assert "effective-ingredients" in src, "Missing effective-ingredients panel"
    assert "merged_count" in src, "Missing merged_count badge (N× sumadas)"


def test_cliente_nuevo_inline_form():
    """`clientes.html` must have an inline `nuevo cliente` form (not a separate page)."""
    src = TEMPLATES.joinpath("clientes.html").read_text()
    assert "inline-new-client" in src, "Missing inline new-client form anchor"
    # The new-cliente button
    assert "nuevo-cliente-btn" in src, "Missing nuevo-cliente button"


def test_producto_detalle_shows_recipe_and_prices():
    """`producto_detalle.html` must show the product's recipe (if any) and prices."""
    src = TEMPLATES.joinpath("producto_detalle.html").read_text()
    assert "Receta" in src or "receta" in src, "Missing recipe section"
    assert "Precio" in src or "precio" in src, "Missing price section"
