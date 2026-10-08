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

from app.rms.models_legacy import *  # noqa: F403 — re-export shim for the public API

# Also export names legacy __all__ may miss
from app.rms.models_legacy import (
    AppMeta,
    AuditLog,
    BankTransaction,
    CashSession,
    Category,
    Channel,
    CommunicationLog,
    ComplianceInfo,
    CreditAccount,
    CreditTransaction,
    Customer,
    CustomerAddress,
    CustomerInvoiceProfile,
    DateRangePreset,
    DeliveryZone,
    Expense,
    FreezerTemperatureLog,
    ImportBatch,
    Ingredient,
    IngredientPriceEvent,
    IngredientVariant,
    MarginTier,
    MarketBenchmark,
    MarketPriceReference,
    Menu,
    MenuItem,
    MessageTemplate,
    PaymentMethod,
    Pedido,
    PedidoEvent,
    PedidoLine,
    PriceHistory,
    Product,
    ProductionClosedDay,
    ProductionCompletion,
    ProductionPlan,
    ProductionPlanOverride,
    ProductionPlanTemplate,
    Recipe,
    RecipeLine,
    RecipePricing,
    RiskItem,
    Sale,
    SalePayment,
    SaleStockMove,
    SettingsKV,
    ShoppingListItem,
    StockMovement,
    StockStatusConfig,
    StorageKeyword,
    StorageType,
    Supplier,
    Suscripcion,
    Tag,
    TagLink,
    Tenant,
    User,
    WasteLog,
    WishlistItem,
)
from app.rms.models_legacy import __all__ as _legacy_all

# Also export new models not in legacy
from .closure import MonthlyClosure

__all__ = [*_legacy_all, "MonthlyClosure"]
