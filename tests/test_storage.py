"""tests/test_storage.py — BACKLOG #37 Supabase Storage for product images.

Covers:
- is_storage_enabled() returns False when env is unset
- is_storage_enabled() returns False when SUPABASE_URL is unreachable
- is_storage_enabled() returns True when env is set + reachable
  (patches urllib.urlopen to simulate 200 OK)
- upload_product_image() validation (content type, size, empty)
- upload_product_image() happy path with mocked supabase admin
- _ensure_bucket() idempotent — handles "already exists"
- /productos/upload-image route: local fallback when storage disabled
- /productos/upload-image route: backend="supabase_storage" when enabled
- /productos/upload-image route: falls back to local if supabase rejects

Tests that hit the real Supabase project are NOT here — that's a
prod-only check; the helpers below mock the network.
"""
from __future__ import annotations

import io
import urllib.error
from unittest.mock import MagicMock, patch

import pytest


PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n"  # PNG magic
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x03\x00\x05\xfe\x02\xfe\xa3\x9b\x0f\xe0"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


# --- is_storage_enabled ---


def test_is_storage_enabled_returns_false_when_env_unset(monkeypatch):
    """Without SUPABASE_URL + SUPABASE_SECRET_KEY, storage is disabled."""
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    from app.rms.storage import is_storage_enabled

    assert is_storage_enabled() is False


def test_is_storage_enabled_returns_false_when_only_url_set(monkeypatch):
    """Need both URL + key — URL alone is insufficient."""
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    from app.rms.storage import is_storage_enabled

    assert is_storage_enabled() is False


def test_is_storage_enabled_returns_false_on_dns_error(monkeypatch):
    """DNS NXDOMAIN → False (matches /healthz/deps behavior)."""
    monkeypatch.setenv("SUPABASE_URL", "https://nonexistent.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "fake-key-for-test")
    from app.rms.storage import is_storage_enabled

    with patch("urllib.request.urlopen") as fake_u:
        fake_u.side_effect = urllib.error.URLError(
            "Name or service not known"
        )
        assert is_storage_enabled() is False


def test_is_storage_enabled_returns_false_on_http_404(monkeypatch):
    """Project deleted (auth health 404) → False."""
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "fake-key-for-test")
    from app.rms.storage import is_storage_enabled

    with patch("urllib.request.urlopen") as fake_u:
        fake_u.return_value.__enter__.return_value.status = 404
        assert is_storage_enabled() is False


def test_is_storage_enabled_returns_true_when_reachable(monkeypatch):
    """Auth health 200 → True."""
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "fake-key-for-test")
    from app.rms.storage import is_storage_enabled

    with patch("urllib.request.urlopen") as fake_u:
        fake_u.return_value.__enter__.return_value.status = 200
        assert is_storage_enabled() is True


def test_is_storage_enabled_accepts_legacy_service_role_key_alias(
    monkeypatch,
):
    """SUPABASE_SERVICE_ROLE_KEY is also accepted (legacy alias)."""
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake-key")
    from app.rms.storage import is_storage_enabled

    with patch("urllib.request.urlopen") as fake_u:
        fake_u.return_value.__enter__.return_value.status = 200
        assert is_storage_enabled() is True


# --- upload_product_image validation ---


def test_upload_rejects_bad_content_type(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "fake")
    from app.rms.storage import upload_product_image

    with patch("app.rms.storage.is_storage_enabled", return_value=True):
        with pytest.raises(ValueError, match="unsupported_content_type"):
            upload_product_image(b"x", "application/zip", "test.zip")


def test_upload_rejects_empty(monkeypatch):
    from app.rms.storage import upload_product_image

    with patch("app.rms.storage.is_storage_enabled", return_value=True):
        with pytest.raises(ValueError, match="empty_content"):
            upload_product_image(b"", "image/png", "x.png")


def test_upload_rejects_oversize(monkeypatch):
    from app.rms.storage import upload_product_image

    too_big = b"\x89PNG" + b"a" * (5 * 1024 * 1024)
    with patch("app.rms.storage.is_storage_enabled", return_value=True):
        with pytest.raises(ValueError, match="too_large"):
            upload_product_image(too_big, "image/png", "big.png")


# --- upload_product_image happy path ---


def test_upload_happy_path_returns_supabase_url(monkeypatch):
    """When supabase admin returns a public URL, we surface it."""
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "fake")

    mock_storage = MagicMock()
    mock_storage.get_public_url.return_value = (
        "https://x.supabase.co/storage/v1/object/public/product-images/"
        "abc12345-img.png"
    )

    mock_client = MagicMock()
    mock_client.storage.from_.return_value = mock_storage
    # create_bucket succeeds (no exception).
    mock_client.storage.create_bucket.return_value = {"name": "product-images"}

    fake_storage_module = MagicMock()
    fake_storage_module.get_supabase_admin.return_value = mock_client

    with patch.dict("sys.modules", {
        "app.auth_supabase": fake_storage_module,
    }):
        from app.rms.storage import upload_product_image

        result = upload_product_image(PNG_1X1, "image/png", "img.png")
    assert result["backend"] == "supabase_storage"
    assert result["url"].startswith(
        "https://x.supabase.co/storage/v1/object/public/product-images/"
    )
    assert result["filename"].endswith(".png")
    assert int(result["size"]) == len(PNG_1X1)
    # create_bucket was called
    mock_client.storage.create_bucket.assert_called_once()
    # upload was called on the bucket object
    mock_storage.upload.assert_called_once()
    # Public URL retrieved
    mock_storage.get_public_url.assert_called_once()


