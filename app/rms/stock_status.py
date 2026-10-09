"""app/rms/stock_status.py — Stock status threshold helper module (Phase 7).

Replaces hardcoded magic numbers in app/rms/tags.py:325-331. Operators
adjust thresholds via /api/stock-status-config or /settings/catalog.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.constants import (
    DEFAULT_DEAD_STOCK_DAYS,
    DEFAULT_STOCK_RATIO_CRITICO,
    DEFAULT_STOCK_RATIO_SOBRESTOCK,
    STOCK_STATUS_BAJO_MIN,
    STOCK_STATUS_CRITICO,
    STOCK_STATUS_MUERTO,
    STOCK_STATUS_SOBRESTOCK,
)
from app.rms.models import StockStatusConfig


@dataclass(frozen=True)
class Threshold:
    """Effective threshold for one stock status code."""

    code: str
    label: str
    ratio: float | None  # for critico / sobrestock
    days: int | None  # for muerto


def get_thresholds(session: Session) -> dict[str, Threshold]:
    """Return active stock status thresholds keyed by code.

    Falls back to DEFAULT_* constants from app/rms/constants.py for any
    missing config rows. Cache-friendly: callers should pass the result
    to categorize() rather than re-querying per ingredient.
    """
    rows = (
        session.execute(select(StockStatusConfig).where(StockStatusConfig.is_active.is_(True)))
        .scalars()
        .all()
    )

    out: dict[str, Threshold] = {}
    for r in rows:
        out[r.code] = Threshold(
            code=r.code,
            label=r.label,
            ratio=r.threshold_ratio,
            days=r.threshold_days,
        )

    # Fill in defaults for any missing codes
    out.setdefault(
        STOCK_STATUS_BAJO_MIN,
        Threshold(
            code=STOCK_STATUS_BAJO_MIN,
            label="Bajo mínimo",
            ratio=None,
            days=None,
        ),
    )
    out.setdefault(
        STOCK_STATUS_CRITICO,
        Threshold(
            code=STOCK_STATUS_CRITICO,
            label="Crítico",
            ratio=float(DEFAULT_STOCK_RATIO_CRITICO),
            days=None,
        ),
    )
    out.setdefault(
        STOCK_STATUS_SOBRESTOCK,
        Threshold(
            code=STOCK_STATUS_SOBRESTOCK,
            label="Sobrestock",
            ratio=float(DEFAULT_STOCK_RATIO_SOBRESTOCK),
            days=None,
        ),
    )
    out.setdefault(
        STOCK_STATUS_MUERTO,
        Threshold(
            code=STOCK_STATUS_MUERTO,
            label="Sin consumo",
            ratio=None,
            days=DEFAULT_DEAD_STOCK_DAYS,
        ),
    )
    return out


def categorize(
    stock_qty: float,
    min_stock_qty: float,
    last_consumed_at: datetime | None,
    thresholds: dict[str, Threshold],
) -> str | None:
    """Return the matching stock status code (or None).

    Order of checks (first match wins):
      - muerto: last_consumed_at is None OR older than threshold_days
      - sobrestock: ratio > threshold.ratio
      - critico: ratio < threshold.ratio
      - bajo_min: stock_qty < min_stock_qty
      - None: otherwise (no status matches)

    Note: priority order is intentional — "muerto" overrides everything
    else because it's a stronger signal than stock level alone.
    """
    # Compute ratio (None when min is 0 to avoid division by zero)
    ratio = (stock_qty / min_stock_qty) if min_stock_qty > 0 else 1.0

    # muerto — no consumption in N days (or never consumed)
    muerto_cfg = thresholds.get(STOCK_STATUS_MUERTO)
    if muerto_cfg and muerto_cfg.days:
        if last_consumed_at is None:
            return STOCK_STATUS_MUERTO
        last = last_consumed_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - last).days
        if age_days >= muerto_cfg.days:
            return STOCK_STATUS_MUERTO

    # sobrestock
    sob = thresholds.get(STOCK_STATUS_SOBRESTOCK)
    if sob and sob.ratio and ratio > sob.ratio:
        return STOCK_STATUS_SOBRESTOCK

    # critico
    cri = thresholds.get(STOCK_STATUS_CRITICO)
    if cri and cri.ratio and ratio < cri.ratio:
        return STOCK_STATUS_CRITICO

    # bajo_min
    if stock_qty < min_stock_qty:
        return STOCK_STATUS_BAJO_MIN

    return None


def list_status_configs(
    session: Session, include_inactive: bool = False
) -> list[StockStatusConfig]:
    """Return all stock status configs, sorted by sort_order."""
    q = select(StockStatusConfig)
    if not include_inactive:
        q = q.where(StockStatusConfig.is_active.is_(True))
    q = q.order_by(StockStatusConfig.sort_order.asc(), StockStatusConfig.code.asc())
    return list(session.execute(q).scalars())


__all__ = [
    "Threshold",
    "categorize",
    "get_thresholds",
    "list_status_configs",
]
