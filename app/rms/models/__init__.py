"""app.rms.models — single source of truth (pre-refactor models.py).

The Phase-2B domain-package refactor (fb57f00) shipped broken: renamed
tables (Sale/Customer PascalCase) broke every FK, dropped 12 model
classes (catalogs, storage, presets), rewrote sale_stock_move with the
wrong schema, and left db.py with a syntax error. Until the refactor is
redone properly, this package re-exports the last known-good monolithic
models.py (commit b9b5288) which the entire app + 2140-test suite runs
green against. The domain submodules remain on disk for the redo.
"""
from app.rms.models_legacy import *  # noqa: F403 — legacy compatibility layer, all names re-exported intentionally

# Also export names legacy __all__ may miss
from app.rms.models_legacy import (
    AppMeta,  # noqa: F401 — re-exported via __all__
    AuditLog,  # noqa: F401 — re-exported via __all__
    BankTransaction,  # noqa: F401 — re-exported via __all__
    Category,  # noqa: F401 — re-exported via __all__
    Channel,  # noqa: F401 — re-exported via __all__
    ComplianceInfo,  # noqa: F401 — re-exported via __all__
    Customer,  # noqa: F401 — re-exported via __all__
    DateRangePreset,  # noqa: F401 — re-exported via __all__
    DeliveryZone,  # noqa: F401 — re-exported via __all__
    ImportBatch,  # noqa: F401 — re-exported via __all__
    Ingredient,  # noqa: F401 — re-exported via __all__
    IngredientPriceEvent,  # noqa: F401 — re-exported via __all__
    IngredientVariant,  # noqa: F401 — re-exported via __all__
    MarginTier,  # noqa: F401 — re-exported via __all__
    MarketBenchmark,  # noqa: F401 — re-exported via __all__
    MarketPriceReference,  # noqa: F401 — re-exported via __all__
    MessageTemplate,  # noqa: F401 — re-exported via __all__
    PaymentMethod,  # noqa: F401 — re-exported via __all__
    Pedido,  # noqa: F401 — re-exported via __all__
    PedidoLine,  # noqa: F401 — re-exported via __all__
    PriceHistory,  # noqa: F401 — re-exported via __all__
    Product,  # noqa: F401 — re-exported via __all__
    ProductionCompletion,  # noqa: F401 — re-exported via __all__
    ProductionPlan,  # noqa: F401 — re-exported via __all__
    ProductionPlanOverride,  # noqa: F401 — re-exported via __all__
    ProductionPlanTemplate,  # noqa: F401 — re-exported via __all__
    Recipe,  # noqa: F401 — re-exported via __all__
    RecipeLine,  # noqa: F401 — re-exported via __all__
    RecipePricing,  # noqa: F401 — re-exported via __all__
    RiskItem,  # noqa: F401 — re-exported via __all__
    Sale,  # noqa: F401 — re-exported via __all__
    SaleStockMove,  # noqa: F401 — re-exported via __all__
    SettingsKV,  # noqa: F401 — re-exported via __all__
    ShoppingListItem,  # noqa: F401 — re-exported via __all__
    StockMovement,  # noqa: F401 — re-exported via __all__
    StockStatusConfig,  # noqa: F401 — re-exported via __all__
    StorageKeyword,  # noqa: F401 — re-exported via __all__
    StorageType,  # noqa: F401 — re-exported via __all__
    Supplier,  # noqa: F401 — re-exported via __all__
    Suscripcion,  # noqa: F401 — re-exported via __all__
    Tag,  # noqa: F401 — re-exported via __all__
    TagLink,  # noqa: F401 — re-exported via __all__
    Tenant,  # noqa: F401 — re-exported via __all__
    User,  # noqa: F401 — re-exported via __all__
    WasteLog,  # noqa: F401 — re-exported via __all__
    WishlistItem,  # noqa: F401 — re-exported via __all__
)
from app.rms.models_legacy import __all__ as _legacy_all  # noqa: F401 — re-exported via __all__
