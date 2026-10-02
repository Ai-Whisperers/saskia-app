"""CRUD service for the multi-value contact fields of a Customer.

Phase 16 (2026-10-02): Customer contact info is 1:N now (multiple
phones, multiple invoice profiles, multiple addresses) and the cashier
must be able to list/add/remove them without leaving the pedido flow.

The service keeps the legacy `Customer.phone` / `Customer.invoice_ruc`
/ `Customer.invoice_name` columns in sync with whichever row is marked
is_default. This way legacy code paths still work (single-value mental
model) while the cashier can manage the full N-value reality.

Idempotency:
  - `set_default_phone` is the canonical "pick the default" call.
  - `add_phone` with is_default=True auto-demotes the previous default.
  - `add_invoice_profile` with is_default=True auto-demotes the previous
    default.
  - The Customer.legacy columns are updated last so a failed write
    leaves the multi-value table authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rms.models import (
    Customer,
    CustomerAddress,
    CustomerInvoiceProfile,
    CustomerPhone,
)


# ── value objects (to_dict-friendly for the API layer) ───────────────


@dataclass
class PhoneRow:
    id: int
    phone: str
    kind: str
    label: Optional[str]
    is_default: bool
    is_active: bool
    sort_order: int

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "phone": self.phone,
            "kind": self.kind,
            "label": self.label,
            "is_default": self.is_default,
            "is_active": self.is_active,
            "sort_order": self.sort_order,
        }


@dataclass
class InvoiceProfileRow:
    id: int
    alias: str
    ruc_ci: str
    razon_social: str
    tipo_documento: str
    tipo_operacion: str
    is_default: bool
    is_active: bool

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "alias": self.alias,
            "ruc_ci": self.ruc_ci,
            "razon_social": self.razon_social,
            "tipo_documento": self.tipo_documento,
            "tipo_operacion": self.tipo_operacion,
            "is_default": self.is_default,
            "is_active": self.is_active,
        }


# ── helpers ──────────────────────────────────────────────────────────


def _normalize_phone(raw: str) -> str:
    """Strip common formatting but keep + and digits readable.

    ' +595 981 123 456 ' → '+595 981 123 456'
    '0981-123-456' → '0981 123 456'
    """
    s = (raw or "").strip()
    # Drop everything that isn't + digit or whitespace
    out: list[str] = []
    for ch in s:
        if ch == "+":
            out.append("+" if not out else " ")
        elif ch.isdigit():
            out.append(ch)
        elif ch.isspace():
            if out and out[-1] != " ":
                out.append(" ")
    return "".join(out).strip()


def _sync_customer_legacy_phone(s: Session, customer: Customer) -> None:
    """Copy the default phone row's value to Customer.phone.

    Called after add_phone/set_default_phone to keep the legacy column
    in sync. If no active default exists, leave the column untouched
    (the cashier may have deleted the only phone).
    """
    default = s.execute(
        select(CustomerPhone)
        .where(CustomerPhone.customer_id == customer.id)
        .where(CustomerPhone.is_default.is_(True))
        .where(CustomerPhone.is_active.is_(True))
        .limit(1)
    ).scalar_one_or_none()
    customer.phone = default.phone if default else None


def _sync_customer_legacy_invoice(s: Session, customer: Customer) -> None:
    """Copy the default invoice profile's ruc + name to legacy columns."""
    default = s.execute(
        select(CustomerInvoiceProfile)
        .where(CustomerInvoiceProfile.customer_id == customer.id)
        .where(CustomerInvoiceProfile.is_default.is_(True))
        .where(CustomerInvoiceProfile.is_active.is_(True))
        .limit(1)
    ).scalar_one_or_none()
    if default:
        customer.invoice_ruc = default.ruc_ci
        customer.invoice_name = default.razon_social
    else:
        customer.invoice_ruc = None
        customer.invoice_name = None


# ── phone CRUD ───────────────────────────────────────────────────────


