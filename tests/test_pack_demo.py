"""tests/test_pack_demo.py — pack-native demo life (customers/pedidos/sales).

Runs against the same in-memory SQLite harness as test_packs_seed.py.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.rms.models import Base, Customer, Pedido, Product, Sale, StockMovement
from app.rms.seed.pack_demo import reseed_pack, seed_pack_demo
from app.rms.seed.packs import PACKS, seed_pack

PACK = "Café/Cafetería"


def _fresh_session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_demo_life_on_packed_db() -> None:
    s = _fresh_session()
    seed_pack(s, PACK)
    report = seed_pack_demo(s, days_of_history=30, seed=42)
    s.commit()

    assert report["sales"] > 30 * 5
    assert report["customers"] == 42
    assert report["pedidos"] == 28
    # every sale references a product of this pack
    pack_names = {p[0] for p in PACKS[PACK].products}
    names = {
        n
        for (n,) in s.execute(
            select(Product.name).where(Product.id.in_(select(Sale.product_id)))
        ).all()
    }
    assert names and names <= pack_names
    # stock moves exist and reference pack ingredients
    assert s.execute(select(StockMovement.id).limit(1)).scalar_one_or_none() is not None


def test_demo_idempotent_on_seeded_db() -> None:
    s = _fresh_session()
    seed_pack(s, PACK)
    seed_pack_demo(s, days_of_history=14, seed=1)
    s.commit()
    n_before = len(list(s.execute(select(Sale.id)).all()))
    again = seed_pack_demo(s, days_of_history=14, seed=1)
    assert again.get("skipped") is True
    n_after = len(list(s.execute(select(Sale.id)).all()))
    assert n_before == n_after


def test_reseed_switches_pack_cleanly() -> None:
    s = _fresh_session()
    seed_pack(s, "Pizzería")
    seed_pack_demo(s, days_of_history=20, seed=7)
    s.commit()

    result = reseed_pack(s, "Café/Cafetería")
    assert result["demo"]["sales"] > 0

    # no pizzería products survived
    leftover = [
        n
        for (n,) in s.execute(select(Product.name)).all()
        if "pizza" in n.lower() or "muzzarella" in n.lower()
    ]
    assert leftover == []
    # café products + demo life exist
    assert any("espresso" in n.lower() for (n,) in s.execute(select(Product.name)).all())
    assert len(list(s.execute(select(Customer.id)).all())) == 42
    assert len(list(s.execute(select(Pedido.id)).all())) == 28


def test_deterministic_with_same_seed() -> None:
    counts = []
    for _ in range(2):
        s = _fresh_session()
        seed_pack(s, PACK)
        report = seed_pack_demo(s, days_of_history=21, seed=99)
        s.commit()
        counts.append(report["sales"])
    assert counts[0] == counts[1]


def test_demo_requires_products() -> None:
    s = _fresh_session()
    with pytest.raises(ValueError):
        seed_pack_demo(s)
