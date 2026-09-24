"""app/rms/models/sales/pricing.py — Pricing management for sales.

Phase 2B: Structural refactoring for domain-driven design.

Pricing-related entities and management functionality.
"""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.rms.models.core import Base


class RecipePricing(Base):
    """Pricing information for recipes/products."""
    
    __tablename__ = "RecipePricing"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(Integer, ForeignKey("Recipe.id"), nullable=False)
    price_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_gs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    margin_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Relationships
    recipe: Mapped["Recipe"] = relationship("Recipe")
    
    def __repr__(self):
        return f"RecipePricing(id={self.id}, recipe_id={self.recipe_id}, price_gs={self.price_gs})"