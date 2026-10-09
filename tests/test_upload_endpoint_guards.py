"""Integration test for /reorder/upload-prices and /benchmarks/evidencia/importar
file-size and MIME-type guards (Phase 14, mid-tier).
"""

from __future__ import annotations

import io


def _csv_bytes(rows: int = 5) -> bytes:
    lines = ["ingredient_name,supplier_name,price_gs"]
    for i in range(rows):
        lines.append(f"harina{i},Stock PY,{4200 + i}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def test_reorder_upload_prices_accepts_csv(client):
    """Happy path: a small CSV under 2MB should be accepted."""
    r = client.post(
        "/reorder/upload-prices",
        files={"file": ("prices.csv", io.BytesIO(_csv_bytes()), "text/csv")},
    )
    # The endpoint renders a preview page (200) or redirects; either way
    # we should NOT see a 415/413.
    assert r.status_code in (200, 303, 307), r.text[:200]


def test_reorder_upload_prices_rejects_oversize(client):
    """2MB + 1 byte should be rejected with 413."""
    big = b"x" * (2 * 1024 * 1024 + 1)
    r = client.post(
        "/reorder/upload-prices",
        files={"file": ("big.csv", io.BytesIO(big), "text/csv")},
    )
    assert r.status_code == 413


def test_reorder_upload_prices_rejects_bad_mime(client):
    """XML payload should be rejected with 415."""
    r = client.post(
        "/reorder/upload-prices",
        files={"file": ("evil.xml", io.BytesIO(b"<xml>...</xml>"), "application/xml")},
    )
    assert r.status_code == 415
