"""app/rms/models/sales/customer.py — Customer management.

Phase 2B: Structural refactoring for domain-driven design.

Customer-related entities and management functionality.
"""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.rms.models.core import Base


class Customer(Base):
    """Customer entity for sales tracking."""
    
    __tablename__ = "customer"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=True, unique=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    
    # Relationships
    sales: Mapped[list["Sale"]] = relationship("Sale", back_populates="customer")
    
    def __repr__(self):
        return f"Customer(id={self.id}, name='{self.name}', email='{self.email}')"