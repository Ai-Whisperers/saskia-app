"""app/rms/models/sales/__init__.py — Sales domain package.

Phase 2B: Structural refactoring for domain-driven design.

Sales domain entities organized by sub-concerns for better maintainability.
"""

from .core import Sale
from .customer import Customer
from .pricing import RecipePricing
from .stock import SaleStockMove
from .tags import Tag, TagLink

__all__ = [
    "Customer",
    "RecipePricing",
    "Sale",
    "SaleStockMove",
    "Tag",
    "TagLink",
]
