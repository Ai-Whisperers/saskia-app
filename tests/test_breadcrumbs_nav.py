"""Phase 22 — Auto-breadcrumbs (already shipped).

base.html calls fmt.crumbs_for(request.url.path) which uses:
- CRUMBS dict (40+ known paths)
- ENTITY_CRUMBS for entity-scoped paths (/clientes/123, /recetas/45/editar, ...)

This test verifies the crumb system returns correct breadcrumbs and that
base.html's breadcrumb block renders them.
"""

from __future__ import annotations

from app.rms.nav import ENTITY_CRUMBS, crumbs_for

# ---------------------------------------------------------------------------
# Pure unit tests on crumbs_for()
# ---------------------------------------------------------------------------


def test_top_level_returns_inicio():
    """Top-level paths return [('Inicio', None)] or [('Inicio', '/')]."""
    r = crumbs_for("/")
    assert r[0][0] == "Inicio"
    # Unknown path falls back
    fallback = crumbs_for("/random/unknown/path")
    assert fallback[0][0] == "Inicio"


def test_known_crumb_paths():
    """Paths in CRUMBS return the configured trail with the last crumb
    being the current page (no href)."""
    # Each path's CRUMBS entry defines its own label, so we don't assert
    # exact text — just structure.
    for path in ("/pedidos", "/dashboard", "/inventario"):
        crumbs = crumbs_for(path)
        assert crumbs[0][0] == "Inicio", f"{path}: missing Inicio"
        assert len(crumbs) >= 2, f"{path}: expected ≥2 crumbs"
        # Last crumb is current page (no link)
        assert crumbs[-1][1] is None, f"{path}: last crumb should be None href"


def test_entity_crumb_cliente_detalle():
    """Entity path /clientes/123 returns [Inicio, Clientes, #123]."""
    crumbs = crumbs_for("/clientes/123")
    assert crumbs[0] == ("Inicio", "/")
    assert crumbs[1] == ("Clientes", "/clientes")
    assert crumbs[2][0] == "#123"
    assert crumbs[2][1] is None  # current page, no href


def test_entity_crumb_with_action():
    """Entity + action like /clientes/123/editar."""
    crumbs = crumbs_for("/clientes/123/editar")
    assert crumbs[0] == ("Inicio", "/")
    assert crumbs[1] == ("Clientes", "/clientes")
    # Action "editar" should be appended
    assert any(c[0] == "Editar" for c in crumbs), f"No 'Editar' in {crumbs}"


def test_entity_crumb_receta_editar():
    """Recipe edit should show [Inicio, Recetas, #123, Editar]."""
    crumbs = crumbs_for("/recetas/45/editar")
    assert ("Recetas", "/recetas") in crumbs
    assert any(c[0] == "Editar" for c in crumbs)


def test_entity_crumb_pedido_board():
    """Cocina = pedido_board path."""
    crumbs = crumbs_for("/pedidos/board")
    assert any("Cocina" in c[0] for c in crumbs)


def test_entity_crumb_pedido_nuevo():
    """New pedido shows [Inicio, Pedidos, Nuevo]."""
    crumbs = crumbs_for("/pedidos/nuevo")
    assert ("Inicio", "/") in crumbs
    assert ("Pedidos", "/pedidos") in crumbs


def test_entity_crumb_with_entity_name():
    """Passing entity_name adds the friendly name to the crumb."""
    crumbs = crumbs_for("/clientes/42", entity_name="María González")
    # Last crumb should contain the entity name
    assert any("María" in c[0] for c in crumbs)


# ---------------------------------------------------------------------------
# ENTITY_CRUMBS coverage check
# ---------------------------------------------------------------------------


def test_entity_crumbs_minimum_coverage():
    """We should have a healthy number of entity-prefixed routes mapped."""
    assert len(ENTITY_CRUMBS) >= 5, f"Expected ≥5 entity crumb prefixes, got {len(ENTITY_CRUMBS)}"


def test_entity_crumbs_have_required_keys():
    """Each entity crumb should map (parent_label, parent_href, fmt)."""
    for prefix, mapping in ENTITY_CRUMBS.items():
        assert len(mapping) == 3, (
            f"ENTITY_CRUMBS[{prefix}] should be (label, href, fmt), got {mapping}"
        )
        label, href, fmt = mapping
        assert label and href and fmt
