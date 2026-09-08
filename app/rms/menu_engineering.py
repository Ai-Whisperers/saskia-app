"""app/rms/menu_engineering.py — star/puzzle/plowhorse/dog quadrant classification.

Classic restaurant consulting tool (Kasavana/Donaldson, 1992). Each product
is plotted on a 2x2 matrix:
  - x-axis: volume (units sold)
  - y-axis: margin (margin_gs or margin_ratio)

Quadrants:
  STAR     = high margin + high volume   → promote, protect
  PLOWHORSE= low margin  + high volume   → reprice or rework cost
  PUZZLE   = high margin + low volume    → market harder
  DOG      = low margin  + low volume    → consider removing

Thresholds: median margin + median volume across the active catalog.
"""

from __future__ import annotations

import dataclasses
import enum
from dataclasses import dataclass
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.costing import batch_products_cost_margin
from app.rms.models import Product, Sale


class Quadrant(str, enum.Enum):
    STAR = "star"
    PLOWHORSE = "plowhorse"
    PUZZLE = "puzzle"
    DOG = "dog"


@dataclass(frozen=True)
class ProductClassification:
    product_id: int
    product_name: str
    quadrant: Quadrant
    volume: int
    margin_gs: int
    margin_ratio: float
    sale_price_gs: int
    cost_gs: int | None


@dataclass(frozen=True)
class MenuEngineeringReport:
    star: list[ProductClassification]
    plowhorse: list[ProductClassification]
    puzzle: list[ProductClassification]
    dog: list[ProductClassification]

    @property
    def total_margin_gs(self) -> int:
        return sum(p.margin_gs for q in (self.star, self.plowhorse,
                                          self.puzzle, self.dog)
                   for p in q)

    @property
    def counts(self) -> dict[str, int]:
        return {
            "star": len(self.star),
            "plowhorse": len(self.plowhorse),
            "puzzle": len(self.puzzle),
            "dog": len(self.dog),
        }

    def as_dict(self) -> dict:
        return {
            "counts": self.counts,
            "total_margin_gs": self.total_margin_gs,
            "star": [self._to_dict(p) for p in self.star],
            "plowhorse": [self._to_dict(p) for p in self.plowhorse],
            "puzzle": [self._to_dict(p) for p in self.puzzle],
            "dog": [self._to_dict(p) for p in self.dog],
        }

    @staticmethod
    def _to_dict(p: ProductClassification) -> dict:
        return {
            "product_id": p.product_id,
            "product_name": p.product_name,
            "quadrant": p.quadrant.value,
            "volume": p.volume,
            "margin_gs": p.margin_gs,
            "margin_ratio": p.margin_ratio,
            "sale_price_gs": p.sale_price_gs,
            "cost_gs": p.cost_gs,
        }


# ---------------------------------------------------------------------------
# Volume + margin computation
# ---------------------------------------------------------------------------

_VOLUME_WINDOW_DAYS: Final[int] = 90  # last 90 days of sales


def _product_volume(session: Session, product_id: int,
                    days: int = _VOLUME_WINDOW_DAYS) -> int:
    """Units sold in the last N days (excluding voided sales)."""
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = session.execute(
        select(Sale.qty).where(
            Sale.product_id == product_id,
            Sale.voided_at.is_(None),
            Sale.sold_at >= cutoff,
        )
    ).all()
    return sum(int(r[0] or 0) for r in rows)


def _product_margin(session: Session, product: Product) -> tuple[int, int | None, float]:
    """Returns (margin_gs, cost_gs, margin_ratio).

    cost_gs is None when the product has no recipe or cost data; we still
    return margin based on sale price alone (margin_ratio undefined).
    """
    from app.rms.costing import batch_products_cost_margin

    cost_map = batch_products_cost_margin(session, [product])
    cost_result, margin_pair = cost_map.get(product.id, (None, (None, None)))
    cost_gs = cost_result.batch_cost_gs if cost_result else None
    margin_gs, margin_ratio = margin_pair
    if margin_gs is None:
        margin_gs = product.sale_price_gs or 0
    return margin_gs, cost_gs, margin_ratio or 0.0


# ---------------------------------------------------------------------------
# classify + report
# ---------------------------------------------------------------------------

