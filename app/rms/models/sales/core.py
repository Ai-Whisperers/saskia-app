"""app/rms/models/sales/core.py — Core sales entities.

Phase 2B: Structural refactoring for domain-driven design.

Core sales entities that represent the main business objects.
"""

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.rms.models.channels import Channel
from app.rms.models.core import Base


class Sale(Base):
    """Main sales transaction entity."""

    __tablename__ = "sale"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sale_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customer.id"), nullable=True)

    # Sales details
    channel: Mapped[Channel] = mapped_column(
        Enum(Channel), nullable=False, default=Channel.default(), server_default=Channel.default()
    )
    total_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_usd: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer")  # noqa: F821
    stock_moves: Mapped[list["SaleStockMove"]] = relationship(  # noqa: F821
        "SaleStockMove", back_populates="sale"
    )

    def __repr__(self) -> str:
        return f"Sale(id={self.id}, sale_id='{self.sale_id}', total_gs={self.total_gs})"
