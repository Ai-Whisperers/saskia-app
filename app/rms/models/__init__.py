"""app/rms/models/ — per-domain ORM tables.

This package replaces the monolithic `app/rms/models.py` (1350 LOC,
36 model classes). The split happened on 2026-09-23 (Phase 3.1
refactor) for these reasons:

- **Discoverability**: 1350 LOC with every class intermingled made
  domain ownership invisible. After the split, opening
  `inventory.py` shows you all the ingredient/recipe/product models
  in one glance.
- **Faster cold imports**: tests that only need `Sale` no longer
  pay for parsing `Ingredient`, `WishlistItem`, `BankTransaction`, etc.
  Marginal in practice, but a real win in test collection time.
- **Conflict surface**: changes to one domain (e.g. `Ingredient`)
  no longer require touching the same diff as changes to a
  different domain (e.g. `RiskItem`), reducing merge-noise.

## Backward compatibility

This package re-exports every model class at the top level, so all
existing call sites continue to work unchanged:

    from app.rms.models import Product, Sale, Customer, AuditLog

These re-exports also drive SQLAlchemy's mapper configuration: every
domain sub-module is imported once here, and each `class X(Base)`
binds itself to the registry on `Base`. After this `__init__.py`
finishes executing, every model class is in the registry and
relationship strings like `relationship("Sale", back_populates="...")`
resolve correctly across modules.

## Domain layout

| File | Contents |
|---|---|
| `core.py` | The shared `Base` (declarative registry root) |
| `audit.py` | `AppMeta` (the key-value store) |
| `auth.py` | `User`, `AuditLog`, `SettingsKV`, `Tenant` |
| `inventory.py` | `Ingredient`, `Recipe`, `RecipeLine`, `Product`, `IngredientPriceEvent`, `PriceHistory` |
| `sales.py` | `Sale`, `SaleStockMove`, `Customer`, `Tag`, `TagLink`, `RecipePricing` |
| `orders.py` | `Pedido`, `PedidoLine` |
| `production.py` | `ProductionCompletion`, `ProductionPlanTemplate`, `ProductionPlanOverride`, `ProductionPlan` |
| `procurement.py` | `Supplier`, `WasteLog`, `ShoppingListItem`, `StockMovement`, `ImportBatch` |
| `delivery.py` | `DeliveryZone` |
| `herbus_drive.py` | `WishlistItem`, `RiskItem`, `MarketBenchmark`, `BankTransaction`, `ComplianceInfo`, `MarketPriceReference` (operational / HEREBUS-imported) |
"""

from __future__ import annotations

# 1. The declarative Base MUST be imported first; every model class
#    inherits from it, and SQLAlchemy's mapper config attaches to its
#    registry on import.
from app.rms.models.core import Base  # noqa: F401

# 2. Import every domain sub-module so its @class-decorated models
#    register with the Base registry. Order doesn't matter — SQLAlchemy
#    resolves relationship() strings lazily.
from app.rms.models import (
    audit,           # AppMeta
    auth,            # User, AuditLog, SettingsKV, Tenant
    inventory,       # Ingredient, Recipe, RecipeLine, Product,
                     # IngredientPriceEvent, PriceHistory
    sales,           # Sale, SaleStockMove, Customer, Tag, TagLink,
                     # RecipePricing
    orders,          # Pedido, PedidoLine
    production,      # ProductionCompletion, ProductionPlanTemplate,
                     # ProductionPlanOverride, ProductionPlan
    procurement,     # Supplier, WasteLog, ShoppingListItem, StockMovement,
                     # ImportBatch
    delivery,        # DeliveryZone
    herbus_drive,    # WishlistItem, RiskItem, MarketBenchmark, BankTransaction,
                     # ComplianceInfo, MarketPriceReference
)

# 3. Re-export every public model class at the top level of
#    `app.rms.models` so existing call sites
#    (`from app.rms.models import Product`) continue to work.
#    This is the backward-compatibility shim — do NOT remove without
#    auditing the 470+ imports across app/ and tests/ that use it.
from app.rms.models.audit import AppMeta
from app.rms.models.auth import AuditLog, SettingsKV, Tenant, User
from app.rms.models.delivery import DeliveryZone
from app.rms.models.herbus_drive import (
    BankTransaction,
    ComplianceInfo,
    MarketBenchmark,
    MarketPriceReference,
    RiskItem,
    WishlistItem,
)
from app.rms.models.inventory import (
    Ingredient,
    IngredientPriceEvent,
    PriceHistory,
    Product,
    Recipe,
    RecipeLine,
)
from app.rms.models.orders import Pedido, PedidoLine
from app.rms.models.procurement import (
    ImportBatch,
    ShoppingListItem,
    StockMovement,
    Supplier,
    WasteLog,
)
from app.rms.models.production import (
    ProductionCompletion,
    ProductionPlan,
    ProductionPlanOverride,
    ProductionPlanTemplate,
)
from app.rms.models.sales import (
    Customer,
    RecipePricing,
    Sale,
    SaleStockMove,
    Tag,
    TagLink,
)


__all__ = [
    "Base",
    # audit
    "AppMeta",
    # auth
    "AuditLog",
    "SettingsKV",
    "Tenant",
    "User",
    # delivery
    "DeliveryZone",
    # herbus_drive
    "BankTransaction",
    "ComplianceInfo",
    "MarketBenchmark",
    "MarketPriceReference",
    "RiskItem",
    "WishlistItem",
    # inventory
    "Ingredient",
    "IngredientPriceEvent",
    "PriceHistory",
    "Product",
    "Recipe",
    "RecipeLine",
    # orders
    "Pedido",
    "PedidoLine",
    # procurement
    "ImportBatch",
    "ShoppingListItem",
    "StockMovement",
    "Supplier",
    "WasteLog",
    # production
    "ProductionCompletion",
    "ProductionPlan",
    "ProductionPlanOverride",
    "ProductionPlanTemplate",
    # sales
    "Customer",
    "RecipePricing",
    "Sale",
    "SaleStockMove",
    "Tag",
    "TagLink",
]
