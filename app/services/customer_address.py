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

    street_line = _build_street_line(addr)
    if street_line:
        parts.append(street_line)

    building_line = _build_building_line(addr)
    if building_line:
        parts.append(building_line)

    locality_line = _build_locality_line(addr)
    if locality_line:
        parts.append(locality_line)

    return ", ".join(p for p in parts if p)


def _build_street_line(addr) -> str:
    """Build the street line (calle principal + secundaria + número).
    
    Extracted from compose_address_text to reduce complexity.
    """
    cp = (addr.get("calle_principal") or "").strip()
    if not cp:
        return ""
    line = cp
    cs = (addr.get("calle_secundaria") or "").strip()
    if cs:
        line = f"{line} e/ {cs}"
    n = (addr.get("numero") or "").strip()
    if n:
        line = f"{line} {n}"
    return line


def _build_building_line(addr) -> str:
    """Build the building line (edificio + piso + unidad).
    
    Extracted from compose_address_text to reduce complexity.
    """
    edif = (addr.get("edificio") or "").strip()
    piso = (addr.get("piso") or "").strip()
    unidad = (addr.get("unidad") or "").strip()
    if edif:
        extra_bits = _collect_floor_unit_bits(piso, unidad)
        if extra_bits:
            return f"{edif} ({', '.join(extra_bits)})"
        return edif
    if piso or unidad:
        bits = _collect_floor_unit_bits(piso, unidad)
        return ", ".join(bits)
    return ""


def _collect_floor_unit_bits(piso: str, unidad: str) -> list[str]:
    """Collect floor/unit bits into a list.
    
    Extracted from _build_building_line to reduce complexity.
    """
    bits = []
    if piso:
        bits.append(f"piso {piso}")
    if unidad:
        bits.append(f"unidad {unidad}")
    return bits


def _build_locality_line(addr) -> str:
    """Build the locality line (barrio + ciudad + departamento).
    
    Extracted from compose_address_text to reduce complexity.
    """
    barrio = (addr.get("barrio") or "").strip()
    ciudad = (addr.get("ciudad") or "").strip()
    departamento = (addr.get("departamento") or "").strip()

    loc_parts = _collect_locality_parts(barrio, ciudad, departamento)
    if loc_parts:
        return ", ".join(loc_parts)
    if departamento and ciudad:
        return departamento
    return ""


def _collect_locality_parts(barrio: str, ciudad: str, departamento: str) -> list[str]:
    """Collect locality parts into a list.
    
    Extracted from _build_locality_line to reduce complexity.
    """
    loc_parts: list[str] = []
    if barrio:
        loc_parts.append(f"Barrio {barrio}")
    if ciudad:
        loc_parts.append(ciudad)
    elif departamento:
        loc_parts.append(departamento)
    return loc_parts


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
    "CI_PARAGUAYA",
    "RUC",
    "PASAPORTE",
    "CEDULA_EXTRANJERA",
    "CARNET_RESIDENCIA",
    "INNOMINADO",
    "DIPLOMATICA_EXONERACION",
    "OTRO",
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
        items.append(
            {
                "id": p["id"],
                "label": p.get("alias") or p.get("razon_social") or "",
                "ruc_ci": p.get("ruc_ci") or "",
                "razon_social": p.get("razon_social") or "",
                "tipo_documento": p.get("tipo_documento") or "CI_PARAGUAYA",
                "tipo_operacion": p.get("tipo_operacion") or "B2C",
                "is_default": bool(p.get("is_default")),
            }
        )
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


def ventana_text(
    pref: str | None, start: str | None, end: str | None, scheduled_date: str | None = None
) -> str:
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
    "DELIVERY_PREFERENCES",
    "INVOICE_TIPOS_DOCUMENTO",
    "INVOICE_TIPOS_OPERACION",
    "address_alias_label",
    "compose_address_text",
    "default_invoice_profile_payload",
    "invoice_profile_summary",
    "ventana_text",
]
