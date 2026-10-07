"""app/rms/menu_ejecutivo.py — WP-4.2: menú ejecutivo (combo de venta).

expand_menu_items(session, menu_id, qty) → [(product_id, qty, price_gs)]
— el POS manda items=[{menu_id, qty}] y el backend expande ANTES de
insertar: cada producto descuenta stock/costea por su receta, pero el
PRECIO de la venta es el del menú (no la sumatoria).

Precio: la primera línea lleva el precio completo del menú; las demás
0 — así el total de la venta == price_gs × qty y el recibo lista
"Menú X (incluye A, B, C)".
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.rms.models_legacy import MenuItem

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class MenuNotFound(LookupError):
    """menu_id inexistente, inactivo o sin productos."""


def expand_menu_items(
    session: Session,
    menu_id: int,
    qty: float,
) -> list[tuple[int, float, int]]:
    """Devuelve [(product_id, qty, precio_unitario_gs)].

    El precio completo del menú va en la PRIMERA línea (por unidad de
    menú; el caller lo repite qty veces porque qty ya viene multiplicada
    en la qty de línea).
    """
    from app.rms.models_legacy import Menu

    menu = session.get(Menu, int(menu_id))
    if menu is None or not menu.active:
        raise MenuNotFound(f"menu {menu_id} inexistente o inactivo")
    if qty <= 0:
        raise ValueError("qty debe ser > 0")

    items = (
        session.query(MenuItem)
        .filter(MenuItem.menu_id == menu.id)
        .order_by(MenuItem.id)
        .all()
    )
    if not items:
        raise MenuNotFound(f"menu {menu_id} no tiene productos")

    out: list[tuple[int, float, int]] = []
    for _i, it in enumerate(items):
        unit_price = int(menu.price_gs) if _i == 0 else 0
        out.append((int(it.product_id), float(it.qty) * float(qty), unit_price))
    return out


def menus_with_items(session: Session) -> list[dict[str, Any]]:
    """Lista activa para el POS: {id, name, price_gs, incluye: [nombres]}."""
    from app.rms.models_legacy import Menu, Product

    rows = session.query(Menu).filter(Menu.active.is_(True)).order_by(Menu.name).all()
    out: list[dict[str, Any]] = []
    for m in rows:
        names: list[str] = []
        for it in m.items:
            p = session.get(Product, it.product_id)
            if p is not None:
                names.append(p.name)
        out.append(
            {"id": m.id, "name": m.name, "price_gs": int(m.price_gs), "incluye": names}
        )
    return out
