"""app/rms/nav.py — Single Source of Truth for navigation, breadcrumbs,
status labels and filter specs (redesign SSOT layer, 2026-09-26).

Everything that renders "where am I / where can I go / what state is this"
reads from these tables:
  - sidebar (base.html)          <- NAV_GROUPS
  - breadcrumbs (page_header)    <- CRUMBS + CRUMB_OVERRIDES
  - "Nuevo" menu (topbar)        <- CREATE_ACTIONS
  - Cmd-K palette (app.js)       <- NAV_GROUPS + CREATE_ACTIONS
  - status pills (status_pill)   <- STATUS_MAP
  - user guide TOC               <- NAV_GROUPS

RULE: never hardcode a nav label, crumb, or status string in a template.
Add/fix it here; tests assert consistency.
"""

from __future__ import annotations

# ── SS-1: navigation ──────────────────────────────────────────────────
# (route, label, icon, sub?)  — order matters; groups of ≤7.
NAV_GROUPS: list[tuple[str, list[dict]]] = [
    (
        "Operación",
        [
            {"route": "/", "label": "Inicio", "icon": "icon-home", "exact": True},
            {"route": "/ventas", "label": "Ventas", "icon": "icon-sale"},
            # SASKIA-MIG-2: pre-shift session gate. /caja was orphaned
            # (no sidebar entry) — without it the cashier had no path
            # to open the arqueo de caja X/Z that /ventas depends on.
            # Placed in the same group as Ventas (operator daily flow).
            {"route": "/caja", "label": "Caja", "icon": "icon-cash"},
            {"route": "/pedidos", "label": "Pedidos", "icon": "icon-box"},
            {"route": "/produccion", "label": "Producción", "icon": "icon-production"},
            # /produccion/manana is intentionally NOT in the sidebar — surfaced as a
            # button on /produccion and / instead (see produccion.html + inicio.html).
            {"route": "/eod", "label": "Cierre del día", "icon": "icon-close"},
        ],
    ),
    (
        "Catálogo",
        [
            {"route": "/productos", "label": "Productos", "icon": "icon-box"},
            {"route": "/recetas", "label": "Recetas", "icon": "icon-recipe"},
            {"route": "/inventario", "label": "Inventario", "icon": "icon-inventory"},
            {"route": "/merma", "label": "Merma", "icon": "icon-waste"},
        ],
    ),
    (
        "Compras",
        [
            {"route": "/reorder", "label": "Reponer", "icon": "icon-reorder"},
            {"route": "/shopping-list", "label": "Lista de compras", "icon": "icon-list"},
            {"route": "/suppliers", "label": "Proveedores", "icon": "icon-supplier"},
            {"route": "/wishlist", "label": "Equipamiento", "icon": "icon-wrench"},
        ],
    ),
    (
        "Ventas y clientes",
        [
            {"route": "/clientes", "label": "Clientes", "icon": "icon-customer"},
            {"route": "/suscripciones", "label": "Suscripciones", "icon": "icon-customer"},
        ],
    ),
    (
        "Análisis y Reportes",
        [
            {"route": "/reportes", "label": "Reportes", "icon": "icon-report"},
            {"route": "/analisis", "label": "Análisis", "icon": "icon-chart"},
            {"route": "/pricing", "label": "Precios por canal", "icon": "icon-tag", "sub": True},
            {
                "route": "/vs-mercado",
                "label": "Precios vs mercado",
                "icon": "icon-tag",
                "sub": True,
            },
        ],
    ),
    (
        "Dashboard",
        [
            {"route": "/dashboard", "label": "KPIs mensuales", "icon": "icon-report"},
        ],
    ),
    (
        "Finanzas",
        [
            {"route": "/bank", "label": "Banco", "icon": "icon-bank"},
            {"route": "/riesgos", "label": "Riesgos", "icon": "icon-warn"},
        ],
    ),
    (
        "Sistema",
        [
            {"route": "/settings", "label": "Configuración", "icon": "icon-settings"},
            {"route": "/users", "label": "Usuarios", "icon": "icon-user"},
            {"route": "/excel", "label": "Excel", "icon": "icon-excel"},
            {"route": "/auditoria", "label": "Auditoría", "icon": "icon-list"},
            {"route": "/guia", "label": "Guía", "icon": "icon-help"},
        ],
    ),
]

NAV_INDEX: dict[str, dict] = {
    item["route"]: {**item, "group": group} for group, items in NAV_GROUPS for item in items
}

