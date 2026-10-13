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

from tests.conftest import REPO_ROOT

pytestmark = [pytest.mark.smoke]

TEMPLATES = Path(REPO_ROOT / "app" / "templates")


def test_clientes_page_has_nudge_banner():
    """`/clientes` must show the incomplete-data nudge banner."""
    src = TEMPLATES.joinpath("clientes.html").read_text(encoding="utf-8")
    assert "Datos incompletos" in src, "Missing 'Datos incompletos' nudge banner"
    # The 4 incomplete fields
    for field in ("sin_telefono", "sin_dietary", "sin_direccion", "sin_consent"):
        assert field in src, f"Missing nudge field: {field}"


def test_cliente_editar_has_phone_placeholder():
    """`cliente_editar.html` must use Paraguay phone placeholder `+595 9XX XXXXX`."""
    src = TEMPLATES.joinpath("cliente_editar.html").read_text(encoding="utf-8")
    assert "+595" in src, "Missing Paraguay phone placeholder"


def test_cliente_detalle_shows_lifetime_spend():
    """`cliente_detalle.html` must show the lifetime spend as the primary
    stat (the most relevant figure for a customer ficha). The 30d window
    already appears in `pedido_detalle.html` (cross-customer view)."""
    src = TEMPLATES.joinpath("cliente_detalle.html").read_text(encoding="utf-8")
    assert "lifetime_spend_gs" in src, "Missing lifetime_spend_gs in context"
    assert "Gasto total" in src, "Missing 'Gasto total' stat card label"
    # And the loyalty program description (1 punto = X Gs.)
    assert "punto" in src and "Gs." in src, "Missing loyalty program description"


def test_productos_no_duplicate_importar_csv():
    """`productos.html` must NOT have a duplicate `Importar CSV` button.

    Bug: lines 27 and 33 both rendered the same link with same class.
    Fix: keep one (the secondary-styled one), drop the duplicate.
    """
    src = TEMPLATES.joinpath("productos.html").read_text(encoding="utf-8")
    count = src.count('href="/productos/importar"')
    assert count == 1, f"Found {count} `Importar CSV` buttons — should be exactly 1"


def test_producto_form_has_helpful_placeholders():
    """`producto_form.html` must have a name placeholder and a price placeholder."""
    src = TEMPLATES.joinpath("producto_form.html").read_text(encoding="utf-8")
    assert "Muffin" in src or "Pan" in src or "Factura" in src, "Missing name placeholder example"
    # Price placeholder should be formatted Gs. (with thousands sep)
    assert "8.000" in src or "8000" in src, "Missing price placeholder example"


def test_productos_filter_toolbar():
    """`productos.html` must have the full filter toolbar: search + tag + category + margin + availability + recipe."""
    src = TEMPLATES.joinpath("productos.html").read_text(encoding="utf-8")
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
    src = TEMPLATES.joinpath("receta_detalle.html").read_text(encoding="utf-8")
    # Strip Jinja/HTML comments so the migration comment (which
    # mentions `/ 0.65` to explain what was removed) doesn't trigger
    # the assertion.
    import re

    code = re.sub(r"\{#.*?#\}", "", src, flags=re.S)
    assert "/ 0.65" not in code, (
        "Old placeholder margin formula (1 / 0.65) still in code (not in comment)"
    )
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
    src = TEMPLATES.joinpath("recetas.html").read_text(encoding="utf-8")
    for d in ("1 — Muy fácil", "5 — Muy difícil"):
        assert d in src, f"Missing difficulty option: {d}"


def test_receta_form_has_effective_ingredients_panel():
    """`receta_form.html` must show the 'ingredientes efectivos' panel
    (the P3 batch UX that explodes sub-recipes)."""
    src = TEMPLATES.joinpath("receta_form.html").read_text(encoding="utf-8")
    assert "effective-ingredients" in src, "Missing effective-ingredients panel"
    assert "merged_count" in src, "Missing merged_count badge (N× sumadas)"


def test_cliente_nuevo_inline_form():
    """`clientes.html` must have an inline `nuevo cliente` form (not a separate page)."""
    src = TEMPLATES.joinpath("clientes.html").read_text(encoding="utf-8")
    assert "inline-new-client" in src, "Missing inline new-client form anchor"
    # The new-cliente button
    assert "nuevo-cliente-btn" in src, "Missing nuevo-cliente button"


def test_producto_detalle_shows_recipe_and_prices():
    """`producto_detalle.html` must show the product's recipe (if any) and prices."""
    src = TEMPLATES.joinpath("producto_detalle.html").read_text(encoding="utf-8")
    assert "Receta" in src or "receta" in src, "Missing recipe section"
    assert "Precio" in src or "precio" in src, "Missing price section"


def _slice(src: str, start: str, end: str, from_idx: int = 0) -> str:
    begin = src.find(start, from_idx)
    assert begin >= 0, f"Missing {start!r}"
    finish = src.find(end, begin)
    assert finish > begin, f"Missing {end!r} after {start!r}"
    return src[begin:finish]


