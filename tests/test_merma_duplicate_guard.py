"""PROD-MERMA-2 (Batch E): duplicate-record guard on /merma/registrar.

Prevents accidental double-submit by returning 409 if the same
(ingredient, reason, qty within tolerance) was submitted within the
last 60 seconds. The response carries an X-Saskia-Duplicate-Of header
with the existing event id so the client can surface it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.rms.models import Ingredient


def _post_merma(authed_client, ing_id: int, qty: float = 0.5, reason: str = "vencida"):
    return authed_client.post(
        "/merma/registrar",
        data={
            "ingredient_id": str(ing_id),
            "qty": str(qty),
            "qty_unit": "kg",
            "reason": reason,
            "notes": "dup-guard test",
            "source": "manual",
        },
        follow_redirects=False,
    )


def test_first_submit_succeeds(authed_client, session_factory):
    """Baseline: a fresh merma submit returns 303."""
    with session_factory() as s:
        ing = Ingredient(name="DupGuard Baseline Ing", unit="kg", stock_qty=5.0, min_stock_qty=1.0)
        s.add(ing)
        s.commit()
        ing_id = ing.id
    r = _post_merma(authed_client, ing_id)
    assert r.status_code == 303, f"First submit should redirect (303), got {r.status_code}"


def test_duplicate_within_window_returns_409(authed_client, session_factory):
    """A second identical submit within 60s returns 409 with X-Saskia-Duplicate-Of header."""
    with session_factory() as s:
        ing = Ingredient(name="DupGuard Window Ing", unit="kg", stock_qty=5.0, min_stock_qty=1.0)
        s.add(ing)
        s.commit()
        ing_id = ing.id
    r1 = _post_merma(authed_client, ing_id)
    assert r1.status_code == 303
    r2 = _post_merma(authed_client, ing_id)
    assert r2.status_code == 409, f"Duplicate should be 409, got {r2.status_code}"
    # The header should point at the first event
    dup_of = r2.headers.get("X-Saskia-Duplicate-Of") or r2.headers.get("x-saskia-duplicate-of")
    assert dup_of is not None and dup_of.isdigit(), (
        f"X-Saskia-Duplicate-Of header missing or invalid: {r2.headers}"
    )


def test_duplicate_with_qty_tolerance(authed_client, session_factory):
    """A second submit with qty within 5% is treated as a duplicate."""
    with session_factory() as s:
        ing = Ingredient(name="DupGuard Tol Ing", unit="kg", stock_qty=5.0, min_stock_qty=1.0)
        s.add(ing)
        s.commit()
        ing_id = ing.id
    r1 = _post_merma(authed_client, ing_id, qty=1.0)
    assert r1.status_code == 303
    # 1.04 is within 5% of 1.0 — should be blocked
    r2 = _post_merma(authed_client, ing_id, qty=1.04)
    assert r2.status_code == 409, f"qty within tolerance should be blocked, got {r2.status_code}"


def test_different_qty_not_blocked(authed_client, session_factory):
    """A second submit with qty > 5% different succeeds (legitimate, not a double-click)."""
    with session_factory() as s:
        ing = Ingredient(name="DupGuard DiffQty Ing", unit="kg", stock_qty=5.0, min_stock_qty=1.0)
        s.add(ing)
        s.commit()
        ing_id = ing.id
    r1 = _post_merma(authed_client, ing_id, qty=0.5)
    assert r1.status_code == 303
    # 0.8 is > 5% away from 0.5 — should succeed
    r2 = _post_merma(authed_client, ing_id, qty=0.8)
    assert r2.status_code == 303, f"Different qty should not be blocked, got {r2.status_code}"


def test_different_reason_not_blocked(authed_client, session_factory):
    """A second submit with a different reason is NOT a duplicate."""
    with session_factory() as s:
        ing = Ingredient(name="DupGuard Reason Ing", unit="kg", stock_qty=5.0, min_stock_qty=1.0)
        s.add(ing)
        s.commit()
        ing_id = ing.id
    r1 = _post_merma(authed_client, ing_id, qty=0.5, reason="vencida")
    assert r1.status_code == 303
    r2 = _post_merma(authed_client, ing_id, qty=0.5, reason="quemada")
    assert r2.status_code == 303, f"Different reason should not be blocked, got {r2.status_code}"


def test_duplicate_window_expires(authed_client, session_factory):
    """An identical submit AFTER the 60s window succeeds."""
    from app.rms.models import WasteLog
    with session_factory() as s:
        ing = Ingredient(name="DupGuard Expired Ing", unit="kg", stock_qty=5.0, min_stock_qty=1.0)
        s.add(ing)
        s.commit()
        ing_id = ing.id
    r1 = _post_merma(authed_client, ing_id)
    assert r1.status_code == 303

    # Rewind the recorded_at of the existing event so it's outside the window.
    with session_factory() as s:
        prev = s.query(WasteLog).filter(WasteLog.ingredient_id == ing_id).order_by(WasteLog.recorded_at.desc()).first()
        prev.recorded_at = datetime.now(timezone.utc) - timedelta(seconds=120)
        s.commit()

    r2 = _post_merma(authed_client, ing_id)
    assert r2.status_code == 303, f"Submit after window should succeed, got {r2.status_code}"


def test_409_response_message_in_spanish(authed_client, session_factory):
    """The 409 message is in Spanish and mentions the duplicate id."""
    with session_factory() as s:
        ing = Ingredient(name="DupGuard Msg Ing", unit="kg", stock_qty=5.0, min_stock_qty=1.0)
        s.add(ing)
        s.commit()
        ing_id = ing.id
    _post_merma(authed_client, ing_id)
    r = _post_merma(authed_client, ing_id)
    assert r.status_code == 409
    # body is JSON {"detail": "..."}
    body = r.json()
    assert "Ya registraste" in body["detail"], f"Expected Spanish 'Ya registraste' in detail, got: {body}"
    assert "id=#" in body["detail"], f"Expected id reference, got: {body}"