# ── SS-2: breadcrumbs ─────────────────────────────────────────────────
# path prefix -> ordered Spanish crumbs [(label, href_or_None), ...]
# None href = current page (last crumb). Entity pages use {entity} slot
# filled by the page at render time.
CRUMBS: dict[str, list[tuple[str, str | None]]] = {
    "/": [("Inicio", None)],
    "/ventas": [("Inicio", "/"), ("Ventas", None)],
    "/ventas/historial": [("Inicio", "/"), ("Ventas", "/ventas"), ("Historial", None)],
    "/ventas/nueva": [("Inicio", "/"), ("Ventas", "/ventas"), ("Nueva venta", None)],
    "/pedidos": [("Inicio", "/"), ("Pedidos", None)],
    "/pedidos/nuevo": [("Inicio", "/"), ("Pedidos", "/pedidos"), ("Nuevo pedido", None)],
    "/pedidos/board": [("Inicio", "/"), ("Pedidos", "/pedidos"), ("Cocina (KDS)", None)],
    "/produccion": [("Inicio", "/"), ("Producción", None)],
    "/produccion-planner": [("Inicio", "/"), ("Producción", "/produccion"), ("Planificador", None)],
    "/produccion/accuracy": [("Inicio", "/"), ("Producción", "/produccion"), ("Precisión", None)],
    "/eod": [("Inicio", "/"), ("Cierre del día", None)],
    "/productos": [("Inicio", "/"), ("Productos", None)],
    "/productos/nuevo": [("Inicio", "/"), ("Productos", "/productos"), ("Nuevo", None)],
    "/recetas": [("Inicio", "/"), ("Recetas", None)],
    "/recetas/nueva": [("Inicio", "/"), ("Recetas", "/recetas"), ("Nueva", None)],
    "/inventario": [("Inicio", "/"), ("Inventario", None)],
    "/inventario/nuevo": [("Inicio", "/"), ("Inventario", "/inventario"), ("Nuevo", None)],
    "/merma": [("Inicio", "/"), ("Merma", None)],
    "/reorder": [("Inicio", "/"), ("Reponer", None)],
    "/shopping-list": [("Inicio", "/"), ("Compras", None), ("Lista de compras", None)],
    "/suppliers": [("Inicio", "/"), ("Proveedores", None)],
    "/suppliers/nuevo": [("Inicio", "/"), ("Proveedores", "/proveedores"), ("Nuevo", None)],
    "/proveedores": [("Inicio", "/"), ("Proveedores", None)],
    "/wishlist": [("Inicio", "/"), ("Equipamiento", None)],
    "/clientes": [("Inicio", "/"), ("Clientes", None)],
    "/clientes/nuevo": [("Inicio", "/"), ("Clientes", "/clientes"), ("Nuevo", None)],
    "/suscripciones": [("Inicio", "/"), ("Suscripciones", None)],
    "/suscripciones/nuevo": [("Inicio", "/"), ("Suscripciones", "/suscripciones"), ("Nueva", None)],
    "/reportes": [("Inicio", "/"), ("Reportes", None)],
    "/analisis": [("Inicio", "/"), ("Análisis", None)],
    "/dashboard": [("Inicio", "/"), ("KPIs mensuales", None)],
    "/pricing": [("Inicio", "/"), ("Precios por canal", None)],
    "/vs-mercado": [("Inicio", "/"), ("Precios vs mercado", None)],
    "/bank": [("Inicio", "/"), ("Banco", None)],
    "/riesgos": [("Inicio", "/"), ("Riesgos", None)],
    "/settings": [("Inicio", "/"), ("Configuración", None)],
    "/users": [("Inicio", "/"), ("Usuarios", None)],
    "/excel": [("Inicio", "/"), ("Excel", None)],
    "/auditoria": [("Inicio", "/"), ("Auditoría", None)],
    "/auditoria/analytics": [("Inicio", "/"), ("Auditoría", "/auditoria"), ("Analítica", None)],
    "/guia": [("Inicio", "/"), ("Guía", None)],
    "/ops": [("Inicio", "/"), ("Sistema", None), ("Estado operativo", None)],
}