def test_upload_idempotent_when_bucket_exists(monkeypatch):
    """_ensure_bucket swallows 'Bucket already exists' and returns."""
    mock_client = MagicMock()
    mock_client.storage.create_bucket.side_effect = Exception(
        "Bucket already exists"
    )
    fake_storage_module = MagicMock()
    fake_storage_module.get_supabase_admin.return_value = mock_client
    with patch.dict("sys.modules", {
        "app.auth_supabase": fake_storage_module,
    }):
        from app.rms.storage import _ensure_bucket, PRODUCT_IMAGE_BUCKET

        # Should not raise.
        _ensure_bucket(PRODUCT_IMAGE_BUCKET)


def test_upload_propagates_other_bucket_errors(monkeypatch):
    """Network / permission errors must surface (not silently swallowed)."""
    mock_client = MagicMock()
    mock_client.storage.create_bucket.side_effect = Exception(
        "Network timeout: ECONNREFUSED"
    )
    fake_storage_module = MagicMock()
    fake_storage_module.get_supabase_admin.return_value = mock_client
    with patch.dict("sys.modules", {
        "app.auth_supabase": fake_storage_module,
    }):
        from app.rms.storage import _ensure_bucket

        with pytest.raises(Exception, match="Network timeout"):
            _ensure_bucket("product-images")


def test_upload_filename_collision_resistant(monkeypatch):
    """Filename incorporates content hash + safe-original-name."""
    mock_storage = MagicMock()
    mock_storage.get_public_url.return_value = (
        "https://x.supabase.co/storage/v1/object/public/product-images/x.png"
    )
    mock_client = MagicMock()
    mock_client.storage.from_.return_value = mock_storage
    fake_storage_module = MagicMock()
    fake_storage_module.get_supabase_admin.return_value = mock_client

    with patch.dict("sys.modules", {
        "app.auth_supabase": fake_storage_module,
    }):
        from app.rms.storage import upload_product_image

        result = upload_product_image(PNG_1X1, "image/png", "m!xéd_näme.png")
    # Filename should be: <8-char-hash>-mxd_nme.png (alphanum + -_)
    fn = result["filename"]
    assert fn.endswith(".png")
    # Hash prefix + dash + sanitized name + ext
    assert "-" in fn
    # No special chars from the original
    assert "!" not in fn
    assert " " not in fn


# --- /productos/upload-image route integration ---


def _post_upload(client, png_bytes, content_type="image/png", filename="t.png"):
    return client.post(
        "/productos/upload-image",
        files={"file": (filename, png_bytes, content_type)},
    )


def test_upload_route_uses_local_when_storage_disabled(client, monkeypatch):
    """Default path: storage disabled → local fallback works."""
    from app.rms.storage import is_storage_enabled as real

    monkeypatch.setattr(
        "app.rms.storage.is_storage_enabled", lambda: False
    )
    # Sanity: confirm the real helper is False too in this env
    assert real() is False
    r = _post_upload(client, PNG_1X1)
    assert r.status_code == 200
    body = r.json()
    assert body["url"].startswith("/static/uploads/")
    assert body["backend"] == "local"


def test_upload_route_uses_supabase_when_enabled(client, monkeypatch):
    """When is_storage_enabled=True + supabase returns URL, route returns it."""
    monkeypatch.setattr(
        "app.rms.storage.is_storage_enabled", lambda: True
    )
    monkeypatch.setattr(
        "app.rms.storage.upload_product_image",
        lambda content, ct, name: {
            "url": "https://x.supabase.co/storage/v1/object/public/product-images/abc.png",
            "filename": "abc.png",
            "size": str(len(content)),
            "backend": "supabase_storage",
        },
    )
    r = _post_upload(client, PNG_1X1)
    assert r.status_code == 200
    body = r.json()
    assert body["backend"] == "supabase_storage"
    assert "supabase.co" in body["url"]


def test_upload_route_falls_back_to_local_when_supabase_fails(
    client, monkeypatch,
):
    """Supabase raises mid-upload → route falls back to local silently.

    The user gets a working upload; the operator sees the supabase
    failure separately via /healthz/summary.
    """
    monkeypatch.setattr(
        "app.rms.storage.is_storage_enabled", lambda: True
    )

    def _boom(content, ct, name):
        raise RuntimeError("Network unreachable")

    monkeypatch.setattr(
        "app.rms.storage.upload_product_image", _boom
    )
    r = _post_upload(client, PNG_1X1)
    assert r.status_code == 200
    body = r.json()
    assert body["backend"] == "local"
    assert body["url"].startswith("/static/uploads/")


def test_upload_route_415_on_bad_type(client):
    """Validation still happens at the route even when storage is enabled."""
    r = client.post(
        "/productos/upload-image",
        files={"file": ("x.zip", b"PK", "application/zip")},
    )
    assert r.status_code == 415


def test_upload_route_400_on_empty(client):
    r = client.post(
        "/productos/upload-image",
        files={"file": ("x.png", b"", "image/png")},
    )
    assert r.status_code == 400