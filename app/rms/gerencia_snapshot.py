"""The few facts Gerencia shows on its landing page.

Counts and one money total. The modules behind the menu keep the detail.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.config import ASUNCION_TZ
from app.rms.eod_closed import eod_is_day_closed
from app.rms.models import Pedido, Sale
from app.rms.money import to_int_gs
from app.rms.reorder import compute_reorder_list
from app.rms.workflow import fresh_eod_checklist

_OPEN_ORDER = ("pending", "confirmed", "ready")


def snapshot(session: Session) -> dict:
    """Today's operating picture. Each query is independent and fail-soft."""
    today = datetime.now(ASUNCION_TZ).date()
    sales_gs = _sales_today(session, today)
    open_orders = _open_orders(session)
    kitchen_done, kitchen_planned = _kitchen(session, today)
    low_stock = _low_stock(session)
    close_done, close_total, closed = _closing(session, today)
    notices = _notices(session, today, low_stock_count=low_stock, open_orders=open_orders)
    return {
        "sales_gs": sales_gs,
        "open_orders": open_orders,
        "kitchen_done": kitchen_done,
        "kitchen_planned": kitchen_planned,
        "low_stock": low_stock,
        "close_done": close_done,
        "close_total": close_total,
        "day_closed": closed,
        "notices": notices,
    }


def _sales_today(session: Session, today: date) -> int:
    start = datetime.combine(today, datetime.min.time()).replace(tzinfo=ASUNCION_TZ)
    end = start + timedelta(days=1)
    rows = session.scalars(
        select(Sale).where(
            Sale.sold_at.isnot(None),
            Sale.voided_at.is_(None),
            Sale.sold_at >= start,
            Sale.sold_at < end,
        )
    ).all()
    total = Decimal("0")
    for sale in rows:
        total += Decimal(str(sale.qty)) * Decimal(str(sale.unit_price_gs))
    return to_int_gs(total)


def _open_orders(session: Session) -> int:
    rows = session.scalars(select(Pedido.id).where(Pedido.status.in_(_OPEN_ORDER))).all()
    return len(rows)


def _kitchen(session: Session, today: date) -> tuple[int, int]:
    try:
        from app.rms.eod_completions import completions_for_date
        from app.rms.production import plan_production

        plan = plan_production(session, for_date=today)
        done_map = completions_for_date(session, today)
    except Exception:  # noqa: BLE001 — the landing page must still render
        return 0, 0
    rows = getattr(plan, "rows", None) or []
    planned = len(rows)
    done = 0
    for row in rows:
        recorded = done_map.get(row.product_id)
        if recorded is not None and recorded + 1e-9 >= float(row.qty_to_produce):
            done += 1
    return done, planned


def _low_stock(session: Session) -> int:
    try:
        return len(compute_reorder_list(session))
    except Exception:  # noqa: BLE001
        return 0


def _closing(session: Session, today: date) -> tuple[int, int, bool]:
    items = fresh_eod_checklist()
    total = len(items)
    try:
        closed = eod_is_day_closed(session, today)
    except Exception:  # noqa: BLE001
        closed = False
    if closed:
        return total, total, True
    from app.rms.models import AppMeta

    prefix = f"eod_check_{today.isoformat()}_"
    saved = session.scalars(select(AppMeta).where(AppMeta.key.like(f"{prefix}%"))).all()
    done = sum(1 for row in saved if row.value == "1")
    return done, total, False


def _notices(
    session: Session, today: date, *, low_stock_count: int, open_orders: int
) -> list[dict]:
    """Concrete lines. The KPI row already shows the counts."""
    notices: list[dict] = []
    if low_stock_count:
        try:
            names = [item.name for item in compute_reorder_list(session)[:3]]
        except Exception:  # noqa: BLE001
            names = []
        if names:
            notices.append(
                {
                    "text": "Bajo mínimo: " + ", ".join(names),
                    "href": "/inventario",
                }
            )
    if open_orders:
        due = session.scalars(
            select(Pedido)
            .where(Pedido.status.in_(_OPEN_ORDER), Pedido.promised_date <= today)
            .limit(3)
        ).all()
        for order in due:
            who = (order.customer_name or "").strip() or f"Pedido {order.id}"
            notices.append({"text": f"{who} · {order.promised_date}", "href": "/pedidos"})
    if not notices:
        notices.append({"text": "Sin avisos.", "href": ""})
    return notices[:5]
