"""app/rms/models/sales/stock.py — DEPRECATED (BACKLOG #1).

SaleStockMove was consolidated into stock_movement in this session.
The class is preserved as a no-table stub so any legacy import path
that lands here (`from app.rms.models.sales.stock import SaleStockMove`)
still resolves the symbol — but the table no longer exists in the
database (migration 092 dropped it).

Re-exports the canonical stub from models_legacy so there is exactly
ONE class definition for the deprecated name. Importing
SaleStockMove through this path or through `models_legacy` or through
`models` returns the same class.
"""

from app.rms.models_legacy import SaleStockMove

__all__ = ["SaleStockMove"]
