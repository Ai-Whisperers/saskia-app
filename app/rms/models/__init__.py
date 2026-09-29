"""app.rms.models — single source of truth (pre-refactor models.py).

The Phase-2B domain-package refactor (fb57f00) shipped broken: renamed
tables (Sale/Customer PascalCase) broke every FK, dropped 12 model
classes (catalogs, storage, presets), rewrote sale_stock_move with the
wrong schema, and left db.py with a syntax error. Until the refactor is
redone properly, this package re-exports the last known-good monolithic
models.py (commit b9b5288) which the entire app + 2140-test suite runs
green against. The domain submodules remain on disk for the redo.
"""
from app.rms.models_legacy import *  # noqa: F403

# Also export names legacy __all__ may miss
from app.rms.models_legacy import (  # noqa: F401
    AppMeta,
    AuditLog,
    BankTransaction,
    Category,
    Channel,
    ComplianceInfo,
    Customer,
    DateRangePreset,
    DeliveryZone,
    ImportBatch,
    Ingredient,
    IngredientPriceEvent,
    IngredientVariant,
    MarginTier,
    MarketBenchmark,
    MarketPriceReference,
    MessageTemplate,
    PaymentMethod,
    Pedido,
    PedidoLine,
    PriceHistory,
    Product,
    ProductionCompletion,
    ProductionPlan,
    ProductionPlanOverride,
    ProductionPlanTemplate,
    Recipe,
    RecipeLine,
    RecipePricing,
    RiskItem,
    Sale,
    SaleStockMove,
    SettingsKV,
    ShoppingListItem,
    StockMovement,
    StockStatusConfig,
    StorageKeyword,
    StorageType,
    Supplier,
    Tag,
    TagLink,
    Tenant,
    User,
    WasteLog,
    WishlistItem,
)
from app.rms.models_legacy import __all__ as _legacy_all  # noqa: F401
