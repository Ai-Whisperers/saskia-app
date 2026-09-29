"""app/rms/margin_tier.py — Margin tier helper module (Phase 7).

Replaces hardcoded if-chain in app/rms/tags.py:378-382. Operators can
adjust thresholds via /api/margin-tiers or /settings/catalog without
code deploy.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import MarginTier


@dataclass(frozen=True)
class TierMatch:
    """Result of matching a recipe cost against active tiers."""

    code: str
    label: str
    min_cost_gs: int | None
    max_cost_gs: int | None


def list_margin_tiers(session: Session, include_inactive: bool = False) -> list[MarginTier]:
    """Return all margin tiers, sorted by sort_order."""
    q = select(MarginTier)
    if not include_inactive:
        q = q.where(MarginTier.is_active.is_(True))
    q = q.order_by(MarginTier.sort_order.asc(), MarginTier.code.asc())
    return list(session.execute(q).scalars())


def get_margin_tier(session: Session, code: str) -> MarginTier | None:
    """Return one tier by code (or None if missing/inactive)."""
    return session.execute(
        select(MarginTier).where(
            MarginTier.code == code,
            MarginTier.is_active.is_(True),
        )
    ).scalar_one_or_none()


def recipe_matches_tier(cost_gs: int | None, tier: MarginTier) -> bool:
    """Return True iff the recipe's cost matches this tier's thresholds.

    A tier matches when:
      - tier.max_cost_gs is None or cost <= max_cost_gs
      - tier.min_cost_gs is None or cost >= min_cost_gs
    """
    if cost_gs is None:
        return False
    if tier.max_cost_gs is not None and cost_gs > tier.max_cost_gs:
        return False
    if tier.min_cost_gs is not None and cost_gs < tier.min_cost_gs:
        return False
    return True


def filter_recipes_by_tier(
    session: Session, recipes_with_cost: list[tuple], tier_code: str
) -> list:
    """Filter a list of (recipe, cost) tuples by the named tier.

    Reads thresholds from the `margin_tier` table. Falls back to including
    all recipes if the tier code is missing/inactive (so an operator
    accidentally disabling a tier doesn't lose data).
    """
    tier = get_margin_tier(session, tier_code)
    if tier is None:
        return [r for r, _ in recipes_with_cost]
    return [r for r, cost in recipes_with_cost if recipe_matches_tier(cost, tier)]


__all__ = [
    "TierMatch",
    "filter_recipes_by_tier",
    "get_margin_tier",
    "list_margin_tiers",
    "recipe_matches_tier",
]
