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
    """
    MOSTRADOR = "mostrador"
    MOSTRADOR_ENCARGO = "mostrador-encargo"
    WHATSAPP = "whatsapp"
    PEDIDOSYA = "pedidosya"
    MONCHIS = "monchis"
    OTHER = "other"  # fallback for unknown values

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
        """Return channels in display order (first = most prominent)."""
        return (
            cls.MOSTRADOR.value,
            cls.MOSTRADOR_ENCARGO.value,
            cls.WHATSAPP.value,
            cls.PEDIDOSYA.value,
            cls.MONCHIS.value,
        )


# SQLAlchemy enum type for migrations and model definitions
CHANNEL_ENUM_TYPE = Annotated[
    Channel, 
    "Channel enum ensuring only valid channels are accepted"
]

# Legacy constants for backward compatibility (deprecated)
# TODO: Remove these once all code is updated to use Channel enum
ALLOWED_CHANNELS = Channel.allowed_values()
CHANNELS_DISPLAY = Channel.display_order()
CHANNEL_DEFAULT = Channel.default()