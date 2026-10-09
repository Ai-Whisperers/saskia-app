"""app/routers/menus.py — WP-4.2: menú ejecutivo (ABM mínimo).

GET  /menus            → lista activos + form crear (nombre, precio,
                         productos con qty) + desactivar
POST /menus/nuevo      → crea menú + items (form: name, price_gs,
                         prod_<id> checkboxes + qty_<id>)
POST /menus/{id}/off   → desactivar (soft)

El POS ya vende menús vía /ventas/nueva/multi items=[{menu_id, qty}]
(expansión en app/rms/menu_ejecutivo.expand_menu_items).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import require_login_or_disabled as require_login
from app.rms.csrf import verify_form_csrf
from app.rms.dependencies import get_session
from app.rms.observability import record_audit
from app.rms.rate_limit import is_write_rate_limited
from app.services.template_render import render


def _fmt(v: int | None) -> str:
    return f"Gs. {v:,.0f}".replace(",", ".") if v is not None else "—"


router = APIRouter(
    prefix="/menus",
    tags=["menus"],
    dependencies=[Depends(require_login)],
)


@router.get("", response_class=HTMLResponse)
async def menus_home(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    from app.rms.menu_ejecutivo import menus_with_items
    from app.rms.models_legacy import Product

    menus = menus_with_items(session)
    products = (
        session.query(Product).filter(Product.is_available.is_(True)).order_by(Product.name).all()
    )
    return render(
        request,
        "menus.html",
        {
            "menus": menus,
            "products": [{"id": p.id, "name": p.name} for p in products],
            "money": _fmt,
        },
    )


@router.post("/nuevo")
async def menu_create(
    request: Request,
    session: Session = Depends(get_session),
    name: str = Form(...),
    price_gs: int = Form(...),
) -> RedirectResponse:
    await verify_form_csrf(request)
    if is_write_rate_limited(request):
        from fastapi import HTTPException

        raise HTTPException(status_code=429, detail="Demasiadas escritas; probá en un momento")
    form = await request.form()
    from app.rms.models_legacy import Menu, MenuItem

    picked: list[tuple[int, float]] = []
    for key, val in form.multi_items():
        if key.startswith("prod_") and str(val) == "on":
            pid = int(key.removeprefix("prod_"))
            qty_raw = form.get(f"qty_{pid}")
            try:
                qty = float(qty_raw) if qty_raw else 1.0
            except (TypeError, ValueError):
                qty = 1.0
            picked.append((pid, max(0.01, qty)))
    if not name.strip() or price_gs <= 0 or not picked:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Nombre, precio y ≥1 producto")

    menu = Menu(name=name.strip(), price_gs=int(price_gs), active=True)
    session.add(menu)
    session.flush()
    for pid, qty in picked:
        session.add(MenuItem(menu_id=menu.id, product_id=pid, qty=qty))
    record_audit(
        request,
        session=session,
        action="menu_create",
        target_type="menu",
        target_id=menu.id,
        detail={"name": menu.name, "price_gs": menu.price_gs, "items": len(picked)},
    )
    session.commit()
    return RedirectResponse("/menus", status_code=303)


@router.post("/{menu_id}/off")
async def menu_deactivate(
    request: Request,
    menu_id: int,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    await verify_form_csrf(request)
    if is_write_rate_limited(request):
        from fastapi import HTTPException

        raise HTTPException(status_code=429, detail="Demasiadas escritas; probá en un momento")
    from app.rms.models_legacy import Menu

    menu = session.get(Menu, menu_id)
    if menu is not None:
        menu.active = False
        record_audit(
            request,
            session=session,
            action="menu_deactivate",
            target_type="menu",
            target_id=menu_id,
            detail={"name": menu.name},
        )
        session.commit()
    return RedirectResponse("/menus", status_code=303)
