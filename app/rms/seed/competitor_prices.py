"""competitor_prices.py — competitor price seed orchestrator.

Sprint 2.4: split from monolithic seed_competitor_prices.py.

Provides:
- COMPETITOR_SEED: 86 non-shopping entries (backward compat re-export)
- COMPETITOR_SEED_SHOPPINGS: 58 shopping entries (backward compat re-export)
- COMPETITOR_SEED_ALL: 144 total entries (new combined list)
- seed_competitor_prices(session): DB insert orchestrator
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.rms.seed.competitor_seed import COMPETITOR_SEED
from app.rms.seed.competitor_shoppings import COMPETITOR_SEED_SHOPPINGS

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

COMPETITOR_SEED_ALL = list(COMPETITOR_SEED) + list(COMPETITOR_SEED_SHOPPINGS)
def seed_competitor_prices(session: "Session") -> "tuple[int, int]":
    """Inserta observaciones si no existen (idempotente). Devuelve (nuevas, omitidas)."""
    from datetime import date

    from sqlalchemy import select

    from app.rms.models import CompetitorPriceObservation

    existing = set(
        session.execute(
            select(
                CompetitorPriceObservation.competitor_name,
                CompetitorPriceObservation.product_name,
                CompetitorPriceObservation.as_of,
            )
        ).all()
    )
    added = skipped = 0
    for comp, ctype, city, item, fam, unit, price, asof, fuente in (
        COMPETITOR_SEED + COMPETITOR_SEED_SHOPPINGS
    ):
        as_of = date.fromisoformat(asof)
        if (comp, item, as_of) in existing:
            skipped += 1
            continue
        session.add(
            CompetitorPriceObservation(
                competitor_name=comp,
                competitor_type=ctype,
                city=city,
                product_name=item,
                family=fam,
                unit=unit,
                price_gs=price,
                as_of=as_of,
                source=fuente,
            )
        )
        added += 1
    session.commit()
    return added, skipped
