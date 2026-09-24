"""app/rms/models/sales/tags.py — Tagging system for sales.

Phase 2B: Structural refactoring for domain-driven design.

Tag entities and relationships for sales categorization.
"""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.rms.models.core import Base


class Tag(Base):
    """Tag entity for sales categorization."""
    
    __tablename__ = "tag"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#cccccc")
    
    # Relationships
    links: Mapped[list["TagLink"]] = relationship("TagLink", back_populates="tag")
    
    def __repr__(self):
        return f"Tag(id={self.id}, name='{self.name}', color='{self.color}')"


class TagLink(Base):
    """Many-to-many relationship between tags and sales."""
    
    __tablename__ = "tag_link"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tag.id"), nullable=False)
    sale_id: Mapped[str] = mapped_column(String(32), ForeignKey("sale.sale_id"), nullable=False)
    
    # Relationships
    tag: Mapped["Tag"] = relationship("Tag", back_populates="links")
    
    def __repr__(self):
        return f"TagLink(id={self.id}, tag_id={self.tag_id}, sale_id='{self.sale_id}')"