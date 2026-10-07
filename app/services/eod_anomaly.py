"""EOD anomaly detection (Tier 8.3, 2026-10-01).

Operator-facing alerts when the daily cierre looks off. Four checks,
each returns an Anomaly (or None) so the caller can decide severity.

Checks (all cheap, run in <100ms for a typical day):
1. **cash_zero_with_active_sales** — many active sales but no cash
   recorded. Info-level (operator might run a card-only day).
2. **voided_rate** — fraction of today's sales that were voided. Above
   10% is suspicious (a healthy bakery is closer to 1-3%).
3. **uninvoiced_factura** — sales with ``invoice_type='factura'`` but
   no ``invoice_number`` (DNIT compliance hole).
4. **negative_grand_total** — total sales for the day came out
   negative. Shouldn't happen (voids are positive, not negative) but
   catches a class of migration bugs.

Design choice: this module is **pure functions taking a Session**.
It does not call ``send_alert`` directly — that's wired at the
lifespan / cron layer so test mocking is straightforward and the
detector stays side-effect-free. Uses raw SQL via ``text()`` to avoid
the Sale ORM stub class (migration 092 dropped the table; the class
is kept for import-time compatibility only).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.rms.config import ASUNCION_TZ

Severity = Literal["info", "warn", "error", "critical"]


@dataclass(frozen=True)
class Anomaly:
    """A single EOD anomaly. Subject/body for ``send_alert``."""

    key: str  # stable identifier, e.g. "eod.voided_rate"
    severity: Severity
    title: str
    body: str

    def to_email(self) -> tuple[str, str, Severity]:
        return self.title, self.body, self.severity


def _day_range(day: date) -> tuple[datetime, datetime]:
    """Return (start_naive_local, end_naive_local) for the local-day window.

    Sale.sold_at is stored as a naive datetime in the local timezone
    (America/Asuncion) — see Sale.tz default in app.rms.models.sales.
    """
    start_local = datetime.combine(day, time.min)
    end_local = datetime.combine(day, time.max)
    return start_local, end_local


def _sales_today(session: Session, day: date) -> list[dict]:
    """Return today's sales as a list of dicts.

    Bypasses the ORM Sale class because the class is a deprecated
    stub (sale_stock_move table removed by migration 092; Sale
    itself still has a real table but the stub is the easiest path
    to keep the detector isolated from the rest of the app's mapper
    graph).
    """
    start, end = _day_range(day)
    rows = session.execute(
        text(
            """
            SELECT
                id,
                unit_price_gs,
                qty,
                discount_gs,
                voided_at,
                payment_method,
                invoice_type,
                invoice_number
            FROM sale
            WHERE sold_at >= :start AND sold_at <= :end
            """
        ),
        {"start": start, "end": end},
    ).fetchall()
    return [
        {
            "id": r[0],
            "unit_price_gs": r[1] or 0,
            "qty": r[2] or 0,
            "discount_gs": r[3] or 0,
            "voided": r[4] is not None,
            "payment_method": (r[5] or "").lower(),
            "invoice_type": r[6] or "boleta_resimple",
            "invoice_number": r[7],
        }
        for r in rows
    ]


def _row_total_gs(s: dict) -> int:
    """Total Gs. for a single sale row, matching the app's
    unit_price_gs * qty - discount_gs convention."""
    return int(s["unit_price_gs"] * s["qty"] - s["discount_gs"])


def _check_cash_zero_with_active(session: Session, day: date) -> Anomaly | None:
    sales = _sales_today(session, day)
    active = [s for s in sales if not s["voided"]]
    if not active:
        return None
    if any(s["payment_method"] in ("efectivo", "cash") for s in active):
        return None
    if len(active) < 5:
        return None
    return Anomaly(
        key="eod.cash_zero_with_active_sales",
        severity="info",
        title="Cierre sin ventas en efectivo",
        body=(
            f"Hay {len(active)} ventas activas hoy pero ninguna en "
            f"efectivo. Si la panadería estuvo abierta al público, "
            f"revisá que el método de pago se esté registrando bien."
        ),
    )


def _check_voided_rate(session: Session, day: date) -> Anomaly | None:
    sales = _sales_today(session, day)
    if len(sales) < 3:  # too small to be meaningful
        return None
    voided = sum(1 for s in sales if s["voided"])
    rate = voided / len(sales)
    if rate < 0.10:
        return None
    return Anomaly(
        key="eod.voided_rate",
        severity="warn",
        title="Tasa de anulaciones alta",
        body=(
            f"Hoy se anularon {voided} de {len(sales)} ventas "
            f"({rate:.0%}). Normal es 1-3%. Si fue error de operador, "
            f"no hay problema. Si fue sistemático, revisá el flujo de "
            f"cobro."
        ),
    )


def _check_uninvoiced_factura(session: Session, day: date) -> Anomaly | None:
    sales = _sales_today(session, day)
    bad = [s for s in sales if s["invoice_type"] == "factura" and not s["invoice_number"]]
    if not bad:
        return None
    return Anomaly(
        key="eod.uninvoiced_factura",
        severity="error",
        title="Ventas con factura sin número",
        body=(
            f"{len(bad)} ventas marcadas como 'factura' no tienen número "
            f"de timbrado. DNIT puede multar. IDs: "
            + ", ".join(str(s["id"]) for s in bad[:10])
            + ("..." if len(bad) > 10 else "")
        ),
    )


def _check_negative_grand_total(session: Session, day: date) -> Anomaly | None:
    sales = _sales_today(session, day)
    total = sum(_row_total_gs(s) for s in sales if not s["voided"])
    if total >= 0:
        return None
    return Anomaly(
        key="eod.negative_grand_total",
        severity="critical",
        title="Total de ventas del día NEGATIVO",
        body=(
            f"El total de hoy (sin anuladas) es Gs. {total:,}. No debería "
            f"ser negativo. Probable bug en la migración o en la "
            f"lógica de descuento. IDs: " + ", ".join(str(s["id"]) for s in sales[:10])
        ),
    )


def detect_anomalies(session: Session, day: date | None = None) -> list[Anomaly]:
    """Run all EOD anomaly checks. Returns a list (possibly empty)."""
    if day is None:
        day = datetime.now(ASUNCION_TZ).date()
    found: list[Anomaly] = []
    for check in (
        _check_cash_zero_with_active,
        _check_voided_rate,
        _check_uninvoiced_factura,
        _check_negative_grand_total,
    ):
        result = check(session, day)
        if result is not None:
            found.append(result)
    return found


__all__ = [
    "Anomaly",
    "Severity",
    "detect_anomalies",
]
