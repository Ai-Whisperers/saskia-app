"""app/rms/models/__init__.py — Models package with domain-driven structure.

Phase 2B: Structural refactoring for domain-driven design.

This package provides SQLAlchemy models organized by domain and sub-domain
for better maintainability and separation of concerns.

Domain Structure:
- core/: Common base classes and utilities
- sales/: Sales domain with sub-modules (core, customer, stock, tags, pricing)
- inventory/: Inventory management
- orders/: Order management
- production/: Production planning
- procurement/: Procurement and supplier management
- delivery/: Delivery management
- auth/: Authentication and authorization
- audit/: Audit logging
- herbus_drive/: External integrations

Usage:
    from app.rms.models import Sale, Customer, Product
"""

from .core import Base
from .channels import Channel
from .inventory import Ingredient, Product, Recipe, RecipeLine, IngredientPriceEvent, PriceHistory
from .orders import Pedido, PedidoLine
from .production import ProductionCompletion, ProductionPlan, ProductionPlanOverride, ProductionPlanTemplate
from .procurement import ImportBatch, ShoppingListItem, StockMovement, Supplier, WasteLog
from .delivery import DeliveryZone
from .auth import User, AuditLog, SettingsKV, Tenant
from .herbus_drive import BankTransaction, ComplianceInfo, MarketBenchmark, MarketPriceReference, RiskItem, WishlistItem
from .audit import AppMeta

# Import sales from sub-package
from .sales import Sale, Customer, SaleStockMove, Tag, TagLink, RecipePricing

__all__ = [
    # Core
    "Base",
    "Channel",
    
    # Sales domain
    "Sale",
    "Customer",
    "SaleStockMove", 
    "Tag",
    "TagLink",
    "RecipePricing",
    
    # Inventory domain
    "Ingredient",
    "Product",
    "Recipe",
    "RecipeLine",
    "IngredientPriceEvent",
    "PriceHistory",
    
    # Orders domain
    "Pedido",
    "PedidoLine",
    
    # Production domain
    "ProductionCompletion",
    "ProductionPlan",
    "ProductionPlanOverride",
    "ProductionPlanTemplate",
    
    # Procurement domain
    "ImportBatch",
    "ShoppingListItem",
    "StockMovement",
    "Supplier",
    "WasteLog",
    
    # Delivery domain
    "DeliveryZone",
    
    # Auth domain
    "User",
    "AuditLog",
    "SettingsKV",
    "Tenant",
    
    # External integrations
    "BankTransaction",
    "ComplianceInfo",
    "MarketBenchmark",
    "MarketPriceReference",
    "RiskItem",
    "WishlistItem",
    
    # Audit
    "AppMeta",
]