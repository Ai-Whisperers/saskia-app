"""app/rms/seed — seed data packages (Sprint 2.4).

Split from monolithic seed_competitor_prices.py. The legacy seed_demo_data
function and seed constants moved into this package at app.rms.seed.demo
and are re-exported here so `from app.rms.seed import X` keeps working.
"""
from app.rms.seed import (
    competitor_prices,
    competitor_seed,
    competitor_shoppings,
)
from app.rms.seed.demo import (
    DEMO_USER_PASSWORD,
    DEMO_USER_USERNAME,
    INGREDIENTS,
    PRODUCTS,
    RECIPES,
    seed_demo_data,
)

__all__ = [
    "competitor_prices",
    "competitor_seed",
    "competitor_shoppings",
    "DEMO_USER_PASSWORD",
    "DEMO_USER_USERNAME",
    "INGREDIENTS",
    "PRODUCTS",
    "RECIPES",
    "seed_demo_data",
]