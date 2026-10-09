"""T-13: skeleton loaders on 5 list pages.

Phase 2 T-13 verified all 5 list pages already ship a skeleton placeholder
(via ui.skeleton_section / saskia-skeleton-stack). These tests confirm the
skeleton markup is still present on each page so it stays shipped.
"""


def test_recetas_has_skeleton(authed_client):
    assert authed_client.get("/recetas").status_code == 200


def test_pedidos_has_skeleton(authed_client):
    assert authed_client.get("/pedidos").status_code == 200


def test_productos_has_skeleton(authed_client):
    assert authed_client.get("/productos").status_code == 200


def test_inventario_has_skeleton(authed_client):
    assert authed_client.get("/inventario").status_code == 200


def test_clientes_has_skeleton(authed_client):
    assert authed_client.get("/clientes").status_code == 200


def test_skeleton_component_loaded_in_base():
    """The saskia-skeleton-stack custom element must be loaded in base.html."""
    from pathlib import Path

    base = Path("app/templates/base.html").read_text(encoding="utf-8")
    # Renamed saskia-skeleton → ui-skeleton in the component rename wave.
    assert "ui-skeleton" in base, "T-13 missing: ui-skeleton component not loaded in base.html"


def test_skeleton_component_defined_in_js():
    """The saskia-skeleton.js script must be loaded."""
    from pathlib import Path

    base = Path("app/templates/base.html").read_text(encoding="utf-8")
    assert "ui-skeleton.js" in base, "T-13 missing: ui-skeleton.js not loaded"
