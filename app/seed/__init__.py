"""app.seed — operator/demo seed helpers.

This package exposes pure-function seed helpers that:

- Build a "complete" demo customer (Kyrian Weiss) with full history
  across customer / pedido / sale / loyalty / subscription / addresses.
- Are idempotent (safe to call twice — deletes by phone before insert).
- Are reused by both the qseed test fixture AND the `/demo/seed`
  endpoint (Phase 2), so tests and live demo stay in sync.

The seed produces a coherent, realistic dataset that lets us:

- Exercise every form field on `/pedidos/nuevo` against Kyrian's record.
- Demonstrate the loyalty ledger (earn + redeem + audit row per sale).
- Show subscriptions, addresses, dietary profile, all in one customer.
- Drive smart-defaults from real history (Phase 3 uses this output).

PII NOTE: Kyrian's phone / email / CI match the live operator's actual
data (Ivan's brother-in-law). They are documented as demo data and must
NEVER be committed with any real production data attached. Idempotency
deletes by phone — running this on a DB that already has a real Kyrian
will overwrite his record.
"""

from app.seed.kyrian import (
    KyrianBundle,
    seed_kyrian,
    KYRIAN_PHONE,
    KYRIAN_EMAIL,
    KYRIAN_CEDULA,
    KYRIAN_NAME,
)
from app.seed.catalog import (
    seed_catalog,
    INGREDIENTS_BY_SLUG,
    RECIPES_BY_SLUG,
    RECIPES_BY_ID,
    PRODUCTS_BY_SLUG,
)

__all__ = [
    "KyrianBundle",
    "seed_kyrian",
    "KYRIAN_PHONE",
    "KYRIAN_EMAIL",
    "KYRIAN_CEDULA",
    "KYRIAN_NAME",
    "seed_catalog",
    "INGREDIENTS_BY_SLUG",
    "RECIPES_BY_SLUG",
    "RECIPES_BY_ID",
    "PRODUCTS_BY_SLUG",
]
