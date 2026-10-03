"""app/rms/storage.py — Supabase Storage wrapper for product images.

BACKLOG #37 (2026-10-02): migrate product image storage from local
filesystem (`app/static/uploads/`) to Supabase Storage so images
survive container redeploys and are CDN-cached.

Design:
- `is_storage_enabled()` returns True only when Supabase is reachable.
  In dev / when SUPABASE_URL is unset / when Supabase DNS fails, this
  returns False and callers fall back to local filesystem storage.
- `upload_image(content_bytes, filename, content_type)` uploads to the
  configured bucket. Returns the public URL.
- The bucket is created on first upload (idempotent — Supabase raises
  a 400 if it exists, which we catch and ignore).
- File naming: `product-images/<date>-<hex>.<ext>` to keep collisions
  near-zero and lookup easy.

Operator pre-req: the configured `SUPABASE_URL` env var must point
to a live Supabase project. As of 2026-10-02, prod shows
`url_host=aiwhisperers.supabase.co` returns `DNSError` — the Supabase
project appears to have been deleted/renamed. Until that's fixed,
`is_storage_enabled()` returns False and the existing local-storage
upload path keeps working (this module is fully backward-compatible).
"""
from __future__ import annotations

import hashlib
import logging
import os
import urllib.error
from typing import TYPE_CHECKING
import urllib.request
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from supabase import Client

PRODUCT_IMAGE_BUCKET: Final[str] = "product-images"
ALLOWED_CONTENT_TYPES: Final[set[str]] = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
}
EXT_BY_CONTENT_TYPE: Final[dict[str, str]] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_BYTES: Final[int] = 5 * 1024 * 1024  # 5 MB


def is_storage_enabled() -> bool:
    """True iff Supabase env is fully configured AND the host is reachable.

    We check reachability via a HEAD on the auth health endpoint with
    a 1.5s timeout — fast, no auth required, fails closed if DNS /
    network / 405 / SSL are broken. This prevents the upload route
    from queueing uploads against a dead Supabase project.
    """
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SECRET_KEY", "") or os.environ.get(
        "SUPABASE_SERVICE_ROLE_KEY", ""
    )
    if not (url and key):
        return False
    try:
        # Reuse the same health probe shape as healthz/deps.
        from urllib.parse import urlparse

        netloc = urlparse(url).netloc
        health = f"https://{netloc}/auth/v1/health"
        req = urllib.request.Request(health, method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        logger.debug("is_storage_enabled: supabase unreachable: %s", exc)
        return False


def _supabase_admin() -> "Client":
    """Lazy-import the service-role client (mirrors auth_supabase.py)."""
    from app.auth_supabase import get_supabase_admin

    return get_supabase_admin()


def _ensure_bucket(bucket: str) -> None:
    """Idempotently create the bucket if it doesn't exist.

    Supabase raises a 400 with "Bucket already exists" on retry — we
    treat that as success. Any other exception bubbles up so the route
    can return a 503 to the client.
    """
    client = _supabase_admin()
    try:
        client.storage.create_bucket(
            bucket,
            options={"public": True},
        )
    except Exception as exc:
        msg = str(exc).lower()
        if "already exists" in msg or "duplicate" in msg:
            return
        # Re-raise so the route can surface a real error.
        raise


def upload_product_image(
    content_bytes: bytes, content_type: str, original_filename: str = ""
) -> dict[str, str]:
    """Upload to Supabase Storage. Returns {url, filename, size, backend}.

    Raises HTTPException-shaped errors via the caller's FastAPI
    dependency — we raise plain exceptions here and let the route
    translate them (HTTPException lives in FastAPI; storage.py
    shouldn't depend on it).
    """
    if not ALLOWED_CONTENT_TYPES.__contains__(content_type):
        raise ValueError(
            f"unsupported_content_type:{content_type}"
        )
    if not content_bytes:
        raise ValueError("empty_content")
    if len(content_bytes) > MAX_BYTES:
        raise ValueError(
            f"too_large:{len(content_bytes) // 1024}KB > {MAX_BYTES // 1024}KB"
        )

    ext = EXT_BY_CONTENT_TYPE[content_type]
    # Use a hash prefix of the content + original filename + a short
    # random token — keeps the URL collision-resistant without exposing
    # raw filenames to the public CDN.
    body_hash = hashlib.sha256(content_bytes).hexdigest()[:8]
    safe_name = "".join(
        c for c in Path(original_filename).stem if c.isalnum() or c in "-_"
    )[:32] or "img"
    filename = f"{body_hash}-{safe_name}{ext}"
    object_path = filename  # bucket root is fine; we don't nest

    _ensure_bucket(PRODUCT_IMAGE_BUCKET)
    client = _supabase_admin()
    storage = client.storage.from_(PRODUCT_IMAGE_BUCKET)
    # supabase-py: upload(path, file, options={...})
    storage.upload(
        object_path,
        content_bytes,
        file_options={"content-type": content_type, "upsert": "true"},
    )
    public_url = storage.get_public_url(object_path)
    return {
        "url": public_url,
        "filename": filename,
        "size": str(len(content_bytes)),
        "backend": "supabase_storage",
    }


__all__ = [
    "ALLOWED_CONTENT_TYPES",
    "EXT_BY_CONTENT_TYPE",
    "MAX_BYTES",
    "PRODUCT_IMAGE_BUCKET",
    "is_storage_enabled",
    "upload_product_image",
]
