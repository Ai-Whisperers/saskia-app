"""app/rms/loyalty/tiers.py — customer tier thresholds + tier_for_spend.

Loyalty tier is computed from lifetime_spend_gs:
  BRONZE   — default (0-99k Gs.)
  SILVER   — 100k-499k Gs.
  GOLD     — 500k-999k Gs.
  PLATINUM — 1M+ Gs.

Tier 4.1 (2026-10-01): extracted from app/rms/customers.py.
"""
from __future__ import annotations

from enum import Enum


class LoyaltyTier(str, Enum):
    """Customer tier based on lifetime spend (Gs.)."""

    BRONZE = "bronze"  # 0-100k
    SILVER = "silver"  # 100k-500k
    GOLD = "gold"  # 500k-1M
    PLATINUM = "platinum"  # 1M+


# Tier thresholds (Gs.).
TIER_THRESHOLDS: dict[LoyaltyTier, int] = {
    LoyaltyTier.BRONZE: 0,
    LoyaltyTier.SILVER: 100_000,
    LoyaltyTier.GOLD: 500_000,
    LoyaltyTier.PLATINUM: 1_000_000,
}


def tier_for_spend(lifetime_spend_gs: int) -> LoyaltyTier:
    """Map lifetime spend (Gs.) to the matching tier."""
    if lifetime_spend_gs >= TIER_THRESHOLDS[LoyaltyTier.PLATINUM]:
        return LoyaltyTier.PLATINUM
    if lifetime_spend_gs >= TIER_THRESHOLDS[LoyaltyTier.GOLD]:
        return LoyaltyTier.GOLD
    if lifetime_spend_gs >= TIER_THRESHOLDS[LoyaltyTier.SILVER]:
        return LoyaltyTier.SILVER
    return LoyaltyTier.BRONZE


__all__ = ["TIER_THRESHOLDS", "LoyaltyTier", "tier_for_spend"]
