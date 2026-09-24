"""app.rms.models — single source of truth (pre-refactor models.py).

The Phase-2B domain-package refactor (fb57f00) shipped broken: renamed
tables (Sale/Customer PascalCase) broke every FK, dropped 12 model
classes (catalogs, storage, presets), rewrote sale_stock_move with the
wrong schema, and left db.py with a syntax error. Until the refactor is
redone properly, this package re-exports the last known-good monolithic
models.py (commit b9b5288) which the entire app + 2140-test suite runs
green against. The domain submodules remain on disk for the redo.
"""
from app.rms.models_legacy import *  # noqa: F401,F403
from app.rms.models_legacy import __all__ as _legacy_all  # noqa: F401

# Also export names legacy __all__ may miss
from app.rms.models_legacy import (  # noqa: F401
    IngredientVariant, StorageKeyword, Category, DateRangePreset,
    MarginTier, MessageTemplate, PaymentMethod, StockStatusConfig,
    StorageType, AppMeta, Channel, PriceHistory, IngredientPriceEvent,
    SaleStockMove, WasteLog, ComplianceInfo, Customer, Sale, Product,
    Recipe, RecipeLine, Ingredient, User, AuditLog, SettingsKV, Tenant,
    Supplier, Tag, TagLink, Pedido, PedidoLine, ProductionPlan,
    ProductionPlanTemplate, ProductionPlanOverride, ProductionCompletion,
    ShoppingListItem, StockMovement, ImportBatch, DeliveryZone,
    RiskItem, WishlistItem, MarketBenchmark, MarketPriceReference,
    BankTransaction, RecipePricing,
)
