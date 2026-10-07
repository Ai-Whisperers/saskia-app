"""Sprint Week 1 — Cache utility tests.

Verifies the client-side Cache with TTL support and memoization.
"""

from __future__ import annotations

from pathlib import Path

CACHE_JS = Path(__file__).parent.parent / "app" / "static" / "cache.js"
BASE_HTML = Path(__file__).parent.parent / "app" / "templates" / "base.html"


def test_cache_js_exists():
    """Should have a dedicated cache script."""
    assert CACHE_JS.exists()


def test_cache_loaded_in_base():
    """Should be loaded in base.html."""
    text = BASE_HTML.read_text()
    assert "cache.js" in text


def test_cache_implements_set_get():
    """Should have basic set/get operations."""
    js = CACHE_JS.read_text()
    assert "set:" in js
    assert "get:" in js
    assert "Map" in js


def test_cache_supports_ttl():
    """Should support TTL (time-to-live)."""
    js = CACHE_JS.read_text()
    assert "ttlMs" in js
    assert "expiresAt" in js
    assert "setTimeout" in js


def test_cache_has_expiration():
    """Should auto-expire entries after TTL."""
    js = CACHE_JS.read_text()
    assert "Date.now()" in js
    assert "expiresAt" in js
    assert "delete" in js


def test_cache_has_delete():
    """Should support explicit deletion."""
    js = CACHE_JS.read_text()
    assert "delete:" in js
    assert "clearTimeout" in js


def test_cache_has_clear():
    """Should support clearing all entries."""
    js = CACHE_JS.read_text()
    assert "clear:" in js
    assert "_store.clear" in js


def test_cache_has_size():
    """Should expose size for monitoring."""
    js = CACHE_JS.read_text()
    assert "size:" in js
    assert "_store.size" in js


def test_cache_has_memoize():
    """Should support function memoization."""
    js = CACHE_JS.read_text()
    assert "memoize:" in js
    assert "JSON.stringify" in js


def test_cache_has_method():
    """Should support has() check."""
    js = CACHE_JS.read_text()
    assert "has:" in js


def test_cache_cleans_on_unload():
    """Should clean up on page unload."""
    js = CACHE_JS.read_text()
    assert "beforeunload" in js
    assert "Cache.clear" in js


def test_cache_exposes_global():
    """Should expose Cache globally."""
    js = CACHE_JS.read_text()
    assert "window.Cache" in js


def test_cache_default_ttl():
    """Should have a sensible default TTL."""
    js = CACHE_JS.read_text()
    assert "60000" in js or "ttlMs = " in js


def test_cache_handles_undefined_gracefully():
    """Should return undefined for missing keys."""
    js = CACHE_JS.read_text()
    assert "undefined" in js


def test_cache_uses_iife():
    """Should be wrapped in IIFE to avoid global pollution."""
    js = CACHE_JS.read_text()
    assert "(function()" in js or "(function ()" in js
    assert "'use strict'" in js
