"""app.rms.models — single source of truth (pre-refactor models.py).

The Phase-2B domain-package refactor (fb57f00) shipped broken: renamed
tables (Sale/Customer PascalCase) broke every FK, dropped 12 model
classes (catalogs, storage, presets), rewrote sale_stock_move with the
wrong schema, and left db.py with a syntax error. Until the refactor is
redone properly, this package re-exports the last known-good monolithic
models.py (commit b9b5288) which the entire app + 2140-test suite runs
green against. The domain submodules remain on disk for the redo.
"""
from app.rms.models_legacy import *

# Also export names legacy __all__ may miss
from app.rms.models_legacy import (
    AppMeta,  # noqa: F401 — re-exported
    AuditLog,  # noqa: F401 — re-exported
    BankTransaction,  # noqa: F401 — re-exported
    Category,  # noqa: F401 — re-exported
    Channel,  # noqa: F401 — re-exported
    ComplianceInfo,  # noqa: F401 — re-exported
    Customer,  # noqa: F401 — re-exported
    DateRangePreset,  # noqa: F401 — re-exported
    DeliveryZone,  # noqa: F401 — re-exported
    ImportBatch,  # noqa: F401 — re-exported
    Ingredient,  # noqa: F401 — re-exported
    IngredientPriceEvent,  # noqa: F401 — re-exported
    IngredientVariant,  # noqa: F401 — re-exported
    MarginTier,  # noqa: F401 — re-exported
    MarketBenchmark,  # noqa: F401 — re-exported
    MarketPriceReference,  # noqa: F401 — re-exported
    MessageTemplate,  # noqa: F401 — re-exported
    PaymentMethod,  # noqa: F401 — re-exported
    Pedido,  # noqa: F401 — re-exported
    PedidoLine,  # noqa: F401 — re-exported
    PriceHistory,  # noqa: F401 — re-exported
    Product,  # noqa: F401 — re-exported
    ProductionCompletion,  # noqa: F401 — re-exported
    ProductionPlan,  # noqa: F401 — re-exported
    ProductionPlanOverride,  # noqa: F401 — re-exported
    ProductionPlanTemplate,  # noqa: F401 — re-exported
    Recipe,  # noqa: F401 — re-exported
    RecipeLine,  # noqa: F401 — re-exported
    RecipePricing,  # noqa: F401 — re-exported
    RiskItem,  # noqa: F401 — re-exported
    Sale,  # noqa: F401 — re-exported
    SaleStockMove,  # noqa: F401 — re-exported
    SettingsKV,  # noqa: F401 — re-exported
    ShoppingListItem,  # noqa: F401 — re-exported
    StockMovement,  # noqa: F401 — re-exported
    StockStatusConfig,  # noqa: F401 — re-exported
    StorageKeyword,  # noqa: F401 — re-exported
    StorageType,  # noqa: F401 — re-exported
    Supplier,  # noqa: F401 — re-exported
    Tag,  # noqa: F401 — re-exported
    TagLink,  # noqa: F401 — re-exported
    Tenant,  # noqa: F401 — re-exported
    User,  # noqa: F401 — re-exported
    WasteLog,  # noqa: F401 — re-exported
    WishlistItem,  # noqa: F401 — re-exported
)
from app.rms.models_legacy import __all__ as _legacy_all  # noqa: F401 — re-exported
