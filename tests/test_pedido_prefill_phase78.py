"""tests/test_pedido_prefill_phase78.py — phases 7 (address picker) + 8 (loyalty banner).

Verify the new prefill fields:
- available_addresses: list of saved customer addresses with id/label/
  address_text/is_default/delivery_zone_id
- loyalty_points_balance: customer's current balance
- loyalty_points_projected: 1pt / 1.000 Gs. earn rate applied to clone lines

Plus a templating test ensuring the address picker DOM would be
populated when there are 2+ addresses.
"""

from __future__ import annotations


def test_available_addresses_populated(qseed, session_factory):
    """Kyrian has 2 addresses; prefill returns both."""
    from datetime import date

    from app.rms.models import Customer
    from app.seed.kyrian import KYRIAN_PHONE
    from app.services.customer_prefill import compute_customer_defaults

    qseed("with_kyrian_full")
    with session_factory() as s:
        c = s.query(Customer).filter_by(phone=KYRIAN_PHONE).one()
        out = compute_customer_defaults(s, c.id, today=date(2026, 10, 1))

    assert len(out.available_addresses) == 2
    labels = sorted(a["label"] for a in out.available_addresses)
    assert labels == ["casa", "oficina"]
    # Exactly one is the default
    defaults = [a for a in out.available_addresses if a["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["label"] == "casa"


def test_available_addresses_empty_for_new_customer(session_factory):
    """A new customer has no saved addresses."""
    from datetime import date

    from app.rms.models import Customer
    from app.services.customer_prefill import compute_customer_defaults

    with session_factory() as s:
        c = Customer(name="Sin Direccion", phone="0991112222")
        s.add(c)
        s.commit()
        cid = c.id
    with session_factory() as s:
        out = compute_customer_defaults(s, cid, today=date(2026, 10, 1))

    assert out.available_addresses == []


def test_loyalty_balance_populated(qseed, session_factory):
    """Kyrian's prefill returns her current loyalty_points balance.

    Note: the seed now generates 14 sales with 1pt/1.000 Gs. earn, so
    Kyrian's actual balance is well above the original 494 constant —
    we just verify the field is populated and reasonable.
    """
    from datetime import date

    from app.rms.models import Customer
    from app.seed.kyrian import KYRIAN_PHONE
    from app.services.customer_prefill import compute_customer_defaults

    qseed("with_kyrian_full")
    with session_factory() as s:
        c = s.query(Customer).filter_by(phone=KYRIAN_PHONE).one()
        out = compute_customer_defaults(s, c.id, today=date(2026, 10, 1))

    # Kyrian has >= the seeded base balance (from manual_adjust bonus) +
    # earn rows for every fulfilled sale.
    assert out.loyalty_points_balance > 0
    # Cross-check against the database row
    assert out.loyalty_points_balance == c.loyalty_points


def test_loyalty_projected_from_clone_lines(qseed, session_factory):
    """Projected points = sum(qty * unit_price) / 1000 of the clone lines."""
    from datetime import date

    from app.rms.models import Customer
    from app.seed.kyrian import KYRIAN_PHONE
    from app.services.customer_prefill import compute_customer_defaults

    qseed("with_kyrian_full")
    with session_factory() as s:
        c = s.query(Customer).filter_by(phone=KYRIAN_PHONE).one()
        out = compute_customer_defaults(s, c.id, today=date(2026, 10, 1))

    # Kyrian's most recent pedido total is ~568.000 Gs → ~568 pts
    total_gs = sum(ln["qty"] * ln["unit_price_gs"] for ln in out.clone_lines)
    expected = int(total_gs // 1000)
    assert out.loyalty_points_projected == expected
    assert out.loyalty_points_projected > 0


def test_loyalty_projected_zero_when_no_clone_lines(session_factory):
    """No clone lines → projected = 0."""
    from datetime import date

    from app.rms.models import Customer
    from app.services.customer_prefill import compute_customer_defaults

    with session_factory() as s:
        c = Customer(name="Sin Historial", phone="0992223333", loyalty_points=42)
        s.add(c)
        s.commit()
        cid = c.id
    with session_factory() as s:
        out = compute_customer_defaults(s, cid, today=date(2026, 10, 1))

    assert out.loyalty_points_balance == 42
    assert out.loyalty_points_projected == 0


def test_endpoint_returns_new_fields(client, monkeypatch, qseed, session_factory):
    """The JSON endpoint exposes available_addresses + loyalty fields."""
    from app.rms.models import Customer
    from app.seed.kyrian import KYRIAN_PHONE

    qseed("with_kyrian_full")
    with session_factory() as s:
        c = s.query(Customer).filter_by(phone=KYRIAN_PHONE).one()
        cid = c.id

    r = client.get(f"/pedidos/api/customer-defaults/{cid}")
    assert r.status_code == 200
    body = r.json()
    assert "available_addresses" in body
    assert len(body["available_addresses"]) == 2
    assert "loyalty_points_balance" in body
    assert body["loyalty_points_balance"] > 0
    assert "loyalty_points_projected" in body
    assert body["loyalty_points_projected"] >= 0


def test_template_includes_prefill_blob_for_addresses(client, monkeypatch, qseed, session_factory):
    """GET /pedidos/nuevo?customer_id=X renders the prefill JSON blob
    which contains available_addresses for the JS picker to read."""
    import json
    import re

    from app.rms.models import Customer
    from app.seed.kyrian import KYRIAN_PHONE

    qseed("with_kyrian_full")
    with session_factory() as s:
        c = s.query(Customer).filter_by(phone=KYRIAN_PHONE).one()
        cid = c.id

    r = client.get(f"/pedidos/nuevo?customer_id={cid}")
    html = r.text
    m = re.search(r'<script id="customer-prefill"[^>]*>(.*?)</script>', html, re.DOTALL)
    assert m, "customer-prefill script not rendered"
    prefill = json.loads(m.group(1))
    assert len(prefill["available_addresses"]) == 2
    # Confirm the default is marked
    default = next((a for a in prefill["available_addresses"] if a["is_default"]), None)
    assert default is not None
    assert default["label"] == "casa"
    # Confirm loyalty balance + projected
    assert prefill["loyalty_points_balance"] > 0
    assert prefill["loyalty_points_projected"] >= 0


def test_pedido_prefill_js_has_address_and_loyalty_handlers():
    """The JS file ships with Phase 7 + Phase 8 handlers."""
    path = "/opt/data/profiles/ivan/scratch/saskia-app-work/app/static/pedido-prefill.js"
    with open(path) as f:
        content = f.read()
    assert "renderAddressPicker" in content
    assert "available_addresses" in content
    assert "renderLoyaltyBanner" in content
    assert "loyalty_points_balance" in content
    assert "loyalty_points_projected" in content
