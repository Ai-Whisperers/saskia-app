"""tests/test_held_sales.py — service tests for held_sale (B-7).

Ports the Hao0321/pos-pro "hold" pattern (MIT, CartPanel.jsx 掛單).
Tests exercise the full happy path + cap eviction + JSON parse + cap.

Covers:
    - hold_cart inserts an 'active' row with serialized cart_json
    - list_active_held returns active rows, oldest first
    - resume_held returns the cart payload + marks status='resumed'
    - discard_held marks status='discarded'
    - get_held returns None for missing id
    - resume_held on a discarded/resumed row raises KeyError
    - _evict_oldest_if_at_capacity evicts FIFO when cap is hit
    - hold_cart validates input shape (must be dict with 'items')
"""

from __future__ import annotations

import pytest

from app.rms.held_sales import (
    discard_held,
    get_held,
    hold_cart,
    list_active_held,
    resume_held,
)

# Uses the project-wide `session_factory` + `app_engine` fixtures
# defined in tests/conftest.py — every test runs against a tmp DB.


def _cart(items=None, **kw):
    return {"items": items or [{"product_id": 1, "qty": 2.0}], **kw}


def test_hold_inserts_active_row(session_factory):
    sf = session_factory
    with sf() as s:
        held = hold_cart(s, _cart(), held_by="alice", label="cliente Juan")
    assert held.id >= 1
    assert held.status == "active"
    assert held.held_by == "alice"
    assert held.label == "cliente Juan"


def test_hold_blank_label_normalized(session_factory):
    sf = session_factory
    with sf() as s:
        held = hold_cart(s, _cart(), held_by="alice", label="   ")
    assert held.label == "sin etiqueta"


def test_hold_long_label_truncated(session_factory):
    sf = session_factory
    long_label = "x" * 200
    with sf() as s:
        held = hold_cart(s, _cart(), held_by="alice", label=long_label)
    assert len(held.label) == 120


def test_hold_requires_dict(session_factory):
    sf = session_factory
    with sf() as s, pytest.raises(ValueError, match="dict"):
        hold_cart(s, ["not", "a", "dict"], held_by="alice", label="x")


def test_hold_requires_items_key(session_factory):
    sf = session_factory
    with sf() as s, pytest.raises(ValueError, match="items"):
        hold_cart(s, {}, held_by="alice", label="x")


def test_list_active_returns_oldest_first(session_factory):
    sf = session_factory
    with sf() as s:
        h1 = hold_cart(s, _cart(), held_by="a", label="first")
        h2 = hold_cart(s, _cart(), held_by="b", label="second")
        h3 = hold_cart(s, _cart(), held_by="c", label="third")
    with sf() as s:
        active = list_active_held(s)
        assert [r.id for r in active] == [h1.id, h2.id, h3.id]
        assert [r.label for r in active] == ["first", "second", "third"]


def test_resume_returns_cart_and_marks_resumed(session_factory):
    sf = session_factory
    with sf() as s:
        cart = _cart(items=[{"product_id": 42, "qty": 3.0}],
                     customer_id=7, channel="losso_especial")
        held = hold_cart(s, cart, held_by="alice", label="k")
    with sf() as s:
        resumed = resume_held(s, held.id)
    assert resumed["items"] == [{"product_id": 42, "qty": 3.0}]
    assert resumed["customer_id"] == 7
    assert resumed["channel"] == "losso_especial"
    # Now resume again → KeyError (status no longer 'active')
    with sf() as s, pytest.raises(KeyError):
        resume_held(s, held.id)


def test_resume_missing_raises(session_factory):
    sf = session_factory
    with sf() as s, pytest.raises(KeyError):
        resume_held(s, 99999)


def test_discard_marks_status(session_factory):
    sf = session_factory
    with sf() as s:
        held = hold_cart(s, _cart(), held_by="a", label="x")
    with sf() as s:
        assert discard_held(s, held.id) is True
        assert discard_held(s, held.id) is False  # already discarded
    with sf() as s:
        # Resumed status = 'resumed' would also return False here
        # Verify via raw status read
        row = get_held(s, held.id)
        assert row.status == "discarded"


def test_discard_missing_returns_false(session_factory):
    sf = session_factory
    with sf() as s:
        assert discard_held(s, 99999) is False


def test_get_held_missing_returns_none(session_factory):
    sf = session_factory
    with sf() as s:
        assert get_held(s, 99999) is None


def test_parse_cart_returns_dict(session_factory):
    sf = session_factory
    with sf() as s:
        cart = _cart(items=[{"product_id": 1}, {"product_id": 2}])
        held = hold_cart(s, cart, held_by="a", label="x")
    with sf() as s:
        row = get_held(s, held.id)
        parsed = row.parse_cart()
    assert len(parsed["items"]) == 2


def test_cap_evicts_oldest(monkeypatch, session_factory):
    """When SAZON_MAX_HELD_SALES is hit, oldest active is evicted FIFO."""
    monkeypatch.setenv("SAZON_MAX_HELD_SALES", "3")
    # Re-import to pick up env var (config module reads at import time)
    import importlib

    import app.rms.config as cfg
    importlib.reload(cfg)
    import app.rms.held_sales as hs
    importlib.reload(hs)
    hold_cart = hs.hold_cart
    list_active_held = hs.list_active_held

    sf = session_factory
    with sf() as s:
        h1 = hold_cart(s, _cart(), held_by="a", label="first")
        _h2 = hold_cart(s, _cart(), held_by="a", label="second")
        _h3 = hold_cart(s, _cart(), held_by="a", label="third")
        _h4 = hold_cart(s, _cart(), held_by="a", label="fourth (evicts first)")
    with sf() as s:
        rows = list_active_held(s)
        labels = [r.label for r in rows]
    # h1 should be evicted; h2, h3, h4 remain
    assert "first" not in labels
    assert labels == ["second", "third", "fourth (evicts first)"]
    # Verify h1 is now status=auto_evicted
    with sf() as s:
        row = hs.get_held(s, h1.id)
        assert row.status == "auto_evicted"


def test_cap_default_is_50(monkeypatch):
    """SAZON_MAX_HELD_SALES default is 50."""
    monkeypatch.delenv("SAZON_MAX_HELD_SALES", raising=False)
    import importlib

    import app.rms.config as cfg
    importlib.reload(cfg)
    assert cfg.SAZON_MAX_HELD_SALES == 50


def test_held_sale_round_trip_preserves_unicode(session_factory):
    """Unicode in labels and cart must survive json dump/load."""
    sf = session_factory
    label = "Cliente Juan — ñoño + 漢字"
    cart = _cart(items=[{"product_id": 1, "note": "Exquisito ☕"}])
    with sf() as s:
        held = hold_cart(s, cart, held_by="maria", label=label)
    with sf() as s:
        row = get_held(s, held.id)
        assert row.label == label
        assert row.parse_cart()["items"][0]["note"] == "Exquisito ☕"
