"""app/rms/seed — seed data packages (Sprint 2.4).

Split from monolithic seed_competitor_prices.py. The legacy seed_demo_data
function and seed constants moved into this package at app.rms.seed.demo
and are re-exported here so `from app.rms.seed import X` keeps working.

The **sazon** seeder creates a fully populated multi-tenant business
("La Vaquita Holandesa") with operators, ingredients, recipes, products,
customers, sales, pedidos, production plans, HACCP records, compliance,
suppliers, and more. Use this for demo / first-run.
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
from app.rms.seed.sazon import (
    SASKIA_PASSWORD,
    SASKIA_USER,
    SAZON_META_KEYS,
    TENANT_NAME,
    TENANT_SLUG,
    SazonReport,
    is_sazon_seeded,
    sazon_meta,
    seed_sazon,
)

__all__ = [
    "DEMO_USER_PASSWORD",
    "DEMO_USER_USERNAME",
    "INGREDIENTS",
    "PRODUCTS",
    "RECIPES",
    "SASKIA_PASSWORD",
    "SASKIA_USER",
    "SAZON_META_KEYS",
    "SazonReport",
    "TENANT_NAME",
    "TENANT_SLUG",
    "competitor_prices",
    "competitor_seed",
    "competitor_shoppings",
    "is_sazon_seeded",
    "sazon_meta",
    "seed_demo_data",
    "seed_sazon",
]
