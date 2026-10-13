"""tests/test_models_smoke.py — Smoke test for all 65 ORM models.
# allow-hardcoded-dates: fixture: updated_at='2026-10-12T00:00:00' is AppMeta row data, not relative-time

Phase 4.4 (2026-10-12): each model in app/rms/models/ must be importable
and instantiable. This is the canary that catches:
  - Schema refactors that break mapper config (e.g. the Phase-2B
    domain-package refactor that renamed tables and dropped classes)
  - Missing imports
  - Required-field changes that break the existing test suite

Two layers:

  L1 (cheap, ~62 tests, no DB):
    - Import the class
    - Verify it has __tablename__ (so it actually maps to a table)

  L2 (DB roundtrip, ~8 critical models):
    - Create instance with minimum required fields
    - session.add, commit, fetch by PK
    - Verify the row exists

L1 catches ~80% of model issues with zero DB cost. L2 covers the
high-risk path: a model whose mapper-config is fine but whose actual
SQL write fails. We only do L2 for the most-touched models (those
referenced by the factory layer); the rest are implicitly exercised
by the 2140-test suite.

What this does NOT do:
  - Test every field's constraint (too noisy, low value)
  - Test relationships (already covered by integration tests)
  - Replace tests/factories.py (it IS the factory's contract)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.models_smoke


# L1: every model can be imported and has a tablename.
# Generated list from `grep -E '^class \w+\(Base\)' app/rms/models_legacy.py`
# plus `MonthlyClosure` from app/rms/models/closure.py.
# Note: SaleStockMove is the deprecated stub from the BACKLOG (its
# __table__ is None); excluded from L1 by intent.
_L1_MODELS = [
    "AppMeta",
    "Ingredient",
    "IngredientVariant",
    "Recipe",
    "RecipeLine",
    "Product",
    "Sale",
    "SalePayment",
    "CashSession",
    "CreditAccount",
    "CreditTransaction",
    "Menu",
    "MenuItem",
    "ImportBatch",
    "User",
    "AuditLog",
    "IngredientPriceEvent",
    "Customer",
    "Tag",
    "TagLink",
    "ProductionCompletion",
    "FreezerTemperatureLog",
    "ProductionPlanTemplate",
    "ProductionPlanOverride",
    "ProductionClosedDay",
    "ProductionDemandSnapshot",
    "ProductionPlanAudit",
    "Supplier",
    "WasteLog",
    "Expense",
    "CustomerAddress",
    "CustomerInvoiceProfile",
    "DeliveryZone",
    "WishlistItem",
    "RiskItem",
    "RecipePricing",
    "PriceHistory",
    "ProductionPlan",
    "ShoppingListItem",
    "MarketBenchmark",
    "BankTransaction",
    "SettingsKV",
    "Pedido",
    "PedidoLine",
    "PedidoEvent",
    "Tenant",
    "StockMovement",
    "ComplianceInfo",
    "CommunicationLog",
    "Channel",
    "Category",
    "DateRangePreset",
    "MarginTier",
    "MarketPriceReference",
    "MessageTemplate",
    "PaymentMethod",
    "StockStatusConfig",
    "StorageKeyword",
    "StorageType",
    "Suscripcion",
    "MonthlyClosure",
]


@pytest.mark.parametrize("model_name", _L1_MODELS)
def test_model_importable_and_has_tablename(model_name):
    """L1: every model imports cleanly and maps to a table.

    The 29 models at 0% coverage in the coverage report include the
    model files themselves; importing the class touches the module
    body, which moves the coverage counter for that file.
    """
    from app.rms import models

    cls = getattr(models, model_name, None)
    assert cls is not None, f"app.rms.models.{model_name} not importable"
    # Has a tablename attribute (not abstract)
    assert hasattr(cls, "__tablename__"), (
        f"app.rms.models.{model_name} has no __tablename__ (abstract?)"
    )
    assert cls.__tablename__, f"app.rms.models.{model_name}.__tablename__ is empty"


# L2: critical models can be created and roundtripped.
# These are the models used by tests/factories.py and the production
# code paths. A mapper-config bug on one of these would break the whole
# app; a SQL-write bug would surface as a 500 in production.
_L2_MODELS = [
    # (class_name, required_kwargs)
    # NOTE: ingredient.unit is a CHECK constraint ∈ {'g','kg','ml','l','und'}
    # NOTE: tag.kind is NOT NULL (default 'dietary' is set in factory, must
    #       be passed here)
    # NOTE: SettingsKV uses `value_json` (not `value`)
    # NOTE: AppMeta needs updated_at (text column, NOT NULL)
    ("Supplier", {"name": "_smoke_supplier"}),
    ("Tag", {"name": "_smoke_tag", "kind": "dietary"}),
    ("Customer", {"name": "_smoke_customer"}),
    ("Ingredient", {"name": "_smoke_ingredient", "unit": "kg"}),
    ("Recipe", {"name": "_smoke_recipe", "yield_qty": 1.0, "yield_unit": "und"}),
    ("Product", {"name": "_smoke_product", "sale_price_gs": 1000}),
    ("SettingsKV", {"key": "_smoke_kv", "value_json": "{}"}),
    ("AppMeta", {"key": "_smoke_meta", "value": "x", "updated_at": "2026-10-12T00:00:00Z"}),
]


@pytest.mark.parametrize("model_name,kwargs", _L2_MODELS)
def test_model_roundtrips_through_db(session_factory, model_name, kwargs):
    """L2: critical models survive a real SQL roundtrip.

    For each model, create with minimum required fields, commit, fetch
    by primary key, verify the row exists. Catches schema mismatches
    and migration drift.
    """
    from datetime import datetime, timezone

    from sqlalchemy import select

    from app.rms import models

    cls = getattr(models, model_name)
    # Append a unique suffix to identifier fields (name, key) to avoid
    # collision across the parametrized run. Don't suffix enum/check
    # values like unit='kg' or kind='dietary' — they must match their
    # CHECK constraints verbatim.
    ts_suffix = datetime.now(timezone.utc).strftime("%H%M%S%f")
    unique_kwargs = {
        k: (f"{v}_{ts_suffix}" if k in ("name", "key") else v) for k, v in kwargs.items()
    }
    with session_factory() as s:
        instance = cls(**unique_kwargs)
        s.add(instance)
        s.commit()
        s.refresh(instance)

        # Fetch back. PK is either `id` (int auto) or `key` (KV-style).
        if getattr(instance, "id", None) is not None:
            fetched = s.get(cls, instance.id)
        elif getattr(instance, "key", None) is not None:
            fetched = s.get(cls, instance.key)
        else:
            first_col = list(unique_kwargs)[0]
            fetched = s.execute(
                select(cls).where(getattr(cls, first_col) == list(unique_kwargs.values())[0])
            ).scalar_one()
        assert fetched is not None, f"{model_name} did not roundtrip"


# L3: Sale needs a real product (FK). Sub-test: create a sale and verify
# the FK constraint is satisfied. This is a different test from the
# generic L2 because it has a dependency.
def test_sale_roundtrip_with_product(session_factory):
    """L2b: Sale requires a real Product (FK constraint).

    Sale is the most-touched model in the suite; a Sale-side regression
    would block the entire ventas vertical. This test pins the FK
    relationship.
    """
    from datetime import datetime, timedelta, timezone

    from app.rms import models

    ts = datetime.now(timezone.utc).strftime("%H%M%S%f")
    with session_factory() as s:
        product = models.Product(name=f"_smoke_p_{ts}", sale_price_gs=1000)
        s.add(product)
        s.commit()
        s.refresh(product)

        sale = models.Sale(
            product_id=product.id,
            qty=1.0,
            unit_price_gs=1000,
            sold_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        s.add(sale)
        s.commit()
        s.refresh(sale)

        fetched = s.get(models.Sale, sale.id)
        assert fetched is not None
        assert fetched.product_id == product.id
        assert fetched.qty == 1.0
        assert fetched.unit_price_gs == 1000