def list_phones(s: Session, customer_id: int) -> List[CustomerPhone]:
    """Return all phones (active first, then inactive), default first."""
    return list(
        s.execute(
            select(CustomerPhone)
            .where(CustomerPhone.customer_id == customer_id)
            .order_by(
                CustomerPhone.is_default.desc(),
                CustomerPhone.is_active.desc(),
                CustomerPhone.sort_order.asc(),
                CustomerPhone.id.asc(),
            )
        ).scalars()
    )


def get_default_phone(s: Session, customer_id: int) -> Optional[CustomerPhone]:
    return s.execute(
        select(CustomerPhone)
        .where(CustomerPhone.customer_id == customer_id)
        .where(CustomerPhone.is_default.is_(True))
        .where(CustomerPhone.is_active.is_(True))
        .limit(1)
    ).scalar_one_or_none()


def add_phone(
    s: Session,
    customer_id: int,
    phone: str,
    *,
    kind: str = "mobile",
    label: Optional[str] = None,
    is_default: bool = False,
    sort_order: int = 0,
) -> CustomerPhone:
    """Add a phone to a customer. Auto-demotes prior default if is_default=True."""
    phone_norm = _normalize_phone(phone)
    if not phone_norm:
        raise ValueError("phone vacío")
    if kind not in ("mobile", "whatsapp", "work", "home", "other"):
        raise ValueError(f"kind inválido: {kind!r}")
    customer = s.get(Customer, customer_id)
    if customer is None:
        raise ValueError(f"customer {customer_id} no existe")

    if is_default:
        # Demote all other defaults
        for p in s.execute(
            select(CustomerPhone).where(
                CustomerPhone.customer_id == customer_id,
                CustomerPhone.is_default.is_(True),
            )
        ).scalars():
            p.is_default = False

    row = CustomerPhone(
        customer_id=customer_id,
        phone=phone_norm,
        kind=kind,
        label=(label or None),
        is_default=is_default,
        is_active=True,
        sort_order=sort_order,
    )
    s.add(row)
    s.flush()
    _sync_customer_legacy_phone(s, customer)
    s.flush()
    return row


def remove_phone(s: Session, customer_id: int, phone_id: int) -> bool:
    """Soft-disable a phone (set is_active=False). Returns True if changed."""
    row = s.get(CustomerPhone, phone_id)
    if row is None or row.customer_id != customer_id:
        return False
    if not row.is_active:
        return False
    row.is_active = False
    if row.is_default:
        # Promote the next-active phone (or none)
        nxt = s.execute(
            select(CustomerPhone)
            .where(
                CustomerPhone.customer_id == customer_id,
                CustomerPhone.id != phone_id,
                CustomerPhone.is_active.is_(True),
            )
            .order_by(CustomerPhone.sort_order.asc(), CustomerPhone.id.asc())
            .limit(1)
        ).scalar_one_or_none()
        if nxt is not None:
            nxt.is_default = True
    customer = s.get(Customer, customer_id)
    if customer is not None:
        _sync_customer_legacy_phone(s, customer)
    s.flush()
    return True


def set_default_phone(s: Session, customer_id: int, phone_id: int) -> bool:
    """Mark one phone as the default (and demote all others)."""
    target = s.get(CustomerPhone, phone_id)
    if target is None or target.customer_id != customer_id:
        return False
    if not target.is_active:
        return False
    for p in s.execute(
        select(CustomerPhone).where(
            CustomerPhone.customer_id == customer_id,
            CustomerPhone.id != phone_id,
        )
    ).scalars():
        p.is_default = False
    target.is_default = True
    customer = s.get(Customer, customer_id)
    if customer is not None:
        _sync_customer_legacy_phone(s, customer)
    s.flush()
    return True


# ── invoice profile CRUD ────────────────────────────────────────────


def list_invoice_profiles(
    s: Session, customer_id: int
) -> List[CustomerInvoiceProfile]:
    return list(
        s.execute(
            select(CustomerInvoiceProfile)
            .where(CustomerInvoiceProfile.customer_id == customer_id)
            .order_by(
                CustomerInvoiceProfile.is_default.desc(),
                CustomerInvoiceProfile.is_active.desc(),
                CustomerInvoiceProfile.id.asc(),
            )
        ).scalars()
    )


