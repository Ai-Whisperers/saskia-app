"""Station shell: four workflows, one login.

The owner picks a station after every login and can switch.
A staff role is pinned to one station and cannot open the others.

Gerencia is the single management workspace (the old Overview and
Escritorio). Sale price is set there. The price paid for an ingredient
is typed in Inventario. Cocina works in quantities and does not type a price.
"""

from __future__ import annotations

from dataclasses import dataclass

SESSION_STATION = "station"
SESSION_LOCKED = "station_locked"
SESSION_ROLE = "user_role"

# Roles that already exist on User.role, plus the station names themselves.
_ROLE_TO_STATION = {
    "cashier": "ventas",
    "manager": "gerencia",
    "cocina": "cocina",
    "ventas": "ventas",
    "inventario": "inventario",
    "gerencia": "gerencia",
    # Earlier pins, still accepted so an existing login is not stranded.
    "overview": "gerencia",
    "escritorio": "gerencia",
}
_LEGACY_STATIONS = {"overview": "gerencia", "escritorio": "gerencia"}
_OWNER_ROLES = frozenset({"admin", "owner"})

# Stored on User.role (String(32)). admin stays the owner.
# cashier and manager stay so existing logins keep their pin.
ASSIGNABLE_ROLES: tuple[tuple[str, str], ...] = (
    ("admin", "Administrador"),
    ("cocina", "Cocina"),
    ("ventas", "Ventas"),
    ("inventario", "Inventario"),
    ("gerencia", "Gerencia"),
    ("cashier", "Cajero"),
    ("manager", "Gerente"),
)

# Older role strings still save. They pin to Gerencia and are not offered
# as separate stations.
ACCEPTED_ROLES: tuple[str, ...] = (
    *(value for value, _display in ASSIGNABLE_ROLES),
    "overview",
    "escritorio",
)


@dataclass(frozen=True)
class Station:
    id: str
    label: str
    blurb: str
    home: str
    # Path prefixes this station owns. /eod is shared by cocina and gerencia.
    prefixes: tuple[str, ...]
    exact: tuple[str, ...] = ()
    # Shown on the back of the chooser card.
    features: tuple[str, ...] = ()


STATIONS: dict[str, Station] = {
    "cocina": Station(
        id="cocina",
        label="Cocina",
        blurb="Pesar la tanda, anotar la merma, armar la semana y cerrar las piezas.",
        home="/produccion",
        prefixes=("/recetas", "/produccion", "/merma", "/eod"),
        features=("Producción", "Recetas", "Merma", "Cierre del día"),
    ),
    "ventas": Station(
        id="ventas",
        label="Ventas",
        blurb="Anotar lo que salió hoy por el mostrador.",
        home="/ventas",
        prefixes=("/ventas",),
        features=("Nueva venta", "Productos del mostrador", "Menús ejecutivos"),
    ),
    "inventario": Station(
        id="inventario",
        label="Inventario",
        blurb="Qué queda, a qué precio se compró y qué hay que reponer.",
        home="/inventario",
        prefixes=("/inventario", "/reorder"),
        features=("Stock", "Precio de compra", "Reponer"),
    ),
    "gerencia": Station(
        id="gerencia",
        label="Gerencia",
        blurb="Ver el día y entrar al módulo que haga falta.",
        home="/gerencia",
        prefixes=(
            "/gerencia",
            "/inicio",
            "/productos",
            "/pedidos",
            "/clientes",
            "/suscripciones",
            "/inventario",
            "/reorder",
            "/shopping-list",
            "/suppliers",
            "/excel",
            "/reportes",
            "/settings",
            "/users",
            "/eod",
        ),
        exact=("/",),
        features=(
            "Pedidos",
            "Productos",
            "Clientes",
            "Inventario",
            "Cierre del día",
            "Reportes",
            "Usuarios",
            "Configuración",
            "Excel",
        ),
    ),
}

# Gerencia's menu. The dashboard is the home, not a second item here.
_GERENCIA_NAV: tuple[tuple[str, tuple[dict, ...]], ...] = (
    (
        "Operación",
        (
            {"route": "/pedidos", "label": "Pedidos", "icon": "icon-box"},
            {"route": "/productos", "label": "Productos", "icon": "icon-box"},
            {"route": "/clientes", "label": "Clientes", "icon": "icon-customer"},
            {"route": "/inventario", "label": "Inventario", "icon": "icon-inventory"},
            {"route": "/eod", "label": "Cierre del día", "icon": "icon-close"},
        ),
    ),
    (
        "Análisis",
        ({"route": "/reportes", "label": "Reportes", "icon": "icon-report"},),
    ),
    (
        "Administración",
        (
            {"route": "/users", "label": "Usuarios", "icon": "icon-user"},
            {"route": "/settings", "label": "Configuración", "icon": "icon-settings"},
            {"route": "/excel", "label": "Excel", "icon": "icon-excel"},
        ),
    ),
)

# Screens that are not a station. Hidden once a station is chosen.
_DENIED_PREFIXES = ("/auditoria", "/ops")

# Reachable from every station (help, session, the chooser itself).
_ALWAYS_PREFIXES = ("/puesto", "/logout", "/login", "/guia", "/healthz", "/static", "/favicon")

_CREATE_BY_STATION: dict[str, tuple[tuple[str, str, str], ...]] = {
    "cocina": (("/recetas/nueva", "Receta", "icon-recipe"),),
    "ventas": (("/ventas/nueva", "Venta", "icon-sale"),),
    "inventario": (("/inventario/nuevo", "Ingrediente", "icon-inventory"),),
    "gerencia": (
        ("/productos/nuevo", "Producto", "icon-box"),
        ("/pedidos/nuevo", "Pedido", "icon-box"),
        ("/clientes/nuevo", "Cliente", "icon-customer"),
    ),
}