# Entity/detail routes: prefix -> (parent_label, parent_href, entity_fmt)
# e.g. "/clientes/1" -> ("Clientes", "/clientes", "{name}")
ENTITY_CRUMBS: dict[str, tuple[str, str, str]] = {
    "/clientes/": ("Clientes", "/clientes", "{name}"),
    "/productos/": ("Productos", "/productos", "{name}"),
    "/recetas/": ("Recetas", "/recetas", "{name}"),
    "/inventario/": ("Inventario", "/inventario", "{name}"),
    "/pedidos/": ("Pedidos", "/pedidos", "Pedido #{id}"),
    "/suppliers/": ("Proveedores", "/proveedores", "{name}"),
    "/ventas/": ("Ventas", "/ventas/historial", "Venta #{id}"),
    "/suscripciones/": ("Suscripciones", "/suscripciones", "Suscripción #{id}"),
}


def crumbs_for(path: str, entity_name: str | None = None) -> list[tuple[str, str | None]]:
    """Return Spanish crumbs for a request path.

    Exact match wins; then ENTITY_CRUMBS prefixes (strip sub-actions like
    /editar, /movimientos and append the Spanish action label).
    """
    if path in CRUMBS:
        return list(CRUMBS[path])
    ACTION_ES: dict[str, str] = {
        "editar": "Editar",
        "nuevo": "Nuevo",
        "movimientos": "Movimientos",
        "variantes": "Variantes",
        "board": "Cocina",
        "detalle": "Detalle",
        "recibo": "Recibo",
        "kardex": "Kardex",
        "historial": "Historial",
        "duplicate": "Duplicar",
        "crear-producto": "Crear producto",
        "set-photo": "Foto",
        "stock-preview": "Vista de stock",
        "compras": "Compras",
    }
    for prefix, (parent_label, parent_href, fmt) in ENTITY_CRUMBS.items():
        if path.startswith(prefix):
            rest = path[len(prefix) :].strip("/").split("/")
            if not rest:
                continue
            try:
                entity_id = rest[0]
            except IndexError:
                continue
            crumbs: list[tuple[str, str | None]] = [
                ("Inicio", "/"),
                (parent_label, parent_href),
                (fmt.format(name=entity_name or f"#{entity_id}", id=entity_id), None),
            ]
            if len(rest) > 1 and rest[-1] in ACTION_ES:
                crumbs[-1] = (
                    fmt.format(name=entity_name or f"#{entity_id}", id=entity_id),
                    parent_href,
                )
                crumbs.append((ACTION_ES[rest[-1]], None))
            return crumbs
    return [("Inicio", "/")]


# ── SS-3: status/enum labels ──────────────────────────────────────────
# enum value -> (Spanish label, severity)  sev ∈ ok/info/warn/danger/neutral
STATUS_MAP: dict[str, tuple[str, str]] = {
    # pedido lifecycle
    "pending": ("Pendiente", "warn"),
    "confirmed": ("Confirmado", "info"),
    "in_production": ("En producción", "info"),
    "ready": ("Listo", "ok"),
    "delivered": ("Entregado", "ok"),
    "cancelled": ("Cancelado", "neutral"),
    # loyalty tiers
    "bronze": ("Bronce", "neutral"),
    "silver": ("Plata", "info"),
    "gold": ("Oro", "warn"),
    # risk
    "activo": ("Activo", "warn"),
    "mitigado": ("Mitigado", "info"),
    "resuelto": ("Resuelto", "ok"),
    # stock states
    "optimo": ("Óptimo", "ok"),
    "justo": ("Justo", "warn"),
    "bajo_minimo": ("Bajo mínimo", "warn"),
    "critico": ("Crítico", "danger"),
    "agotado": ("Agotado", "danger"),
    # generic
    "activo_prod": ("Activo", "ok"),
    "inactivo": ("Inactivo", "neutral"),
}


def status_es(value: str) -> tuple[str, str]:
    """Enum → (label_es, severity); unknown values pass through neutral."""
    return STATUS_MAP.get(value, (value.replace("_", " ").capitalize(), "neutral"))


# ── Nuevo menu (topbar create actions) ────────────────────────────────
CREATE_ACTIONS: list[tuple[str, str]] = [
    ("Venta", "/ventas"),
    ("Pedido", "/pedidos/nuevo"),
    ("Producto", "/productos/nuevo"),
    ("Receta", "/recetas/nueva"),
    ("Ingrediente", "/inventario/nuevo"),
    ("Cliente", "/clientes/nuevo"),
    ("Proveedor", "/suppliers/nuevo"),
    ("Merma", "/merma"),
]


__all__ = [
    "CREATE_ACTIONS",
    "CRUMBS",
    "ENTITY_CRUMBS",
    "NAV_GROUPS",
    "NAV_INDEX",
    "STATUS_MAP",
    "crumbs_for",
    "status_es",
]
