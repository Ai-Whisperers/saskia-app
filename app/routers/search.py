"""Global search API — /api/search
Searches across customers, products, orders (pedidos), and recipes.
Used by the Cmd+K global search modal in base.html.

Phase 1B ticket #8: previously each query block silently `pass`ed on
exception. Now they log a warning so a partial-results UI is visible
to ops in the logs (silent partial results were a debugging nightmare).
"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.rms.dependencies import get_session
from app.rms.models import Customer, Pedido, Product, Recipe

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search")
def global_search(
    q: str = Query("", min_length=1, description="Search query"),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Search across all entities: customers, products, pedidos, recipes.
    Returns grouped results with max 6 per category.
    """
    if not q or len(q) < 2:
        return JSONResponse({"customers": [], "products": [], "pedidos": [], "recipes": []})

    pattern = f"%{q}%"
    results = {"customers": [], "products": [], "pedidos": [], "recipes": []}

    # ── Customers ─────────────────────────────────────────────────────────────
    try:
        customers_q = (
            session.query(Customer)
            .filter(
                or_(
                    Customer.name.ilike(pattern),
                    Customer.phone.ilike(pattern),
                    Customer.email.ilike(pattern),
                    Customer.cedula.ilike(pattern),
                )
            )
            .order_by(Customer.name)
            .limit(8)
        )
        for c in customers_q:
            tier_label = ""
            if c.loyalty_points < 5000:
                tier_label = "Bronce"
            elif c.loyalty_points < 20000:
                tier_label = "Plata"
            elif c.loyalty_points < 50000:
                tier_label = "Oro"
            else:
                tier_label = "Platino"
            results["customers"].append({
                "id": c.id,
                "name": c.name or "—",
                "sub": f"{c.phone or 'sin tel'} · {tier_label}",
                "badge": tier_label,
                "badge_class": f"tier-{tier_label.lower()}",
                "url": f"/clientes/{c.id}",
            })
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"global_search: customers query failed: {exc!r}")

    # ── Products ─────────────────────────────────────────────────────────────
    try:
        products_q = (
            session.query(Product)
            .filter(Product.name.ilike(pattern))
            .order_by(Product.name)
            .limit(8)
        )
        for p in products_q:
            price_str = f"Gs. {p.sale_price_gs:,.0f}".replace(",", ".") if p.sale_price_gs else "—"
            results["products"].append({
                "id": p.id,
                "name": p.name,
                "sub": f"{p.portion_label or '—'} · {price_str}",
                "badge": "Con receta" if p.recipe_name else "Sin receta",
                "badge_class": "info" if p.recipe_name else "neutral",
                "url": f"/productos/{p.id}/editar",
            })
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"global_search: products query failed: {exc!r}")

    # ── Pedidos ─────────────────────────────────────────────────────────────
    try:
        pedidos_q = (
            session.query(Pedido)
            .filter(
                or_(
                    Pedido.customer_name.ilike(pattern),
                    Pedido.customer_phone.ilike(pattern),
                )
            )
            .order_by(Pedido.promised_date.desc())
            .limit(8)
        )
        for ped in pedidos_q:
            status_map = {
                "pending": ("Pendiente", "warn"),
                "confirmed": ("Confirmado", "info"),
                "ready": ("Listo", "ok"),
                "fulfilled": ("Entregado", "good"),
                "cancelled": ("Cancelado", "neutral"),
            }
            label, cls = status_map.get(ped.status, (ped.status or "—", "neutral"))
            date_str = ped.promised_date.strftime("%d/%m/%Y") if ped.promised_date else "—"
            results["pedidos"].append({
                "id": ped.id,
                "name": ped.customer_name or "—",
                "sub": f"{date_str} · {ped.channel or '—'} · {label}",
                "badge": label,
                "badge_class": cls,
                "url": f"/pedidos/{ped.id}",
            })
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"global_search: pedidos query failed: {exc!r}")

    # ── Recipes ─────────────────────────────────────────────────────────────
    try:
        recipes_q = (
            session.query(Recipe)
            .filter(Recipe.name.ilike(pattern))
            .order_by(Recipe.name)
            .limit(8)
        )
        for r in recipes_q:
            cost_str = f"Gs. {r.unit_cost_gs:,.0f}".replace(",", ".") if r.unit_cost_gs else "—"
            results["recipes"].append({
                "id": r.id,
                "name": r.name,
                "sub": f"{r.yield_qty} {r.yield_unit or 'porción'} · {cost_str}/porción",
                "badge": "Receta",
                "badge_class": "info",
                "url": f"/recetas/{r.id}/editar",
            })
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"global_search: recipes query failed: {exc!r}")

    return JSONResponse(results)
