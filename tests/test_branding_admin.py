"""tests/test_branding_admin.py — verify /admin/branding UI works.

Tests the operator branding page: file upload endpoint + page rendering.
The router has prefix="/api", so all paths below include /api/.
"""

from __future__ import annotations

import io


def test_admin_branding_page_renders(client):
    """GET /api/admin/branding returns 200 and renders the editor."""
    resp = client.get("/api/admin/branding")
    assert resp.status_code == 200, resp.text[:500]
    body = resp.text
    # Page should have all key UI elements
    assert "branding-form" in body, "Missing the branding form"
    assert "logo-file" in body, "Missing logo file input"
    assert "favicon-file" in body, "Missing favicon file input"
    assert "hero-file" in body, "Missing hero file input"
    assert "accent_color" in body, "Missing accent color input"
    assert "business_type" in body, "Missing business type select"
    assert "preview-box" in body, "Missing live preview box"


def test_admin_branding_shows_current_settings(client):
    """Page renders with current branding values from settings."""
    resp = client.get("/api/admin/branding")
    assert resp.status_code == 200
    body = resp.text
    # Default business_name is "Sazón" (post-rebrand)
    assert "Sazón" in body
    # Default business_type select should have a default option selected
    assert '<option value="restaurant"' in body


def test_api_settings_branding_get(client):
    """GET /api/settings/branding returns the branding dict."""
    resp = client.get("/api/settings/branding")
    assert resp.status_code == 200
    body = resp.json()
    assert "business_name" in body
    assert "tagline" in body
    assert "accent_color" in body
    assert "business_type" in body
    assert body["business_name"] == "Sazón"  # default


def test_api_settings_branding_post_updates(client):
    """POST /api/settings/branding partial update."""
    resp = client.post(
        "/api/settings/branding",
        json={
            "business_name": "Test Panadería",
            "accent_color": "#FF6B35",
            "business_type": "panaderia",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["business_name"] == "Test Panadería"
    assert body["accent_color"] == "#FF6B35"
    assert body["business_type"] == "panaderia"
    # Verify it was persisted
    resp2 = client.get("/api/settings/branding")
    assert resp2.json()["business_name"] == "Test Panadería"


def test_upload_logo_endpoint(client):
    """POST /api/admin/branding/upload accepts a small PNG file as logo."""
    # Minimal 1x1 PNG (89 bytes)
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02"
        b"\xfeA\x9c\xfa\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    resp = client.post(
        "/api/admin/branding/upload",
        data={"kind": "logo"},
        files={"file": ("logo.png", io.BytesIO(png_bytes), "image/png")},
    )
    assert resp.status_code == 200, resp.text[:500]
    body = resp.json()
    assert body["kind"] == "logo"
    assert body["filename"].startswith("logo-")
    assert body["filename"].endswith(".png")
    assert body["url"].startswith("/static/branding/")
    assert body["size_kb"] > 0


def test_upload_favicon_endpoint(client):
    """POST /api/admin/branding/upload accepts a small ICO."""
    # Minimal ICO header (about 22 bytes) — endpoint must validate by extension
    ico_bytes = (
        b"\x00\x00\x01\x00\x01\x00\x10\x10\x00\x00\x01\x00\x18\x00"
        b"\x68\x03\x00\x00\x16\x00\x00\x00"
    )
    resp = client.post(
        "/api/admin/branding/upload",
        data={"kind": "favicon"},
        files={"file": ("favicon.ico", io.BytesIO(ico_bytes), "image/x-icon")},
    )
    assert resp.status_code == 200, resp.text[:500]
    body = resp.json()
    assert body["kind"] == "favicon"
    assert body["filename"].startswith("favicon-")


def test_upload_rejects_wrong_extension(client):
    """Wrong file extension is rejected with 400."""
    txt_bytes = b"hello world"
    resp = client.post(
        "/api/admin/branding/upload",
        data={"kind": "logo"},
        files={"file": ("logo.txt", io.BytesIO(txt_bytes), "text/plain")},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert "not allowed" in body["detail"].lower()


def test_upload_rejects_oversized(client):
    """File too large is rejected with 400."""
    # 3MB file for a logo (max is 2MB)
    big = b"x" * (3 * 1024 * 1024)
    resp = client.post(
        "/api/admin/branding/upload",
        data={"kind": "logo"},
        files={"file": ("logo.png", io.BytesIO(big), "image/png")},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert "too large" in body["detail"].lower()


def test_upload_rejects_unknown_kind(client):
    """Unknown asset kind is rejected."""
    png_bytes = b"\x89PNG\r\n\x1a\n"
    resp = client.post(
        "/api/admin/branding/upload",
        data={"kind": "watermark"},
        files={"file": ("watermark.png", io.BytesIO(png_bytes), "image/png")},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert "kind must be" in body["detail"].lower()


def test_branding_settings_visible_in_settings(client):
    """branding.* settings are listed in /settings (operator catalog)."""
    resp = client.get("/settings")
    assert resp.status_code == 200
    body = resp.text
    # Should mention the new fields
    assert "logo_filename" in body or "logo" in body.lower()
    assert "favicon" in body.lower() or "favicon_filename" in body