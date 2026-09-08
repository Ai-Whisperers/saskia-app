"""tests/test_pwa.py — verify app/rms/pwa.py (E11).

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E11.

Covers:
- PWA_MANIFEST has required fields (name, icons, start_url)
- is_mobile detects common UAs
- service_worker_source: starts with cache declaration
- OFFLINE_HTML is well-formed
- pwa_meta_tags returns 6 tags
- register_service_worker_script returns inline JS
- OFFLINE_CACHE_ROUTES has /, /productos, /inventario, /recetas
"""
from __future__ import annotations

from app.rms.pwa import (
    OFFLINE_CACHE_ROUTES,
    OFFLINE_HTML,
    PWA_MANIFEST,
    SW_VERSION,
    is_mobile,
    pwa_meta_tags,
    register_service_worker_script,
    service_worker_source,
)


def test_manifest_required_fields():
    assert "name" in PWA_MANIFEST
    assert "start_url" in PWA_MANIFEST
    assert "icons" in PWA_MANIFEST
    assert len(PWA_MANIFEST["icons"]) >= 2


def test_manifest_includes_business_category():
    assert "business" in PWA_MANIFEST.get("categories", [])


def test_is_mobile_detects_iphone():
    assert is_mobile("Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)")
    assert is_mobile("iPhone")


def test_is_mobile_detects_android():
    assert is_mobile("Mozilla/5.0 (Linux; Android 11)")
    assert is_mobile("Android")


def test_is_mobile_detects_ipad():
    assert is_mobile("Mozilla/5.0 (iPad; CPU OS 13_0)")


def test_is_mobile_desktop_false():
    assert not is_mobile("Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    assert not is_mobile("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")


def test_is_mobile_empty_false():
    assert not is_mobile("")
    assert not is_mobile(None)  # type: ignore


def test_sw_source_has_version():
    src = service_worker_source()
    assert SW_VERSION in src
    assert "CACHE" in src
    assert "install" in src
    assert "fetch" in src


def test_sw_caches_offline_routes():
    src = service_worker_source()
    for route in OFFLINE_CACHE_ROUTES:
        assert route in src


def test_offline_html_well_formed():
    assert "<!DOCTYPE html>" in OFFLINE_HTML
    assert "Sin conexión" in OFFLINE_HTML or "offline" in OFFLINE_HTML.lower()


def test_offline_cache_routes_includes_dashboard():
    """The 4 read-only routes for offline cache."""
    assert "/" in OFFLINE_CACHE_ROUTES
    assert "/productos" in OFFLINE_CACHE_ROUTES
    assert "/inventario" in OFFLINE_CACHE_ROUTES
    assert "/recetas" in OFFLINE_CACHE_ROUTES


def test_pwa_meta_tags_returns_6_tags():
    tags = pwa_meta_tags()
    assert tags.count("<link") + tags.count("<meta") == 6


def test_register_script_includes_service_worker():
    js = register_service_worker_script()
    assert "serviceWorker" in js
    assert "register" in js


def test_sw_version_is_semver():
    """Version should follow the major.minor.patch pattern."""
    parts = SW_VERSION.lstrip("v").split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)
