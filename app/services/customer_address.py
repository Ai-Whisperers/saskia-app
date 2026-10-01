"""app/services/customer_address.py — address composition + invoice-profile helpers.

Phase 13 (2026-10-01): delivery UX research synthesis. This module
holds the small bits of business logic that glue the structured
columns on CustomerAddress + CustomerInvoiceProfile to the legacy
single-text columns the receipt + dispatch tickets still consume.

Keeping these helpers out of the SQLAlchemy models keeps models pure
and lets the cashier UI compose whatever it needs on the way in.
"""
from __future__ import annotations

from typing import Any, Mapping


# ── Address composition (structured → single-line text) ───────────

def compose_address_text(addr: Mapping[str, Any] | None) -> str:
    """Compose a one-line summary from the structured address columns.

    Matches how MercadoLibre PY + Lightspeed X render an address for
    confirmation screens — full structured data is preserved on the
    row, but a single line catches everything for the receipt and
    the dispatch ticket (sms SMS is 160ch, so brevity helps).

    Order chosen to match how operators in Paraguay read addresses:
    calle principal + secundaria + número → edificio / piso / unidad
    → barrio → ciudad → departamento.
    """
    if addr is None:
        return ""
    parts: list[str] = []

    cp = (addr.get("calle_principal") or "").strip()
    cs = (addr.get("calle_secundaria") or "").strip()
    n = (addr.get("numero") or "").strip()
    if cp:
        line = cp
        if cs:
            line = f"{line} e/ {cs}"
        if n:
            line = f"{line} {n}"
        parts.append(line)

    edif = (addr.get("edificio") or "").strip()
    piso = (addr.get("piso") or "").strip()
    unidad = (addr.get("unidad") or "").strip()
    if edif:
        extra_bits: list[str] = []
        if piso:
            extra_bits.append(f"piso {piso}")
        if unidad:
            extra_bits.append(f"unidad {unidad}")
        if extra_bits:
            parts.append(f"{edif} ({', '.join(extra_bits)})")
        else:
            parts.append(edif)
    elif piso or unidad:
        # piso/unidad without building — still useful on the receipt
        bits = []
        if piso:
            bits.append(f"piso {piso}")
        if unidad:
            bits.append(f"unidad {unidad}")
        parts.append(", ".join(bits))

    barrio = (addr.get("barrio") or "").strip()
    ciudad = (addr.get("ciudad") or "").strip()
    departamento = (addr.get("departamento") or "").strip()

    # Locality block: barrio is optional, ciudad is required-ish for
    # delivery; if neither is set we fall through silently.
    loc_parts: list[str] = []
    if barrio:
        loc_parts.append(f"Barrio {barrio}")
    if ciudad:
        loc_parts.append(ciudad)
    elif departamento:  # no city but we have a department → still useful
        loc_parts.append(departamento)
    if loc_parts:
        parts.append(", ".join(loc_parts))
    elif departamento and ciudad:
        parts.append(departamento)

    return ", ".join(p for p in parts if p)


def address_alias_label(addr: Mapping[str, Any] | None) -> str:
    """Pick the display label for the address picker. Aliases first
    ("Casa de tu mamá"), falls back to the composed text if no label."""
    if addr is None:
        return ""
    label = (addr.get("label") or "").strip()
    if label:
        return label
    text = compose_address_text(addr)
    return text[:48] + ("…" if len(text) > 48 else "")


# ── Address kind enum (app-layer, mirrors DB CHECK later) ─────────

ADDRESS_KINDS = ("HOME", "WORK", "FAMILY", "OTHER")
"""Allowed values for CustomerAddress.address_kind. Enforced at app
layer (sqlite ALTER TABLE … ADD CONSTRAINT is limited); a follow-up
migration could add a DB CHECK when we cut over to Postgres native."""

INVOICE_TIPOS_DOCUMENTO = (
    "CI_PARAGUAYA", "RUC", "PASAPORTE", "CEDULA_EXTRANJERA",
    "CARNET_RESIDENCIA", "INNOMINADO", "DIPLOMATICA_EXONERACION", "OTRO",
)
"""7-value SIFEN enum (https://sisfe.com.py/documentacion.html)."""

INVOICE_TIPOS_OPERACION = ("B2B", "B2C", "B2G", "EXTRANJERO")
"""4-value SIFEN enum. "EXTRANJERO" is what SIFEN calls B2F."""


# ── Invoice profile selection ─────────────────────────────────────

def default_invoice_profile_payload(profiles: list[Mapping[str, Any]] | None) -> list[dict] | None:
    """Return the cashier-facing payload for the picker dropdown:
    [{id, label, ruc_ci, razon_social, tipo_documento, tipo_operacion}, ...]
    Sorted so the default (is_default=1) is first, then by alias."""
    if not profiles:
        return None
    items = []
    for p in profiles:
        if not p.get("is_active", True):
            continue
        items.append({
            "id": p["id"],
            "label": p.get("alias") or p.get("razon_social") or "",
            "ruc_ci": p.get("ruc_ci") or "",
            "razon_social": p.get("razon_social") or "",
            "tipo_documento": p.get("tipo_documento") or "CI_PARAGUAYA",
            "tipo_operacion": p.get("tipo_operacion") or "B2C",
            "is_default": bool(p.get("is_default")),
        })
    items.sort(key=lambda x: (not x["is_default"], x["label"].lower()))
    return items


def invoice_profile_summary(profile: Mapping[str, Any] | None) -> str:
    """Render the profile for the receipt / dispatch ticket."""
    if not profile:
        return ""
    alias = profile.get("alias") or ""
    ruc = profile.get("ruc_ci") or ""
    razon = profile.get("razon_social") or ""
    return f"{alias}: {razon} — RUC/CI {ruc}".strip(" —")


# ── Delivery preference (pedido-level window) ────────────────────

DELIVERY_PREFERENCES = ("asap", "window", "scheduled")

# 18 departamentos + Asunción (Capital). Used by address_departamento combo.
PARAGUAY_DEPARTMENTS = (
    "Asunción",
    "Alto Paraguay",
    "Alto Paraná",
    "Amambay",
    "Boquerón",
    "Caaguazú",
    "Caazapá",
    "Canindeyú",
    "Central",
    "Concepción",
    "Cordillera",
    "Guairá",
    "Itapúa",
    "Misiones",
    "Ñeembucú",
    "Paraguarí",
    "Presidente Hayes",
    "San Pedro",
)


def ventana_text(pref: str | None, start: str | None, end: str | None,
                 scheduled_date: str | None = None) -> str:
    """Render the preferred-arrival window for the receipt.

    Following your spec: NOT a delivery promise, just a guidance window.
    The trailing "(no es garantía)" makes this explicit to the rider.
    """
    if pref == "scheduled" and scheduled_date:
        if start and end:
            return f"Programado: {scheduled_date}, {start}–{end} (no es garantía)"
        return f"Programado: {scheduled_date} (no es garantía)"
    if pref == "window":
        if start and end:
            return f"Ventana preferida: {start}–{end} (no es garantía)"
        if start:
            return f"Ventana preferida desde {start} (no es garantía)"
        return "Ventana preferida (no es garantía)"
    if pref == "asap" or pref is None:
        return "Lo antes posible"
    return ""


__all__ = [
    "ADDRESS_KINDS",
    "INVOICE_TIPOS_DOCUMENTO",
    "INVOICE_TIPOS_OPERACION",
    "DELIVERY_PREFERENCES",
    "compose_address_text",
    "address_alias_label",
    "default_invoice_profile_payload",
    "invoice_profile_summary",
    "ventana_text",
]