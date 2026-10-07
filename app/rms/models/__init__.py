"""app.rms.models — single source of truth (pre-refactor models.py).

The Phase-2B domain-package refactor (fb57f00) shipped broken: renamed
tables (Sale/Customer PascalCase) broke every FK, dropped 12 model
classes (catalogs, storage, presets), rewrote sale_stock_move with the
wrong schema, and left db.py with a syntax error. Until the refactor is
redone properly, this package re-exports the last known-good monolithic
models.py (commit b9b5288) which the entire app + 2140-test suite runs
green against. The domain submodules remain on disk for the redo.

BACKLOG #1 (2026-10-02): sale_stock_move has been deprecated. The
class still exists as a no-table stub (SaleStockMove.__table__ = None)
so any stale import paths still resolve the symbol, but
session.add(SaleStockMove(...)) raises InvalidRequestError. The actual
sale-driven stock-out is now on stock_movement with movement_type='sale'
and reference_type='sale'. Migration 092 dropped the table itself.
"""

from app.rms.models_legacy import *  # noqa: F403 — legacy compatibility layer, all names re-exported intentionally

# Also export names legacy __all__ may miss
from app.rms.models_legacy import (
    AppMeta,  # noqa: F401 — re-exported via __all__
    AuditLog,  # noqa: F401 — re-exported via __all__
    BankTransaction,  # noqa: F401 — re-exported via __all__
    Category,  # noqa: F401 — re-exported via __all__
    Channel,  # noqa: F401 — re-exported via __all__
    CommunicationLog,  # noqa: F401 — re-exported via __all__
    ComplianceInfo,  # noqa: F401 — re-exported via __all__
    Customer,  # noqa: F401 — re-exported via __all__
    CustomerAddress,  # noqa: F401 — re-exported via __all__
    CustomerInvoiceProfile,  # noqa: F401 — Phase 13 multiple invoice profiles
    DateRangePreset,  # noqa: F401 — re-exported via __all__
    DeliveryZone,  # noqa: F401 — re-exported via __all__
    Expense,  # noqa: F401 — Phase 14 operating-expense rows
    FreezerTemperatureLog,  # noqa: F401 — B.6 HACCP freezer temp log
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
    PedidoEvent,  # noqa: F401 — re-exported via __all__
    PedidoLine,  # noqa: F401 — re-exported via __all__
    PriceHistory,  # noqa: F401 — re-exported via __all__
    Product,  # noqa: F401 — re-exported via __all__
    ProductionClosedDay,  # noqa: F401 — re-exported via __all__
    ProductionCompletion,  # noqa: F401 — re-exported via __all__
    ProductionPlan,  # noqa: F401 — re-exported via __all__
    ProductionPlanOverride,  # noqa: F401 — re-exported via __all__
    ProductionPlanTemplate,  # noqa: F401 — re-exported via __all__
    Recipe,  # noqa: F401 — re-exported via __all__
    RecipeLine,  # noqa: F401 — re-exported via __all__
    RecipePricing,  # noqa: F401 — re-exported via __all__
    RiskItem,  # noqa: F401 — re-exported via __all__
    Sale,  # noqa: F401 — re-exported via __all__
    SalePayment,  # noqa: F401 — re-exported via __all__
    CashSession,  # noqa: F401 — re-exported via __all__
    CreditAccount,  # noqa: F401 — re-exported via __all__
    CreditTransaction,  # noqa: F401 — re-exported via __all__
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
    Menu,
    MenuItem,
)
from app.rms.models_legacy import __all__ as _legacy_all

# Also export new models not in legacy
from .closure import MonthlyClosure

__all__ = [*_legacy_all, "MonthlyClosure"]
