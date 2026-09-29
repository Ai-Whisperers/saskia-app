"""app/rms/models/common.py — Common field definitions and types.

Phase 2B: Structural refactoring for domain-driven design.

This module provides common field definitions and types used across
multiple domains to ensure consistency and reduce duplication.
"""

from datetime import datetime
from typing import Annotated

from sqlalchemy import DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column

# Common timestamp fields with consistent typing
CreatedTimestamp = Annotated[datetime, mapped_column(DateTime, nullable=False, default=datetime.now)]
UpdatedTimestamp = Annotated[datetime, mapped_column(DateTime, nullable=False, default=datetime.now)]

# Common price field (consistent across all domains)
PriceGs = Annotated[float, mapped_column(Float, nullable=False, default=0.0)]


class CommonFieldsMixin:
    """Mixin class providing common fields for models that need them."""

    created_at: Mapped[CreatedTimestamp]
    updated_at: Mapped[UpdatedTimestamp]

    # Optional price field for domain models that need it
    price_gs: Mapped[PriceGs] | Mapped[int] | None = None
