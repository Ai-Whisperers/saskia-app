"""app/rms/invoicing.py — Phase 1.B fiscal invoice snapshot + numbering.

Paraguayan invoice rules per Ley 125/91, Decreto 6539/05, Ley 7165.

Two scenarios:
  1. IRE RESIMPLE — single Boleta Resimple per sale, sequential number per
     timbrado. VAT does NOT itemize on the boleta (cuota fija trimestral
     covers income tax; the sale is not subject to IVA itemization).
  2. IVA General — invoice (Factura) with IVA base + IVA amount itemized.
     Sequential per punto de expedición.

`compute_invoice_snapshot()` is the pure function: takes the unit price +
discount, returns iva_rate / iva_base / iva_amount. Idempotent.

`allocate_invoice_number()` is the stateful step: atomically increments
the ComplianceInfo row's `next_boleta_resimple_number` or
`next_factura_number` counter and returns the assigned number. Atomic via
a SELECT-then-UPDATE inside the caller's transaction.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.rms.constants import DEFAULT_IVA_RATE
from app.rms.models import ComplianceInfo


def compute_invoice_snapshot(
    session: Session,
    *,
    product_id: int,
    qty: float,
    unit_price_gs: int,
    discount_gs: int,
    invoice_type: str,
) -> dict:
    """Compute iva_rate, iva_base_gs, iva_amount_gs for a sale.

    For RESIMPLE: returns iva_amount_gs=0 (cuota fija, no itemization).
    For IVA General (factura): computes base + iva per the product's rate.

    `unit_price_gs` is integer Gs. (per AGENTS.md rule #4).
    `qty` is float (fractional units like 0.5 kg).
    """
    from app.rms.models import Product

    # Default from compliance info if product has no rate set
    ci = session.get(ComplianceInfo, 1)
    default_rate = ci.iva_default_rate if ci else DEFAULT_IVA_RATE

    if invoice_type == "boleta_resimple":
        # RESIMPLE: IRE covered by fixed quarterly cuota; no IVA itemization.
        return {
            "iva_rate": "0",  # Sentinel: "0" means "not applicable"
            "iva_base_gs": 0,
            "iva_amount_gs": 0,
            "default_rate": default_rate,
        }

    if invoice_type == "none":
        return {"iva_rate": "0", "iva_base_gs": 0, "iva_amount_gs": 0, "default_rate": default_rate}

    # Factura (IVA General)
    product = session.get(Product, product_id)
    rate_str = product.iva_rate if product and product.iva_rate else default_rate

    # Compute total sale (discount applied)
    gross = round(float(qty) * float(unit_price_gs))
    net = max(0, gross - int(discount_gs or 0))

    if rate_str == "exento":
        return {
            "iva_rate": "exento",
            "iva_base_gs": net,
            "iva_amount_gs": 0,
            "default_rate": default_rate,
        }

    # rate_str is "5" or "10"
    rate_pct = int(rate_str)
    # IVA base = net / (1 + rate_pct/100). IVA amount = net - base.
    # Use round-half-up per AGENTS.md rule #3 (round at persistence site).
    # Python's int() floors; add 0.5 then int() for half-up.
    base = int(net * 100 / (100 + rate_pct) + 0.5)
    iva_amount = net - base
    return {
        "iva_rate": rate_str,
        "iva_base_gs": base,
        "iva_amount_gs": iva_amount,
        "default_rate": default_rate,
    }


def allocate_invoice_number(session: Session, invoice_type: str) -> int:
    """Atomically allocate the next sequential invoice number.

    Counter lives on ComplianceInfo:
      - 'boleta_resimple' → next_boleta_resimple_number
      - 'factura' → next_factura_number

    Returns the assigned number. Caller is responsible for committing.
    Counter starts at 1 (the migration seeds this).

    Atomicity: uses `with_for_update=True` on the ComplianceInfo read so
    Postgres takes a row-level lock. Without this, two concurrent sales
    can read the same counter value and emit duplicate fiscal invoice
    numbers — rejected by the tax authority. SQLite is single-writer so
    `with_for_update` is a no-op there, but the call is harmless.
    """
    # Only use FOR UPDATE on Postgres (dialect-aware). SQLite serializes
    # writes anyway, so the lock would be redundant overhead.
    dialect_name = session.bind.dialect.name if session.bind else "sqlite"
    use_for_update = dialect_name == "postgresql"

    ci = session.get(ComplianceInfo, 1, with_for_update=use_for_update)
    if ci is None:
        ci = ComplianceInfo(id=1)
        session.add(ci)
        session.flush()

    if invoice_type == "boleta_resimple":
        n = ci.next_boleta_resimple_number
        ci.next_boleta_resimple_number = n + 1
        return n
    if invoice_type == "factura":
        n = ci.next_factura_number
        ci.next_factura_number = n + 1
        return n
    raise ValueError(f"Cannot allocate invoice number for type {invoice_type!r}")


__all__ = ["allocate_invoice_number", "compute_invoice_snapshot"]
