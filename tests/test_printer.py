"""tests/test_printer.py — verify app/rms/printer.py (E18).

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E18.

Covers:
- ESC/POS payload is non-empty + contains INIT_PRINTER + PARTIAL_CUT
- Body text contains business name, sale id, total
- send_to_printer writes to file (default backend)
- format_label includes name + price
- list_supported_vendors returns 4 entries
- config_from_env reads AIW_PRINTER_* env vars
"""
from __future__ import annotations

import socket
from pathlib import Path

from app.integrations.printer import (
    PrinterConfig,
    PrinterKind,
    config_from_env,
    format_label,
    format_receipt_escpos,
    format_receipt_text,
    list_supported_vendors,
    send_to_printer,
)


def test_format_receipt_text_contains_key_fields():
    text = format_receipt_text(
        business_name="HEREBUS Bakery",
        sale_id=42,
        product_name="Muffin",
        qty=2.0,
        unit_price_gs=2500,
        total_gs=5000,
        cashier="Saskia",
    )
    assert "HEREBUS Bakery" in text
    assert "Recibo #42" in text
    assert "Muffin" in text
    assert "5,000 Gs" in text or "5.000 Gs" in text or "5000 Gs" in text
    assert "Saskia" in text
    assert "Gracias" in text


def test_format_receipt_escpos_starts_with_init_and_ends_with_cut():
    payload = format_receipt_escpos(
        business_name="Test Bakery",
        sale_id=1,
        product_name="Torta",
        qty=1.0,
        unit_price_gs=35000,
        total_gs=35000,
    )
    assert payload[:2] == b"\x1b@"  # INIT_PRINTER (ESC @)
    assert payload[-3:] == b"\x1dV\x01"  # PARTIAL_CUT
    # Body bytes are there too
    assert b"Test Bakery" in payload
    assert b"Torta" in payload
    assert b"35,000 Gs" in payload or b"35.000 Gs" in payload


def test_send_to_printer_writes_file(tmp_path):
    """Default backend (file) writes the bytes to disk."""
    config = PrinterConfig(
        kind=PrinterKind.FILE,
        dst_path=str(tmp_path),
    )
    payload = b"\x1b@hello\x0a\x1dV\x01"
    result = send_to_printer(payload, config)
    assert result["ok"]
    assert result["kind"] == "file"
    assert Path(result["path"]).exists()
    assert Path(result["path"]).read_bytes() == payload


def test_send_to_printer_returns_error_for_unimpl_usb():
    config = PrinterConfig(kind=PrinterKind.USB)
    payload = b"test"
    result = send_to_printer(payload, config)
    assert result["ok"] is False
    assert "USB" in result["error"]


def test_send_to_printer_routes_network(monkeypatch):
    """Network path uses socket.create_connection — verified via fake server."""
    # Tiny TCP echo server
    captured = []
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def handle():
        conn, _ = server.accept()
        data = conn.recv(4096)
        captured.append(data)
        conn.close()
        server.close()

    import threading
    t = threading.Thread(target=handle, daemon=True)
    t.start()

    config = PrinterConfig(
        kind=PrinterKind.NETWORK,
        host="127.0.0.1",
        port=port,
    )
    payload = b"hello-printer"
    result = send_to_printer(payload, config)
    assert result["ok"]
    t.join(timeout=2)
    assert captured == [payload]


def test_format_label_includes_name_price():
    label = format_label(name="Muffin clásico", price_gs=2500, sku="MUF-001")
    assert "Muffin" in label
    assert "2,500" in label
    assert "MUF-001" in label


def test_format_label_truncates_long_names():
    label = format_label(name="A" * 100, price_gs=1000, width=20)
    # First line truncated to width
    first_line = label.split("\n")[0]
    assert len(first_line) == 20


def test_list_supported_vendors_returns_4():
    vendors = list_supported_vendors()
    assert len(vendors) == 4
    assert {v["vendor"] for v in vendors} == {"Epson", "Star Micronics", "Citizen", "Brother"}


def test_config_from_env_defaults_to_file(monkeypatch):
    for k in ("AIW_PRINTER_KIND", "AIW_PRINTER_HOST", "AIW_PRINTER_PORT",
              "AIW_PRINTER_VID", "AIW_PRINTER_PID", "AIW_PRINTER_DST"):
        monkeypatch.delenv(k, raising=False)
    cfg = config_from_env()
    assert cfg.kind == PrinterKind.FILE
    assert cfg.dst_path == "./receipts"
    assert cfg.port == 9100


def test_config_from_env_network(monkeypatch):
    monkeypatch.setenv("AIW_PRINTER_KIND", "network")
    monkeypatch.setenv("AIW_PRINTER_HOST", "10.0.0.5")
    monkeypatch.setenv("AIW_PRINTER_PORT", "9101")
    cfg = config_from_env()
    assert cfg.kind == PrinterKind.NETWORK
    assert cfg.host == "10.0.0.5"
    assert cfg.port == 9101


def test_config_from_env_unknown_kind_falls_back(monkeypatch):
    monkeypatch.setenv("AIW_PRINTER_KIND", "morsecode")
    cfg = config_from_env()
    assert cfg.kind == PrinterKind.FILE  # safe default