def add_invoice_profile(
    s: Session,
    customer_id: int,
    *,
    alias: str,
    ruc_ci: str,
    razon_social: str,
    tipo_documento: str = "CI_PARAGUAYA",
    tipo_operacion: str = "B2C",
    is_default: bool = False,
) -> CustomerInvoiceProfile:
    """Add an invoice profile. If is_default=True, demotes prior defaults."""
    if tipo_documento not in (
        "CI_PARAGUAYA", "RUC", "PASAPORTE", "CEDULA_EXTRANJERA",
        "CARNET_RESIDENCIA", "INNOMINADO", "DIPLOMATICA_EXONERACION", "OTRO",
    ):
        raise ValueError(f"tipo_documento inválido: {tipo_documento!r}")
    if tipo_operacion not in ("B2B", "B2C", "B2G", "EXTRANJERO"):
        raise ValueError(f"tipo_operacion inválido: {tipo_operacion!r}")
    if not ruc_ci.strip():
        raise ValueError("ruc_ci vacío")
    if not razon_social.strip():
        raise ValueError("razon_social vacía")
    customer = s.get(Customer, customer_id)
    if customer is None:
        raise ValueError(f"customer {customer_id} no existe")

    if is_default:
        for p in s.execute(
            select(CustomerInvoiceProfile).where(
                CustomerInvoiceProfile.customer_id == customer_id,
                CustomerInvoiceProfile.is_default.is_(True),
            )
        ).scalars():
            p.is_default = False

    row = CustomerInvoiceProfile(
        customer_id=customer_id,
        alias=alias.strip()[:64],
        ruc_ci=ruc_ci.strip()[:20],
        razon_social=razon_social.strip()[:160],
        tipo_documento=tipo_documento,
        tipo_operacion=tipo_operacion,
        is_default=is_default,
        is_active=True,
    )
    s.add(row)
    s.flush()
    if is_default:
        _sync_customer_legacy_invoice(s, customer)
    s.flush()
    return row


def remove_invoice_profile(
    s: Session, customer_id: int, profile_id: int
) -> bool:
    row = s.get(CustomerInvoiceProfile, profile_id)
    if row is None or row.customer_id != customer_id:
        return False
    if not row.is_active:
        return False
    row.is_active = False
    if row.is_default:
        nxt = s.execute(
            select(CustomerInvoiceProfile)
            .where(
                CustomerInvoiceProfile.customer_id == customer_id,
                CustomerInvoiceProfile.id != profile_id,
                CustomerInvoiceProfile.is_active.is_(True),
            )
            .order_by(CustomerInvoiceProfile.id.asc())
            .limit(1)
        ).scalar_one_or_none()
        if nxt is not None:
            nxt.is_default = True
    customer = s.get(Customer, customer_id)
    if customer is not None and row.is_default:
        _sync_customer_legacy_invoice(s, customer)
    s.flush()
    return True


def set_default_invoice_profile(
    s: Session, customer_id: int, profile_id: int
) -> bool:
    target = s.get(CustomerInvoiceProfile, profile_id)
    if target is None or target.customer_id != customer_id:
        return False
    if not target.is_active:
        return False
    for p in s.execute(
        select(CustomerInvoiceProfile).where(
            CustomerInvoiceProfile.customer_id == customer_id,
            CustomerInvoiceProfile.id != profile_id,
        )
    ).scalars():
        p.is_default = False
    target.is_default = True
    customer = s.get(Customer, customer_id)
    if customer is not None:
        _sync_customer_legacy_invoice(s, customer)
    s.flush()
    return True


# ── address CRUD (limited; full CRUD already in customers router) ──


def list_addresses(s: Session, customer_id: int) -> List[CustomerAddress]:
    return list(
        s.execute(
            select(CustomerAddress)
            .where(CustomerAddress.customer_id == customer_id)
            .where(CustomerAddress.is_active.is_(True))
            .order_by(
                CustomerAddress.is_default.desc(),
                CustomerAddress.sort_order.asc(),
                CustomerAddress.id.asc(),
            )
        ).scalars()
    )
