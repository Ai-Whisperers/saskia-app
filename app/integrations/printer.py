"""app/rms/printer.py — ESC/POS receipt printer + label printing (E18).

Per docs/plans/2026-09-07-sazon-complete-epic-plan-v3.md E18.

Adds:
- PrinterConfig: kind=network|usb|file, host (network), vendor_id/product_id
  (USB), dst_path (file destination)
- format_receipt(sale, business_name): returns the receipt text + ESC/POS bytes
- format_label(product): shelf label with name + price + optional date
- send_to_printer(config, payload): routes bytes to the right backend
- list_supported_vendors(): quick reference for known thermal printers

The default backend is "file" so this module works in CI / tests; in
production, set PRINTER_* env vars to point at the real device.

ESC/POS commands used:
- ESC @  → initialize printer (0x1b 0x40)
- LF 0x0a → newline
- ESC ! n  → set font size (0..3)
- ESC a n  → alignment (0=left, 1=center, 2=right)
- GS V 1  → partial cut (0x1d 0x56 0x01)
"""

from __future__ import annotations

import os
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# --- ESC/POS command constants ---


ESC = b"\x1b"
GS = b"\x1d"

INIT_PRINTER = ESC + b"@"  # ESC @
LF = b"\x0a"
PARTIAL_CUT = GS + b"V\x01"  # GS V 1
ALIGN_LEFT = ESC + b"a\x00"
ALIGN_CENTER = ESC + b"a\x01"
ALIGN_RIGHT = ESC + b"a\x02"
BOLD_ON = ESC + b"E\x01"
BOLD_OFF = ESC + b"E\x00"


class PrinterKind(str, Enum):
    """Where the receipt output goes."""

    FILE = "file"
    NETWORK = "network"
    USB = "usb"


@dataclass
class PrinterConfig:
    """Where to send the receipt."""

    kind: PrinterKind = PrinterKind.FILE
    host: str = ""  # for network: host:port
    port: int = 9100
    vendor_id: int = 0x04B8  # Epson default
    product_id: int = 0x0202
    dst_path: str = "./receipts"


def list_supported_vendors() -> list[dict]:
    """Common thermal-printer vendor/product IDs."""
    return [
        {"vendor": "Epson", "vid": 0x04B8, "pid": 0x0202, "model": "TM-T20"},
        {"vendor": "Star Micronics", "vid": 0x0519, "pid": 0x0001, "model": "TSP143III"},
        {"vendor": "Citizen", "vid": 0x1D90, "pid": 0x2068, "model": "CT-S310A"},
        {"vendor": "Brother", "vid": 0x04F9, "pid": 0x2061, "model": "QL-820NWB"},
    ]


def _line(s: str, width: int = 32) -> str:
    """Wrap / pad a line to printer width (default 32 chars: 58mm)."""
    if len(s) >= width:
        return s[:width]
    return s + " " * (width - len(s))


def format_receipt_text(
    *,
    business_name: str,
    sale_id: int,
    product_name: str,
    qty: float,
    unit_price_gs: int,
    total_gs: int,
    cashier: str = "",
    date: datetime | None = None,
    width: int = 32,
) -> str:
    """Build the human-readable receipt body."""
    if date is None:
        date = datetime.now(timezone.utc)
    lines = [
        business_name,
        "--------------------------------",
        f"Recibo #{sale_id}",
        date.strftime("%Y-%m-%d %H:%M"),
        "--------------------------------",
        f"{product_name}",
        f"  {qty:>4.1f} x {unit_price_gs:>9,d} Gs.",
        "--------------------------------",
        f"TOTAL:      {total_gs:>9,d} Gs.",
        "--------------------------------",
    ]
    if cashier:
        lines.append(f"Cajero: {cashier}")
    lines.append("")
    lines.append("¡Gracias por su compra!")
    return "\n".join(lines)


