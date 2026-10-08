"""Station shell: owner chooses a workflow, staff stay pinned, cocina has no prices."""

from __future__ import annotations

from app.rms.nav import NAV_GROUPS
from app.rms.stations import (
    apply_login,
    decide,
    hides_prices,
    nav_groups_for,
    path_allowed,
    sets_purchase_price,
    sets_sale_price,
)


def test_five_stations_and_price_rules():
    assert hides_prices("cocina") is True
    assert hides_prices("inventario") is False
    assert hides_prices(None) is False
    assert sets_sale_price("escritorio") is True
    assert sets_sale_price("cocina") is False
    assert sets_sale_price("inventario") is False
    assert sets_purchase_price("inventario") is True
    assert sets_purchase_price("cocina") is False
    assert sets_purchase_price("escritorio") is False


def test_gerencia_nav_is_one_menu():
    groups = nav_groups_for("gerencia", NAV_GROUPS)
    titles = [title for title, _items in groups]
    routes = [item["route"] for _title, items in groups for item in items]
    assert titles == ["Operación", "Análisis", "Administración"]
    assert routes == [
        "/pedidos",
        "/productos",
        "/clientes",
        "/inventario",
        "/eod",
        "/reportes",
        "/users",
        "/settings",
        "/excel",
    ]
    assert "/inicio" not in routes
    assert "/ventas" not in routes
    assert path_allowed("gerencia", "/inventario") is True
    assert path_allowed("gerencia", "/ventas") is False
    assert path_allowed("cocina", "/gerencia") is False


def test_cocina_nav_excludes_sales_and_audit():
    groups = nav_groups_for("cocina", NAV_GROUPS)
    routes = [item["route"] for _g, items in groups for item in items]
    assert "/produccion" in routes
    assert "/recetas" in routes
    assert "/merma" in routes
    assert "/eod" in routes
    assert "/ventas" not in routes
    assert "/auditoria" not in routes
    assert "/productos" not in routes
    assert groups[0][0] == "Cocina"


def test_path_lock_refuses_another_station_and_audit():
    assert path_allowed("cocina", "/recetas") is True
    assert path_allowed("cocina", "/ventas") is False
    assert path_allowed("cocina", "/auditoria") is False
    assert path_allowed("cocina", "/ops") is False
    assert path_allowed("inventario", "/reorder") is True
    assert path_allowed("inventario", "/productos") is False
    assert path_allowed("escritorio", "/productos") is True
    assert path_allowed("escritorio", "/eod") is True
    assert path_allowed("cocina", "/eod") is True
    assert path_allowed("overview", "/") is True
    assert path_allowed("ventas", "/") is False
    # A station page can still call an unlisted data path.
    assert path_allowed("cocina", "/api/insights/hoy") is True


def test_owner_login_opens_chooser_staff_login_is_pinned():
    owner = {}
    assert apply_login(owner, "admin") == "/puesto"
    assert "station" not in owner
    assert owner["station_locked"] is False

    cook = {}
    assert apply_login(cook, "cocina") == "/produccion"
    assert cook["station"] == "cocina"
    assert cook["station_locked"] is True

    cashier = {}
    assert apply_login(cashier, "cashier") == "/ventas"
    assert cashier["station_locked"] is True

    manager = {}
    assert apply_login(manager, "manager") == "/gerencia"
    assert manager["station"] == "gerencia"


def test_staff_cannot_open_the_chooser_or_another_screen():
    session = {"station": "cocina", "station_locked": True, "user_role": "cocina"}
    assert decide("/puesto", session, auth_disabled=False, user_present=True) == "redirect:/produccion"
    assert decide("/ventas", session, auth_disabled=False, user_present=True) == "deny"
    assert decide("/produccion", session, auth_disabled=False, user_present=True) is None


def test_owner_without_a_station_is_sent_to_the_chooser():
    session = {"user_role": "admin", "station_locked": False}
    assert decide("/ventas", session, auth_disabled=False, user_present=True) == "redirect:/puesto"
    assert decide("/puesto", session, auth_disabled=False, user_present=True) is None


def test_auth_disabled_without_a_station_keeps_the_current_app():
    assert decide("/ventas", {}, auth_disabled=True, user_present=False) is None


def test_chooser_page_lists_four_stations(client):
    r = client.get("/puesto")
    assert r.status_code == 200
    for label in ("Cocina", "Ventas", "Inventario", "Gerencia"):
        assert label in r.text
    assert "Overview" not in r.text
    assert "Escritorio" not in r.text
    assert "Auditoría" not in r.text
    assert "¿Qué vas a hacer?" in r.text


def _cookie_header(response) -> str:
    """Replay Set-Cookie on the next request.

    The session cookie is Secure (HTTPS_ONLY). The test client talks HTTP
    and will not send a Secure cookie back on its own.
    """
    parts = []
    for key, value in response.headers.multi_items():
        if key.lower() == "set-cookie":
            parts.append(value.split(";", 1)[0])
    return "; ".join(parts)


def test_choosing_cocina_blocks_ventas(client):
    client.get("/puesto")
    chosen = client.post("/puesto", data={"station": "cocina"}, follow_redirects=False)
    assert chosen.status_code == 303
    assert chosen.headers["location"] == "/produccion"
    cookie = _cookie_header(chosen)
    blocked = client.get("/ventas", headers={"cookie": cookie}, follow_redirects=False)
    assert blocked.status_code == 403
    assert "otro puesto" in blocked.text
    allowed = client.get("/recetas", headers={"cookie": cookie}, follow_redirects=False)
    assert allowed.status_code != 403