def test_productos_list_is_name_price_and_availability():
    """L1 is Nombre, Precio venta, Disp., and Editar.

    Importar CSV / Exportar CSV stay inside Más (exactly one Importar).
    Tag, category, margen, disponibilidad, and receta sit under Filtros.
    Parked columns and the star / Ver actions sit under Ver detalles.
    Costo and Margen keep a real sort link the list sorter already uses.
    """
    src = TEMPLATES.joinpath("productos.html").read_text(encoding="utf-8")
    header = src[: src.find('class="inv-toolbar"')]
    assert "Nuevo producto" in header
    assert header.find("Nuevo producto") < header.find("<summary>Más</summary>")
    mas = header.find("<summary>Más</summary>")
    assert header.find('href="/productos/importar"') > mas
    assert header.find('href="/productos/export.csv"') > mas
    assert src.count('href="/productos/importar"') == 1

    filtros = src.find("<summary>Filtros</summary>")
    assert filtros > 0
    assert src.find('name="q"') < filtros
    for field in ("tag", "category", "margen", "disponibles", "has_recipe"):
        assert src.find(f'name="{field}"') > filtros, field

    table = src.find("<table")
    thead = _slice(src, "<thead>", "</thead>", table)
    for label in ("Nombre", "Precio venta", "Disp.", "Editar", "Ver detalles"):
        assert label in thead, label
    assert 'm.sort_th("Nombre"' in thead
    assert 'm.sort_th("Precio venta"' in thead
    for parked in (
        "SKU",
        "Porción",
        "Mayorista",
        "Prime Cost",
        "% Costo",
        "Costo act.",
        "Producido",
    ):
        assert parked not in thead, parked
        assert parked in src
    assert 'm.sort_th("Costo"' not in thead
    assert 'm.sort_th("Margen"' not in thead

    tbody = _slice(src, "<tbody>", "</tbody>", table)
    details = tbody.find("<summary>Ver detalles</summary>")
    assert details > 0
    assert 'name="selected"' in tbody[:details]
    assert tbody.find("/editar") < details
    parked = tbody[details:]
    assert 'm.sort_th("Costo"' in parked
    assert 'm.sort_th("Margen"' in parked
    assert "<a href=" in parked
    for label in (
        "SKU",
        "Porción",
        "Mayorista",
        "Receta",
        "Margen %",
        "Prime Cost",
        "% Costo",
        "Costo act.",
        "Producido",
    ):
        assert label in parked, label
    assert "/favorito" in parked
    assert 'href="/productos/{{ p.id }}"' in parked
    assert "bulk-edit-modal" in src
    assert 'id="select-all"' in src
    assert "column-visibility-panel" in src


def test_clientes_list_is_name_phone_and_tier():
    """L1 is Nombre, Teléfono, and Nivel. Nuevo cliente is the primary action.

    Exportar CSV and Ver duplicados live in Más. Visitas, gasto, puntos,
    última compra, suscripción, and + Pedido stay under Ver detalles, with
    the same ?sort= links the directory already understands.
    """
    src = TEMPLATES.joinpath("clientes.html").read_text(encoding="utf-8")
    assert src.find("Nuevo cliente") < src.find("<summary>Más</summary>")
    mas = src.find("<summary>Más</summary>")
    panel_end = src.find("</details>", mas)
    panel = src[mas:panel_end]
    assert "Exportar CSV" in panel
    assert 'data-testid="link-duplicados"' in panel
    assert 'href="/clientes/duplicados"' in panel
    assert "nuevo-cliente-btn" in src
    assert "inline-new-client" in src

    table = src.find("<table")
    thead = _slice(src, "<thead>", "</thead>", table)
    for label in ("Nombre", "Teléfono", "Nivel", "Ver detalles"):
        assert label in thead, label
    assert "cliente_sort(" in thead
    for parked in ("Visitas", "Gasto total", "Puntos", "Última compra", "Sub · Ped", "Registrado"):
        assert parked not in thead, parked
        assert parked in src
    for key in ("n_sales", "lifetime_spend_gs", "points", "last_sale_at"):
        assert key not in thead, key

    tbody = _slice(src, "<tbody>", "</tbody>", table)
    details = tbody.find("<summary>Ver detalles</summary>")
    assert details > 0
    parked = tbody[details:]
    for key in ("n_sales", "lifetime_spend_gs", "points", "last_sale_at"):
        assert f'cliente_sort("{key}"' in parked, key
    macro = _slice(src, "{% macro cliente_sort", "{% endmacro %}")
    assert '<a href="?sort=' in macro
    assert "data-sort-key" not in macro
    for label in ("Visitas", "Gasto total", "Puntos", "Última compra", "Sub · Ped", "Registrado"):
        assert label in parked, label
    assert 'href="/clientes/{{ c.id }}"' in parked
    assert "/pedidos/nuevo?customer_id={{ c.id }}" in parked
    assert "+ Pedido" in parked
    assert "Nunca compró" in parked
    assert 'id="select-all-clients"' in src
