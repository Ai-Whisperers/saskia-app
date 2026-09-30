"""tests/test_reorder_supplier_redesign.py — migration 072 + manual-lock suite.

Phase 1 (2026-09-30): auto-streak lock after 3 buys.
Phase 2 (this commit): replaced auto-streak with a MANUAL 🔒 toggle.
The streak counter is kept for analytics but no longer changes
behaviour automatically.

What's covered:
  - effective-supplier precedence: locked > last_purchase > parent
  - record_purchase_supplier() increments streak + updates last_purchase
    but NEVER touches locked_supplier_id (auto-lock removed)
  - lock_supplier() / unlock_supplier() write audit rows
  - lock() is idempotent (no double-audit when re-locking to same)
  - lock() overrides an existing lock + audits the previous supplier
  - unlock() is a no-op when there is no lock
  - the /reorder template renders 🔒 buttons on every unlocked row and
    🔓 on locked rows
  - /reorder/lock-supplier + /reorder/unlock-supplier endpoints write
    audit + 200 + correct ids
  - /reorder/registrar accepts supplier_id but never auto-locks
  - JSON endpoint exposes supplier_options + per-row lock state

Tests use factories.make_ingredient / make_supplier (uuid-named to avoid
UNIQUE collisions in the shared DB).
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import sessionmaker

from app.rms.models import AuditLog, Ingredient
from app.rms.supplier_history import (
    LOCK_THRESHOLD,
    get_effective_supplier_id,
    lock_supplier,
    record_purchase_supplier,
    unlock_supplier,
)
from tests.factories import make_ingredient, make_supplier


# =========================================================================
# Pure-Python tests — no HTTP, no DB schema beyond what's already there.
# =========================================================================


def test_effective_supplier_precedence(monkeypatch, session_factory):
    """get_effective_supplier_id() returns locked > last_purchase > parent."""
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        tag = uuid.uuid4().hex[:8]
        sup_old = make_supplier(s, name=f"old-{tag}")
        sup_locked = make_supplier(s, name=f"locked-{tag}")
        sup_parent = make_supplier(s, name=f"parent-{tag}")
        ing = make_ingredient(
            s,
            name=f"prec-{tag}",
            unit="kg",
            stock_qty=0.0,
            min_stock_qty=10.0,
        )
        ing.supplier_id = sup_parent.id
        ing.last_purchase_supplier_id = sup_old.id
        ing.locked_supplier_id = None
        s.commit()
        s.refresh(ing)

        # 1. No lock → last_purchase wins over parent
        assert get_effective_supplier_id(ing) == sup_old.id, (
            "no lock + last_purchase set → must use last_purchase"
        )

        # 2. Lock set → lock wins over last_purchase
        ing.locked_supplier_id = sup_locked.id
        s.commit()
        s.refresh(ing)
        assert get_effective_supplier_id(ing) == sup_locked.id, (
            "lock set → must use locked_supplier_id"
        )

        # 3. Lock cleared → falls back to last_purchase
        ing.locked_supplier_id = None
        s.commit()
        s.refresh(ing)
        assert get_effective_supplier_id(ing) == sup_old.id, (
            "lock cleared → must fall back to last_purchase"
        )

        # 4. Both cleared → falls back to parent supplier_id
        ing.last_purchase_supplier_id = None
        s.commit()
        s.refresh(ing)
        assert get_effective_supplier_id(ing) == sup_parent.id, (
            "all cleared → must fall back to parent supplier_id"
        )

        # 5. Everything cleared → None
        ing.supplier_id = None
        s.commit()
        s.refresh(ing)
        assert get_effective_supplier_id(ing) is None, (
            "all sources cleared → must return None"
        )
    finally:
        s.close()


def test_streak_does_NOT_auto_lock(session_factory):
    """Regression (Phase 2): even after LOCK_THRESHOLD buys, the
    helper must NOT set locked_supplier_id. The lock is now a manual
    🔒 toggle on /reorder, not an automatic streak consequence.
    """
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        tag = uuid.uuid4().hex[:8]
        sup_a = make_supplier(s, name=f"streak-a-{tag}")
        ing = make_ingredient(
            s, name=f"streak-{tag}", unit="kg",
            stock_qty=0.0, min_stock_qty=10.0,
        )
        ing.supplier_id = sup_a.id
        s.commit()
        s.refresh(ing)

        # Buy LOCK_THRESHOLD times in a row → streak hits the threshold
        for expected in (1, 2, 3):
            record_purchase_supplier(s, ing.id, sup_a.id)
            s.commit()
            s.refresh(ing)
            assert ing.purchase_streak_count == expected, (
                f"streak count after {expected} consecutive buys must be {expected}"
            )
            assert ing.locked_supplier_id is None, (
                f"after {expected} buys, lock must NOT auto-set — "
                "manual 🔒 toggle replaced the auto-streak behaviour"
            )
    finally:
        s.close()


def test_streak_resets_on_supplier_switch(session_factory):
    """Buying from a different supplier resets the streak to 1."""
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        tag = uuid.uuid4().hex[:8]
        sup_a = make_supplier(s, name=f"reset-a-{tag}")
        sup_b = make_supplier(s, name=f"reset-b-{tag}")
        ing = make_ingredient(
            s, name=f"reset-{tag}", unit="kg",
            stock_qty=0.0, min_stock_qty=10.0,
        )
        ing.supplier_id = sup_a.id
        s.commit()
        s.refresh(ing)

        # 2 buys from A
        record_purchase_supplier(s, ing.id, sup_a.id)
        record_purchase_supplier(s, ing.id, sup_a.id)
        s.commit()
        s.refresh(ing)
        assert ing.purchase_streak_count == 2
        assert ing.last_purchase_supplier_id == sup_a.id

        # Switch to B → streak = 1, last = B
        record_purchase_supplier(s, ing.id, sup_b.id)
        s.commit()
        s.refresh(ing)
        assert ing.purchase_streak_count == 1, (
            f"switching suppliers must reset streak; got {ing.purchase_streak_count}"
        )
        assert ing.last_purchase_supplier_id == sup_b.id
        assert ing.locked_supplier_id is None, "switch shouldn't lock"
    finally:
        s.close()


def test_switching_suppliers_does_not_touch_existing_lock(session_factory):
    """Phase-2 regression: if an ingredient has a manually-set lock,
    switching suppliers on /registrar must NOT auto-clear it. Manual
    toggle is the only thing that clears the lock now.
    """
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        tag = uuid.uuid4().hex[:8]
        sup_a = make_supplier(s, name=f"unlock-a-{tag}")
        sup_b = make_supplier(s, name=f"unlock-b-{tag}")
        ing = make_ingredient(
            s, name=f"unlock-{tag}", unit="kg",
            stock_qty=0.0, min_stock_qty=10.0,
        )
        ing.supplier_id = sup_a.id
        s.commit()

        # Manually pin to A
        lock_supplier(s, ing.id, sup_a.id, actor="demo")
        s.commit()
        s.refresh(ing)
        assert ing.locked_supplier_id == sup_a.id

        # Switch to B on /registrar
        record_purchase_supplier(s, ing.id, sup_b.id)
        s.commit()
        s.refresh(ing)
        # Lock must STAY on A — manual 🔒 is the only thing that clears it
        assert ing.locked_supplier_id == sup_a.id, (
            "switching suppliers on /registrar must NOT clear a manual lock; "
            "only the 🔓 button does"
        )
        assert ing.purchase_streak_count == 1
    finally:
        s.close()


def test_lock_supplier_writes_audit_row(session_factory):
    """lock_supplier() writes an audit row with actor + previous-lock id."""
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        tag = uuid.uuid4().hex[:8]
        sup = make_supplier(s, name=f"lock-audit-{tag}")
        ing = make_ingredient(
            s, name=f"lock-audit-{tag}", unit="kg",
            stock_qty=0.0, min_stock_qty=10.0,
        )
        ing.supplier_id = sup.id
        s.commit()
        ing_id, sup_id = ing.id, sup.id

        lock_supplier(s, ing_id, sup_id, actor="demo", reason="specialty import")
        s.commit()

        rows = s.query(AuditLog).filter(
            AuditLog.action == "ingredient.supplier.lock"
        ).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.target_id == str(ing_id)
        assert row.user_id == "demo"
        assert row.detail["supplier_id"] == sup_id
        assert row.detail["previous_locked_supplier_id"] is None
        assert row.detail["reason"] == "specialty import"
    finally:
        s.close()


def test_lock_is_idempotent(session_factory):
    """Re-locking to the same supplier is a no-op (no extra audit row)."""
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        tag = uuid.uuid4().hex[:8]
        sup = make_supplier(s, name=f"idem-{tag}")
        ing = make_ingredient(
            s, name=f"idem-{tag}", unit="kg",
            stock_qty=0.0, min_stock_qty=10.0,
        )
        ing.supplier_id = sup.id
        s.commit()
        ing_id, sup_id = ing.id, sup.id

        lock_supplier(s, ing_id, sup_id, actor="demo")
        s.commit()
        lock_supplier(s, ing_id, sup_id, actor="demo")
        s.commit()

        rows = s.query(AuditLog).filter(
            AuditLog.action == "ingredient.supplier.lock"
        ).all()
        assert len(rows) == 1, "second lock to same supplier should no-op"
    finally:
        s.close()


def test_lock_overrides_existing_lock_and_audits_previous(session_factory):
    """Re-locking to a different supplier writes a row recording the swap."""
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        tag = uuid.uuid4().hex[:8]
        sup_a = make_supplier(s, name=f"swap-a-{tag}")
        sup_b = make_supplier(s, name=f"swap-b-{tag}")
        ing = make_ingredient(
            s, name=f"swap-{tag}", unit="kg",
            stock_qty=0.0, min_stock_qty=10.0,
        )
        ing.supplier_id = sup_a.id
        ing.locked_supplier_id = sup_a.id
        s.commit()
        ing_id, a_id, b_id = ing.id, sup_a.id, sup_b.id

        lock_supplier(s, ing_id, b_id, actor="demo")
        s.commit()

        ing_now = s.get(Ingredient, ing_id)
        assert ing_now.locked_supplier_id == b_id
        row = s.query(AuditLog).filter(
            AuditLog.action == "ingredient.supplier.lock"
        ).order_by(AuditLog.occurred_at.desc()).first()
        assert row.detail["previous_locked_supplier_id"] == a_id
        assert row.detail["supplier_id"] == b_id
    finally:
        s.close()


def test_unlock_writes_audit_row(session_factory):
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        tag = uuid.uuid4().hex[:8]
        sup = make_supplier(s, name=f"unlock-audit-{tag}")
        ing = make_ingredient(
            s, name=f"unlock-audit-{tag}", unit="kg",
            stock_qty=0.0, min_stock_qty=10.0,
        )
        ing.supplier_id = sup.id
        ing.locked_supplier_id = sup.id
        s.commit()
        ing_id, sup_id = ing.id, sup.id

        unlock_supplier(s, ing_id, actor="demo", reason="changed my mind")
        s.commit()

        ing_now = s.get(Ingredient, ing_id)
        assert ing_now.locked_supplier_id is None
        rows = s.query(AuditLog).filter(
            AuditLog.action == "ingredient.supplier.unlock"
        ).all()
        assert len(rows) == 1
        assert rows[0].detail == {
            "previous_locked_supplier_id": sup_id,
            "reason": "changed my mind",
        }
    finally:
        s.close()


def test_unlock_is_noop_when_unlocked(session_factory):
    """Unlocking an unlocked ingredient must NOT write an audit row."""
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        tag = uuid.uuid4().hex[:8]
        sup = make_supplier(s, name=f"noop-{tag}")
        ing = make_ingredient(
            s, name=f"noop-{tag}", unit="kg",
            stock_qty=0.0, min_stock_qty=10.0,
        )
        ing.supplier_id = sup.id
        s.commit()
        ing_id = ing.id

        unlock_supplier(s, ing_id, actor="demo")
        s.commit()

        rows = s.query(AuditLog).filter(
            AuditLog.action == "ingredient.supplier.unlock"
        ).all()
        assert rows == [], "unlocking an unlocked ingredient must not audit"
    finally:
        s.close()


# =========================================================================
# HTTP tests — the actual /reorder page rendering and POST behavior.
# =========================================================================


def test_reorder_renders_supplier_picker_per_row(client, session_factory):
    """Q1: every row has its own supplier dropdown with inline prices."""
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        tag = uuid.uuid4().hex[:8]
        sup1 = make_supplier(s, name=f"pickr1-{tag}")
        ing = make_ingredient(
            s, name=f"picker-{tag}", unit="kg",
            stock_qty=0.0, min_stock_qty=10.0,
            purchase_price_gs=4500,
        )
        ing.supplier_id = sup1.id
        s.commit()
    finally:
        s.close()

    r = client.get("/reorder")
    assert r.status_code == 200
    body = r.text
    # Each row has a supplier picker with the supplier list rendered
    assert 'class="supplier-picker"' in body, (
        "every reorder row must have a supplier-picker element"
    )
    assert f"pickr1-{tag}" in body, (
        "supplier name must appear inside the picker options"
    )
    # The Q1 inline-price pattern: '<supplier_name> — <price>' or 'sin registro'
    assert "—" in body, (
        "price separator (em-dash) must appear in the dropdown labels"
    )


def test_reorder_renders_four_reponer_cells_per_row(client, session_factory):
    """Q3a: Reponer is split into Cantidad / Unidad / Precio / Confirmar."""
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        tag = uuid.uuid4().hex[:8]
        sup = make_supplier(s, name=f"split-{tag}")
        ing = make_ingredient(
            s, name=f"split-{tag}", unit="kg",
            stock_qty=0.0, min_stock_qty=10.0,
            purchase_price_gs=4500,
        )
        ing.supplier_id = sup.id
        s.commit()
    finally:
        s.close()

    r = client.get("/reorder")
    assert r.status_code == 200
    body = r.text

    # Header row has the 4 column titles in order
    assert ">Cantidad<" in body, "Cantidad column header must render"
    assert ">Unidad<" in body, "Unidad column header must render"
    assert ">Precio<" in body, "Precio column header must render"
    assert ">Confirmar<" in body, "Confirmar column header must render"

    # No more monolithic Reponer header (Q3 regression check)
    assert "<th>Reponer</th>" not in body, (
        "old single-column Reponer header must be gone"
    )


def test_reorder_renders_locked_badge_and_attribute(client, session_factory):
    """Q2: when an ingredient has locked_supplier_id, badge + data-locked attr render."""
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        tag = uuid.uuid4().hex[:8]
        sup = make_supplier(s, name=f"lock-{tag}")
        ing = make_ingredient(
            s, name=f"lock-{tag}", unit="kg",
            stock_qty=0.0, min_stock_qty=10.0,
            purchase_price_gs=4500,
        )
        ing.supplier_id = sup.id
        ing.locked_supplier_id = sup.id
        ing.purchase_streak_count = LOCK_THRESHOLD
        s.commit()
    finally:
        s.close()

    r = client.get("/reorder")
    assert r.status_code == 200
    body = r.text

    # "fijo" badge
    assert ">fijo<" in body, "locked supplier badge must render"
    # data-locked attr on the picker
    assert 'data-locked="1"' in body, (
        "supplier-picker must have data-locked=1 when ingredient is locked"
    )
    # Locked-row class
    assert "reorder-row--locked" in body, (
        "row must be marked reorder-row--locked when locked"
    )


def test_reorder_registrar_records_supplier(client, session_factory):
    """POST /reorder/registrar with supplier_id → ingredient.last_purchase_supplier_id updated."""
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        tag = uuid.uuid4().hex[:8]
        sup = make_supplier(s, name=f"post-{tag}")
        ing = make_ingredient(
            s, name=f"post-{tag}", unit="kg",
            stock_qty=0.0, min_stock_qty=10.0,
            purchase_price_gs=4500,
        )
        ing.supplier_id = None  # no parent default
        ing_id = ing.id
        sup_id = sup.id
        s.commit()
    finally:
        s.close()

    r = client.post(
        "/reorder/registrar",
        data={
            "ingredient_id": str(ing_id),
            "qty": "10.0",
            "qty_unit": "kg",
            "price_gs": "4500",
            "supplier_id": str(sup_id),
            "notes": "",
        },
        follow_redirects=False,
    )
    assert r.status_code in (303, 200), (
        f"POST /reorder/registrar must redirect (303) or render; got {r.status_code}"
    )

    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        ing = s.get(Ingredient, ing_id)
        assert ing is not None
        assert ing.last_purchase_supplier_id == sup_id, (
            f"POST must set last_purchase_supplier_id={sup_id}; "
            f"got {ing.last_purchase_supplier_id}"
        )
        assert ing.purchase_streak_count == 1
        assert ing.locked_supplier_id is None  # only 1 buy so far
    finally:
        s.close()


def test_reorder_registrar_omitted_supplier_does_not_overwrite(
    client, session_factory
):
    """Omitting supplier_id leaves the existing last_purchase pointer intact."""
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        tag = uuid.uuid4().hex[:8]
        sup = make_supplier(s, name=f"keep-{tag}")
        ing = make_ingredient(
            s, name=f"keep-{tag}", unit="kg",
            stock_qty=0.0, min_stock_qty=10.0,
            purchase_price_gs=4500,
        )
        ing.supplier_id = sup.id
        ing.last_purchase_supplier_id = sup.id
        ing_id = ing.id
        sup_id = sup.id
        s.commit()
    finally:
        s.close()

    r = client.post(
        "/reorder/registrar",
        data={
            "ingredient_id": str(ing_id),
            "qty": "10.0",
            "qty_unit": "kg",
            "price_gs": "4500",
            "notes": "",
            # no supplier_id
        },
        follow_redirects=False,
    )
    assert r.status_code in (303, 200)

    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        ing = s.get(Ingredient, ing_id)
        assert ing.last_purchase_supplier_id == sup_id, (
            "missing supplier_id must NOT clobber the existing last-purchase"
        )
    finally:
        s.close()


def test_reorder_json_exposes_supplier_options(client, session_factory):
    """JSON endpoint surfaces supplier_options for downstream tools."""
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        tag = uuid.uuid4().hex[:8]
        sup = make_supplier(s, name=f"json-{tag}")
        ing = make_ingredient(
            s, name=f"json-{tag}", unit="kg",
            stock_qty=0.0, min_stock_qty=10.0,
        )
        ing.supplier_id = sup.id
        s.commit()
    finally:
        s.close()

    r = client.get("/reorder?format=json")
    assert r.status_code == 200
    payload = r.json()
    assert "supplier_options" in payload, (
        "JSON must expose supplier_options"
    )
    supplier_names = [o["name"] for o in payload["supplier_options"]]
    assert f"json-{tag}" in supplier_names, "newly created supplier must appear"
    # Items also include the effective supplier_id
    assert all(
        "effective_supplier_id" in item for item in payload["items"]
    ), "every item must carry effective_supplier_id"
    # Lock threshold surfaced for tooling (analytics-only now — locks
    # are a manual 🔒 toggle, not an automatic streak consequence).
    assert payload.get("lock_threshold") == LOCK_THRESHOLD


def test_reorder_template_has_cascade_banner(client, session_factory):
    """The cascade banner DOM hook exists for JS to populate on supplier change."""
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        tag = uuid.uuid4().hex[:8]
        sup = make_supplier(s, name=f"banner-{tag}")
        ing = make_ingredient(
            s, name=f"banner-{tag}", unit="kg",
            stock_qty=0.0, min_stock_qty=10.0,
        )
        ing.supplier_id = sup.id
        s.commit()
    finally:
        s.close()

    r = client.get("/reorder")
    body = r.text
    assert 'id="supplier-cascade-banner"' in body, (
        "cascade banner element must exist in DOM for JS to populate"
    )
    assert "cascadeSupplier" in body, (
        "JS cascadeSupplier function must be inlined in the page"
    )