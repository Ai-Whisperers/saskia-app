"""app/rms/models/sales/stock.py — Stock movement for sales.

Phase 2B: Structural refactoring for domain-driven design.

Stock movement entities specifically for sales transactions.
"""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.rms.models.core import Base


class SaleStockMove(Base):
    """Tracks stock movement for sales transactions."""

    __tablename__ = "sale_stock_move"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sale_id: Mapped[str] = mapped_column(String(32), ForeignKey("sale.sale_id"), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("product.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(Integer, nullable=False)

    # Relationships
    sale: Mapped["Sale"] = relationship("Sale", back_populates="stock_moves")

    def __repr__(self) -> str:
        return f"SaleStockMove(id={self.id}, sale_id='{self.sale_id}', quantity={self.quantity})"