def canonical_station(station_id: str | None) -> str | None:
    """Map a retired station id onto Gerencia. Unknown ids pass through."""
    if station_id is None:
        return None
    return _LEGACY_STATIONS.get(station_id, station_id)


def is_owner(role: str | None) -> bool:
    """Admin (the single operator) and unknown roles pick any station.

    A known staff role is pinned. Unknown stays owner so the current
    one-login install is not locked out of the chooser.
    """
    if not role or role in _OWNER_ROLES:
        return True
    return role not in _ROLE_TO_STATION


def station_for_role(role: str | None) -> str | None:
    """Pinned station id, or None when the role uses the chooser."""
    if is_owner(role):
        return None
    return _ROLE_TO_STATION[role or ""]


def station_ids() -> list[str]:
    return list(STATIONS)


def get_station(station_id: str) -> Station | None:
    return STATIONS.get(station_id)


def cocina_writes_pieces(station_id: str | None) -> bool:
    """Piece counts are Cocina's. No station keeps the old shared page."""
    return station_id in (None, "", "cocina")


def escritorio_writes_desk(station_id: str | None) -> bool:
    """Cleaning, storage, receipts, and notes are Gerencia's."""
    return canonical_station(station_id) in (None, "", "gerencia")


def hides_prices(station_id: str | None) -> bool:
    """Cocina does not type or show a price. No station keeps today's pages."""
    return station_id == "cocina"


def sets_sale_price(station_id: str | None) -> bool:
    """Gerencia sets the product sale price. No station keeps today's pages."""
    return canonical_station(station_id) in (None, "gerencia")


def sets_purchase_price(station_id: str | None) -> bool:
    """Inventario types what was paid. No station keeps today's pages."""
    return station_id in (None, "inventario")


def _matches(path: str, station: Station) -> bool:
    if path in station.exact:
        return True
    return any(path == prefix or path.startswith(prefix + "/") for prefix in station.prefixes)


def owning_stations(path: str) -> set[str]:
    """Stations that claim this path. Empty means the path is not a station screen."""
    if path.startswith(_ALWAYS_PREFIXES):
        return set()
    return {sid for sid, station in STATIONS.items() if _matches(path, station)}


def path_allowed(station_id: str, path: str) -> bool:
    """True when this station may open the path.

    Unlisted paths (JSON under the page, health, static) stay open so a
    station screen can still load its own data. A screen that belongs to
    another station is refused. Auditoría and Ops belong to none.
    """
    if path.startswith(_DENIED_PREFIXES):
        return False
    if path.startswith(_ALWAYS_PREFIXES):
        return True
    owners = owning_stations(path)
    if not owners:
        return True
    return canonical_station(station_id) in owners


def nav_groups_for(station_id: str, nav_groups: list) -> list[tuple[str, list[dict]]]:
    """One sidebar group: the screens this station owns, in nav-table order."""
    station_id = canonical_station(station_id) or station_id
    if station_id == "gerencia":
        return [(title, [dict(item) for item in items]) for title, items in _GERENCIA_NAV]
    station = STATIONS.get(station_id)
    if station is None:
        return nav_groups
    items: list[dict] = []
    seen: set[str] = set()
    for _group, group_items in nav_groups:
        for item in group_items:
            route = item["route"]
            if route in seen:
                continue
            if station_id in owning_stations(route):
                items.append(item)
                seen.add(route)
    if "/eod" not in seen and station_id == "cocina":
        items.append({"route": "/eod", "label": "Cierre del día", "icon": "icon-close"})
    if not items:
        return []
    return [(station.label, items)]


def create_actions_for(station_id: str) -> list[dict]:
    rows = _CREATE_BY_STATION.get(canonical_station(station_id) or "", ())
    return [{"route": route, "label": label, "icon": icon} for route, label, icon in rows]


def login_destination(role: str | None) -> tuple[str, str | None, bool]:
    """Where a real login lands: (path, station or None, locked)."""
    pinned = station_for_role(role)
    if pinned is None:
        return "/puesto", None, False
    return STATIONS[pinned].home, pinned, True


def apply_login(session: dict, role: str | None) -> str:
    """Write station keys and return the redirect path."""
    path, station, locked = login_destination(role)
    session[SESSION_ROLE] = role or "admin"
    session[SESSION_LOCKED] = locked
    if station is None:
        session.pop(SESSION_STATION, None)
    else:
        session[SESSION_STATION] = station
    return path


def decide(path: str, session: dict, *, auth_disabled: bool, user_present: bool) -> str | None:
    """Gate result: None allows the request. Otherwise 'deny' or 'redirect:<path>'."""
    station = canonical_station(session.get(SESSION_STATION))
    if session.get(SESSION_STATION) not in (None, station) and station:
        session[SESSION_STATION] = station
    locked = bool(session.get(SESSION_LOCKED))

    if auth_disabled and not station:
        return None

    if path.startswith("/puesto"):
        if locked and station:
            return f"redirect:{STATIONS[station].home}"
        return None

    if station:
        if path_allowed(station, path):
            return None
        return "deny"

    if auth_disabled or not user_present:
        return None

    role = session.get(SESSION_ROLE) or "admin"
    pinned = station_for_role(role)
    if pinned is None:
        return "redirect:/puesto"
    session[SESSION_STATION] = pinned
    session[SESSION_LOCKED] = True
    return f"redirect:{STATIONS[pinned].home}"
