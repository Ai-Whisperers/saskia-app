"""app/rms/models/channels.py — unified channel types for sales and pedidos.

Phase 2A ticket: Unify sales vs pedidos channel enums.

This module provides a single source of truth for sales channels,
replacing the duplicated string constants in schemas.py and
ensuring consistency between Pedido and Sale models.
"""

from enum import Enum
from typing import Annotated


class Channel(str, Enum):
    """Unified sales channel enum for both Pedido and Sale models.

    Replaces string constants in app/rms/schemas.py to ensure
    consistency between domain models and validation.

    SASKIA-204 (2026-10-07): the 4 HEREBUS channels (RETAIL,
    WHOLESALE, DISTRIBUTOR, EVENTUAL) were added in migration 112 to
    surface the silent skew where 9 of 346 sales were being collapsed
    to "mostrador" by the import script (line 622 fallback). They
    must stay in display_order() to appear in the /ventas filter
    dropdown, and in allowed_values() so the Pydantic validator
    accepts them.
    """

    MOSTRADOR = "mostrador"
    MOSTRADOR_ENCARGO = "mostrador-encargo"
    WHATSAPP = "whatsapp"
    PEDIDOSYA = "pedidosya"
    MONCHIS = "monchis"
    OTHER = "other"  # fallback for unknown values
    # SASKIA-204: HEREBUS channels (added 2026-10-07)
    RETAIL = "retail"
    WHOLESALE = "wholesale"
    DISTRIBUTOR = "distributor"
    EVENTUAL = "eventual"

    @classmethod
    def allowed_values(cls) -> set[str]:
        """Return all allowed channel values."""
        return {member.value for member in cls}

    @classmethod
    def default(cls) -> str:
        """Return default channel value."""
        return cls.MOSTRADOR.value

    @classmethod
    def display_order(cls) -> tuple[str, ...]:
        """Return channels in display order (first = most prominent).

        SASKIA-204 (2026-10-07): HEREBUS channels appended after the
        original 6 so the /ventas filter shows them but doesn't
        reorder the operator's mental model of "front-of-house"
        channels. Updated by the channel-list sorted-by-count sweep
        if the operator wants to promote one.
        """
        return (
            cls.MOSTRADOR.value,
            cls.MOSTRADOR_ENCARGO.value,
            cls.WHATSAPP.value,
            cls.PEDIDOSYA.value,
            cls.MONCHIS.value,
            cls.RETAIL.value,
            cls.WHOLESALE.value,
            cls.DISTRIBUTOR.value,
            cls.EVENTUAL.value,
            cls.OTHER.value,
        )


# SQLAlchemy enum type for migrations and model definitions
CHANNEL_ENUM_TYPE = Annotated[Channel, "Channel enum ensuring only valid channels are accepted"]
