"""app/rms/models/core.py — the SQLAlchemy declarative base.

This module holds ONLY the `Base` class. All ORM model classes in
`app/rms/models/` import `Base` from here, so SQLAlchemy's mapper
registry sees them all under one declarative base.

Why split Base out: the original monolithic `models.py` had every
class together. Splitting them into per-domain sub-modules while
keeping one shared Base ensures cross-domain `relationship()` strings
(e.g. `relationship("Sale", back_populates="stock_moves")`) still
resolve correctly at mapper-config time.

This module is intentionally tiny. Do NOT add model classes here.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy declarative base. All models inherit from this."""


__all__ = ["Base"]
