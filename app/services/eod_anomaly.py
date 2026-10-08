"""EOD anomaly detection (Tier 8.3, 2026-10-01) + Batch B2 extraction (2026-10-07).

Operator-facing alerts when the daily cierre looks off. Four checks,
each returns an Anomaly (or None) so the caller can decide severity.

Checks (all cheap, run in <100ms for a typical day):
1. **cash_zero_with_active_sales** — many active sales but no cash
   recorded. Info-level (operator might run a card-only day).
2. **voided_rate** — fraction of today's sales that were voided.
   Threshold + min-sales guard tunable via SettingsKV
   (``eod.voided_rate_threshold``, ``eod.voided_rate_min_sales``).
3. **uninvoiced_factura** — sales with ``invoice_type='factura'`` but
   no ``invoice_number`` (DNIT compliance hole). Max IDs displayed
   in the email body tunable via ``eod.max_uninvoiced_ids_displayed``.
4. **negative_grand_total** — total sales for the day came out
   negative. Shouldn't happen (voids are positive, not negative) but
   catches a class of migration bugs.

Design choice: this module is **pure functions taking a Session**.
It does not call ``send_alert`` directly — that's wired at the
lifespan / cron layer so test mocking is straightforward and the
detector stays side-effect-free. Uses raw SQL via ``text()`` to avoid
the Sale ORM stub class (migration 092 dropped the table; the class
is kept for import-time compatibility only).

Batch B2 (2026-10-07): thresholds are now operator-tunable via the
SettingsKV registry. ``detect_anomalies`` accepts an optional
``eod_cfg`` dict kwarg; when None, the module-level
``DEFAULT_EOD_CONFIG`` is used.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.rms.config import ASUNCION_TZ

Severity = Literal["info", "warn", "error", "critical"]


# Batch B2 (2026-10-07): defaults for the operator-tunable thresholds.
# Mirror of the entries in app/rms/settings.py:SETTINGS under
# SettingGroup.EOD. Updated when those defaults change.
DEFAULT_EOD_CONFIG: dict[str, int | float] = {
    "voided_rate_threshold": 0.10,  # fraction; > this → "tasa alta"
    "voided_rate_min_sales": 3,  # skip check on slower days (avoids noise)
    "max_uninvoiced_ids_displayed": 10,  # cap on IDs listed in email body
}


# Batch C (2026-10-08): titles + bodies for the 4 EOD alerts are now
# loaded from the ``message_template`` table via get_eod_alert_template.
# The helper falls back to the prior hardcoded copy when the table is
# missing or the row is absent — preserves operator-observable behavior
# even before migration 116 runs.
from app.rms.alert_templates import get_eod_alert_template


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
    tmpl = get_eod_alert_template(session, "eod.cash_zero_with_active_sales")
    return Anomaly(
        key="eod.cash_zero_with_active_sales",
        severity="info",
        title=tmpl.subject,
        body=tmpl.render(active_count=len(active)),
    )


def _check_voided_rate(
    session: Session,
    day: date,
    cfg: dict[str, int | float],
) -> Anomaly | None:
    sales = _sales_today(session, day)
    min_sales = int(cfg["voided_rate_min_sales"])
    if len(sales) < min_sales:  # too small to be meaningful
        return None
    voided = sum(1 for s in sales if s["voided"])
    rate = voided / len(sales)
    threshold = float(cfg["voided_rate_threshold"])
    if rate < threshold:
        return None
    tmpl = get_eod_alert_template(session, "eod.voided_rate")
    return Anomaly(
        key="eod.voided_rate",
        severity="warn",
        title=tmpl.subject,
        body=tmpl.render(voided=voided, total=len(sales), rate_pct=f"{rate:.0%}"),
    )


def _check_uninvoiced_factura(
    session: Session,
    day: date,
    cfg: dict[str, int | float],
) -> Anomaly | None:
    sales = _sales_today(session, day)
    bad = [s for s in sales if s["invoice_type"] == "factura" and not s["invoice_number"]]
    if not bad:
        return None
    cap = int(cfg["max_uninvoiced_ids_displayed"])
    tmpl = get_eod_alert_template(session, "eod.uninvoiced_factura")
    ids = ", ".join(str(s["id"]) for s in bad[:cap])
    if len(bad) > cap:
        ids += "..."
    return Anomaly(
        key="eod.uninvoiced_factura",
        severity="error",
        title=tmpl.subject,
        body=tmpl.render(bad_count=len(bad), ids=ids),
    )


def _check_negative_grand_total(session: Session, day: date) -> Anomaly | None:
    sales = _sales_today(session, day)
    total = sum(_row_total_gs(s) for s in sales if not s["voided"])
    if total >= 0:
        return None
    tmpl = get_eod_alert_template(session, "eod.negative_grand_total")
    ids = ", ".join(str(s["id"]) for s in sales[:10])
    return Anomaly(
        key="eod.negative_grand_total",
        severity="critical",
        title=tmpl.subject,
        body=tmpl.render(total=total, ids=ids),
    )


def detect_anomalies(
    session: Session,
    day: date | None = None,
    eod_cfg: dict[str, int | float] | None = None,
) -> list[Anomaly]:
    """Run all EOD anomaly checks. Returns a list (possibly empty).

    Args:
      session: SQLAlchemy session (sync).
      day: the local day to check. Defaults to today (Asunción).
      eod_cfg: optional override dict for the tunable thresholds
        (Batch B2, 2026-10-07). When None, defaults from
        DEFAULT_EOD_CONFIG are used. Caller should pass
        get_eod_config(session) for production use.

    Returns:
      List of Anomaly objects, possibly empty.
    """
    if day is None:
        day = datetime.now(ASUNCION_TZ).date()
    cfg = dict(DEFAULT_EOD_CONFIG)
    if eod_cfg is not None:
        cfg.update(eod_cfg)
    found: list[Anomaly] = []
    for check in (
        _check_cash_zero_with_active,
        _check_voided_rate,
        _check_uninvoiced_factura,
        _check_negative_grand_total,
    ):
        # cash_zero + negative_grand_total don't use cfg today; pass
        # it anyway so future extractions don't require a signature bump.
        if check in (_check_voided_rate, _check_uninvoiced_factura):
            result = check(session, day, cfg)  # type: ignore[arg-type]
        else:
            result = check(session, day)
        if result is not None:
            found.append(result)
    return found


__all__ = [
    "DEFAULT_EOD_CONFIG",
    "Anomaly",
    "Severity",
    "detect_anomalies",
]
