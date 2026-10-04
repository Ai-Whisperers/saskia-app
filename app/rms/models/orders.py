from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.rms.models.core import Base

from .channels import Channel

"""
app/rms/models/orders.py — Pre-orders / pickup workflow: Pedido, PedidoLine.

Extracted from app/rms/models.py on 2026-09-23 (Phase 3.1 refactor).
All models here share the same declarative Base as the rest of the
project — see app/rms/models/core.py.
"""


class Pedido(Base):
    """A pre-order (pedido) — Phase 3 (2026-09-17 prelaunch roadmap).

    Most pedidos come in via WhatsApp the day before or morning-of for pickup.
    A pedido can have multiple PedidoLine items. Status moves through
    pending → confirmed → ready → fulfilled, or is cancelled. A public
    pickup-share token (random base32-ish, 8 chars) is generated at create
    time so the customer can fetch a confirmation page without logging in.

    fields:
      customer_id           — optional FK to Customer (pickup may be a stranger)
      customer_name         — denormalized for WhatsApp pedidos with no Customer row
      customer_phone        — index for fast phone lookup; optional
      promised_date         — when the customer expects pickup (Date)
      promised_time         — "HH:MM" local Asunción; optional
      channel               — whatsapp | pedidosya | mostrador | phone | other
      status                — pending | confirmed | ready | fulfilled | cancelled
      payment_intent        — efectivo | transferencia | qr | tarjeta | otro
      notes                 — free text
      public_token          — 8-char unique URL token for /p/{token}
      fulfilled_at          — set by the /fulfill endpoint
      fulfilled_sale_id     — link to the first Sale created on fulfillment
                              (multi-line pedidos create N sales; only the first
                              is linked here for back-reference)
    """

    __tablename__ = "pedido"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id"), index=True, nullable=True
    )
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    customer_phone: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    promised_date: Mapped[datetime] = mapped_column(Date, nullable=False, index=True)
    promised_time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    channel: Mapped[Channel] = mapped_column(
        Enum(Channel), nullable=False, default=Channel.default()
    )

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    payment_intent: Mapped[str] = mapped_column(String(32), nullable=False, default="efectivo")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # HEREBUS integration: link to delivery zone (drives cost + min order)
    delivery_zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("delivery_zone.id"), nullable=True, index=True
    )
    # Migration 069 delivery/facturación (kept in sync with models_legacy.Pedido):
    address_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_window_start: Mapped[str | None] = mapped_column(String(8), nullable=True)
    delivery_window_end: Mapped[str | None] = mapped_column(String(8), nullable=True)
    invoice_ruc: Mapped[str | None] = mapped_column(String(20), nullable=True)
    invoice_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    public_token: Mapped[str] = mapped_column(
        String(40), nullable=False, unique=True, index=True, default=""
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fulfilled_sale_id: Mapped[int | None] = mapped_column(
        ForeignKey("sale.id"), nullable=True, index=True
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # P1-B3: customer-uploaded comprobante de pago from /p/{public_token}.
    # Relative path like "payment_receipts/123/2026-09-29_141503.jpg".
    payment_receipt_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_receipt_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    lines: Mapped[list["PedidoLine"]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan"
    )
    customer: Mapped["Customer | None"] = relationship()  # noqa: F821 — SQLAlchemy 2.0 forward ref
    delivery_zone: Mapped["DeliveryZone | None"] = relationship(  # noqa: F821 — SQLAlchemy 2.0 forward ref
        back_populates="pedidos"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','confirmed','ready','fulfilled','cancelled')",
            name="ck_pedido_status",
        ),
    )


class PedidoLine(Base):
    """A line in a pedido. Mirrors the PedidoLine spec in the 2026-09-17 plan.

    qty is float (paraguay bakeries sell by weight too — 0.5 kg of bread, etc.).
    unit_price_gs is SNAPSHOT — even if the product's sale_price_gs changes later.
    fulfilled_qty starts at 0 and is updated when /pedidos/{id}/fulfill runs.
    """

    __tablename__ = "pedido_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pedido_id: Mapped[int] = mapped_column(
        ForeignKey("pedido.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False, index=True)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price_gs: Mapped[int] = mapped_column(Integer, nullable=False)
    fulfilled_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    pedido: Mapped["Pedido"] = relationship(back_populates="lines")
    product: Mapped["Product"] = relationship()  # noqa: F821 — SQLAlchemy 2.0 forward ref

    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_pedido_line_qty_positive"),
        CheckConstraint("unit_price_gs >= 0", name="ck_pedido_line_price_nonneg"),
    )