def format_receipt_escpos(
    *,
    business_name: str,
    sale_id: int,
    product_name: str,
    qty: float,
    unit_price_gs: int,
    total_gs: int,
    cashier: str = "",
    date: datetime | None = None,
    width: int = 32,
) -> bytes:
    """Build the ESC/POS byte payload (init + body + cut)."""
    body = format_receipt_text(
        business_name=business_name,
        sale_id=sale_id,
        product_name=product_name,
        qty=qty,
        unit_price_gs=unit_price_gs,
        total_gs=total_gs,
        cashier=cashier,
        date=date,
        width=width,
    )
    payload = INIT_PRINTER
    payload += ALIGN_CENTER + BOLD_ON + business_name.encode("utf-8") + LF + BOLD_OFF + ALIGN_LEFT
    payload += body.encode("utf-8") + LF
    payload += LF
    payload += PARTIAL_CUT
    return payload


def format_label(
    *,
    name: str,
    price_gs: int,
    sku: str | None = None,
    date: str | None = None,
    width: int = 24,
) -> str:
    """Shelf label: name + price + sku/date optional."""
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        name[:width],
        "─" * width,
        f"Gs. {price_gs:>6,d}".rjust(width),
    ]
    if sku:
        lines.append(f"SKU: {sku}"[:width])
    lines.append(date.rjust(width))
    return "\n".join(lines)


def send_to_printer(
    payload: bytes,
    config: PrinterConfig,
) -> dict:
    """Send the payload to the configured printer.

    Returns a dict describing what happened.
    """
    if config.kind == PrinterKind.FILE:
        out_dir = Path(config.dst_path)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time() * 1000)
        out_file = out_dir / f"receipt-{ts}.bin"
        out_file.write_bytes(payload)
        return {"ok": True, "kind": "file", "path": str(out_file), "size": len(payload)}

    if config.kind == PrinterKind.NETWORK:
        with socket.create_connection((config.host, config.port), timeout=3.0) as sock:
            sock.sendall(payload)
        return {"ok": True, "kind": "network", "host": config.host, "port": config.port}

    if config.kind == PrinterKind.USB:
        # Real USB write requires pyusb or system spooler integration.
        # We do not depend on those libraries; advertise clearly so the
        # operator can plug one in.
        return {
            "ok": False,
            "kind": "usb",
            "error": "USB backend not implemented; use file or network or "
            "integrate pyusb at this seam.",
        }

    return {"ok": False, "kind": "?", "error": f"unknown kind {config.kind}"}


def config_from_env() -> PrinterConfig:
    """Build a PrinterConfig from environment variables.

    AIW_PRINTER_KIND = file|network|usb
    AIW_PRINTER_HOST = IP address (network)
    AIW_PRINTER_PORT = int (default 9100)
    AIW_PRINTER_VID  = hex int (USB)
    AIW_PRINTER_PID  = hex int (USB)
    AIW_PRINTER_DST  = file destination (file)
    """
    kind_raw = os.environ.get("AIW_PRINTER_KIND", "file").lower()
    kind = PrinterKind(kind_raw) if kind_raw in {e.value for e in PrinterKind} else PrinterKind.FILE
    return PrinterConfig(
        kind=kind,
        host=os.environ.get("AIW_PRINTER_HOST", ""),
        port=int(os.environ.get("AIW_PRINTER_PORT", "9100")),
        vendor_id=int(os.environ.get("AIW_PRINTER_VID", "0x04b8"), 16),
        product_id=int(os.environ.get("AIW_PRINTER_PID", "0x0202"), 16),
        dst_path=os.environ.get("AIW_PRINTER_DST", "./receipts"),
    )


__all__ = [
    "ALIGN_CENTER",
    "ALIGN_LEFT",
    "ALIGN_RIGHT",
    "BOLD_OFF",
    "BOLD_ON",
    "ESC",
    "GS",
    "INIT_PRINTER",
    "LF",
    "PARTIAL_CUT",
    "PrinterConfig",
    "PrinterKind",
    "config_from_env",
    "format_label",
    "format_receipt_escpos",
    "format_receipt_text",
    "list_supported_vendors",
    "send_to_printer",
]