def classify_products(session: Session) -> list[ProductClassification]:
    """Compute quadrant for every product.

    Batched: 1 query for all sales volumes in window (grouped by product)
    + 1 batch_products_cost_margin call (already batched). Total: ~4
    queries regardless of product count, down from ~60+ before.
    """
    from datetime import datetime, timedelta, timezone

    products = list(session.scalars(select(Product)).all())
    if not products:
        return []

    # Batch-load all sales volumes in one query, grouped by product.
    cutoff = datetime.now(timezone.utc) - timedelta(days=_VOLUME_WINDOW_DAYS)
    volume_rows = session.execute(
        select(Sale.product_id, Sale.qty).where(
            Sale.product_id.in_([p.id for p in products]),
            Sale.voided_at.is_(None),
            Sale.sold_at >= cutoff,
        )
    ).all()
    volume_by_product: dict[int, int] = {}
    for pid, qty in volume_rows:
        volume_by_product[pid] = volume_by_product.get(pid, 0) + int(qty or 0)

    # Batch-load all product costs (3-4 queries via existing helper).
    batch_costs = batch_products_cost_margin(session, products)

    classifications: list[ProductClassification] = []
    for p in products:
        vol = volume_by_product.get(p.id, 0)
        cost_result, margin_pair = batch_costs.get(p.id, (None, (None, None)))
        cost_gs = cost_result.batch_cost_gs if cost_result else None
        margin_gs, margin_ratio = margin_pair
        if margin_gs is None:
            margin_gs = p.sale_price_gs or 0
        classifications.append(ProductClassification(
            product_id=p.id,
            product_name=p.name,
            quadrant=Quadrant.DOG,  # placeholder, set after median threshold
            volume=vol,
            margin_gs=margin_gs,
            margin_ratio=margin_ratio or 0.0,
            sale_price_gs=p.sale_price_gs or 0,
            cost_gs=cost_gs,
        ))

    # Compute medians for threshold.
    volumes = sorted(c.volume for c in classifications)
    margins = sorted(c.margin_gs for c in classifications)
    vol_threshold = _median(volumes)
    margin_threshold = _median(margins)

    # Apply thresholds.
    for i, c in enumerate(classifications):
        high_vol = c.volume >= vol_threshold
        high_margin = c.margin_gs >= margin_threshold
        if high_vol and high_margin:
            new_q = Quadrant.STAR
        elif high_vol and not high_margin:
            new_q = Quadrant.PLOWHORSE
        elif not high_vol and high_margin:
            new_q = Quadrant.PUZZLE
        else:
            new_q = Quadrant.DOG
        classifications[i] = dataclasses.replace(c, quadrant=new_q)
    return classifications


def _median(values: list[int]) -> int:
    """Median of a list. 0 for empty."""
    if not values:
        return 0
    n = len(values)
    if n % 2 == 1:
        return values[n // 2]
    return (values[n // 2 - 1] + values[n // 2]) // 2


def menu_engineering_report(session: Session) -> MenuEngineeringReport:
    """Bucket all products into quadrants and return the report."""
    classifications = classify_products(session)
    return MenuEngineeringReport(
        star=[c for c in classifications if c.quadrant == Quadrant.STAR],
        plowhorse=[c for c in classifications if c.quadrant == Quadrant.PLOWHORSE],
        puzzle=[c for c in classifications if c.quadrant == Quadrant.PUZZLE],
        dog=[c for c in classifications if c.quadrant == Quadrant.DOG],
    )


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

RECOMMENDATIONS: Final[dict[str, str]] = {
    Quadrant.STAR.value:
        "Promote and protect — these are your winners.",
    Quadrant.PLOWHORSE.value:
        "Consider repricing or reducing cost — high volume, thin margin.",
    Quadrant.PUZZLE.value:
        "Push harder on marketing — high margin, low visibility.",
    Quadrant.DOG.value:
        "Consider removing from menu or rebranding — low margin, low volume.",
}


def action_for(product_class: ProductClassification) -> str:
    return RECOMMENDATIONS[product_class.quadrant.value]


__all__ = [
    "MenuEngineeringReport",
    "ProductClassification",
    "Quadrant",
    "RECOMMENDATIONS",
    "action_for",
    "classify_products",
    "menu_engineering_report",
]
