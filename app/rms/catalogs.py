"""app/rms/catalogs.py — Phase 4 helpers for Channel + PaymentMethod lists.

These tables back the /ventas form-selects and validation. They are
DB-driven so operators can add/edit channels and payment methods from
/settings/channels and /settings/payment-methods without code deploy.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import Channel, PaymentMethod


def list_channels(session: Session, include_inactive: bool = False) -> list[Channel]:
    """Return channels sorted by sort_order."""
    q = select(Channel)
    if not include_inactive:
        q = q.where(Channel.is_active.is_(True))
    q = q.order_by(Channel.sort_order.asc(), Channel.code.asc())
    return list(session.execute(q).scalars())


def list_payment_methods(session: Session, include_inactive: bool = False) -> list[PaymentMethod]:
    """Return payment methods sorted by sort_order."""
    q = select(PaymentMethod)
    if not include_inactive:
        q = q.where(PaymentMethod.is_active.is_(True))
    q = q.order_by(PaymentMethod.sort_order.asc(), PaymentMethod.code.asc())
    return list(session.execute(q).scalars())


def channel_codes(session: Session) -> list[str]:
    """Return just the codes for validation."""
    return [c.code for c in list_channels(session)]


def payment_method_codes(session: Session) -> list[str]:
    """Return just the codes for validation."""
    return [pm.code for pm in list_payment_methods(session)]


def default_channel_code(session: Session) -> str:
    """Return the code marked is_default=True, or 'mostrador' as fallback."""
    row = session.execute(
        select(Channel).where(Channel.is_default.is_(True), Channel.is_active.is_(True))
    ).scalar_one_or_none()
    return row.code if row else "mostrador"


def default_payment_method_code(session: Session) -> str:
    """Return the code marked is_default=True, or 'efectivo' as fallback."""
    row = session.execute(
        select(PaymentMethod).where(PaymentMethod.is_default.is_(True), PaymentMethod.is_active.is_(True))
    ).scalar_one_or_none()
    return row.code if row else "efectivo"


__all__ = [
    "list_channels",
    "list_payment_methods",
    "channel_codes",
    "payment_method_codes",
    "default_channel_code",
    "default_payment_method_code",
]
