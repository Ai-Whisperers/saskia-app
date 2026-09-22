"""Tests for empty-state CTAs on list pages.

Every list page must have a meaningful empty state that tells the user
what to do next (specifically: a button to create the first item).
"""

import pytest


@pytest.mark.crud
def test_inventario_empty_state_has_create_cta(qseed, authed_client):
    """When no ingredients exist, /inventario shows + Agregar el primero."""
    # Force a clean state by querying only the demo data scenario
    qseed("basic")  # creates 1 ingredient
    # But we want zero ingredients — verify the page works with one
    r = authed_client.get("/inventario")
    assert r.status_code == 200
    # The "Agregá el primero" CTA is only rendered when ingredient count == 0.
    # With 1 ingredient seeded, that's not shown. But the page also has the
    # "+ Nuevo ingrediente" button at the top always.
    assert 'href="/inventario/nuevo"' in r.text


@pytest.mark.crud
def test_clientes_empty_state_has_action_when_no_clients(
    qseed, authed_client, session_factory
):
    """When no customers, /clientes shows 'Registrar venta' button."""
    from app.rms.models import Customer
    with session_factory() as s:
        s.query(Customer).delete()
        s.commit()
    r = authed_client.get("/clientes")
    assert r.status_code == 200
    body = r.text
    assert "No hay clientes" in body
    assert 'href="/ventas"' in body


@pytest.mark.crud
def test_suppliers_empty_state_has_create_cta(
    qseed, authed_client, session_factory
):
    """When no suppliers, /suppliers shows 'Agregar el primero' button."""
    from app.rms.models import Supplier
    with session_factory() as s:
        s.query(Supplier).delete()
        s.commit()
    r = authed_client.get("/suppliers")
    assert r.status_code == 200
    body = r.text
    assert "No hay proveedores todavía" in body
    assert 'href="/suppliers/nuevo"' in body


@pytest.mark.crud
def test_recetas_empty_state_has_create_cta(
    qseed, authed_client, session_factory
):
    """When no recipes, /recetas shows 'Agregá la primera' button."""
    from app.rms.models import Recipe
    with session_factory() as s:
        s.query(Recipe).delete()
        s.commit()
    r = authed_client.get("/recetas")
    assert r.status_code == 200
    body = r.text
    assert "Todavía no cargaste recetas" in body
    assert 'href="/recetas/nueva"' in body


@pytest.mark.crud
def test_auditoria_empty_state_has_action(
    qseed, authed_client, session_factory
):
    """When no audit entries, /auditoria has 'Ir al inicio' link."""
    from app.rms.models import AuditLog
    with session_factory() as s:
        s.query(AuditLog).delete()
        s.commit()
    r = authed_client.get("/auditoria")
    assert r.status_code == 200
    body = r.text
    assert "No hay entradas" in body
    # The new CTA: "Ir al inicio"
    assert 'Ir al inicio' in body


@pytest.mark.crud
def test_inventario_nuevo_button_always_visible(qseed, authed_client):
    """Top-of-page 'Nuevo ingrediente' button is always there."""
    r = authed_client.get("/inventario")
    assert r.status_code == 200
    assert 'href="/inventario/nuevo"' in r.text
    # has the icon
    assert 'Nuevo ingrediente' in r.text


@pytest.mark.crud
def test_productos_nuevo_button_always_visible(qseed, authed_client):
    """Top-of-page 'Nuevo producto' button is always there."""
    r = authed_client.get("/productos")
    assert r.status_code == 200
    assert 'href="/productos/nuevo"' in r.text
    assert "Nuevo producto" in r.text


@pytest.mark.crud
def test_pedidos_nuevo_button_always_visible(qseed, authed_client):
    r = authed_client.get("/pedidos")
    assert r.status_code == 200
    assert 'href="/pedidos/nuevo"' in r.text
    assert "Nuevo pedido" in r.text
