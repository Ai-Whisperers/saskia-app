"""tests/test_onboard.py — one-command onboarding."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.rms.models import Base, Customer, Pedido, Sale, Tenant, User
from app.rms.seed.onboard import onboard_tenant, onboarding_summary


def _fresh_session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_onboard_full_shape() -> None:
    s = _fresh_session()
    report = onboard_tenant(s, "Pizzería Don Carlos", pack="Pizzería", seed=5)
    s.commit()

    assert report["pack"] == "Pizzería"
    tenants = list(s.scalars(select(Tenant)).all())
    assert len(tenants) == 1 and tenants[0].business_name == "Pizzería Don Carlos"
    users = list(s.scalars(select(User)).all())
    assert len(users) == 1 and users[0].username == "admin"
    assert users[0].check_password("cambiar1234")
    assert report["demo"]["sales"] > 0
    assert list(s.execute(select(Sale.id)).all())
    assert list(s.execute(select(Customer.id)).all())
    assert list(s.execute(select(Pedido.id)).all())


def test_onboard_rejects_unknown_pack() -> None:
    s = _fresh_session()
    with pytest.raises(ValueError):
        onboard_tenant(s, "X", pack="No Existe")


def test_onboard_summary_mentions_login() -> None:
    s = _fresh_session()
    rep = onboard_tenant(s, "Café Central", pack="Café/Cafetería", seed=9)
    s.commit()
    txt = onboarding_summary(rep)
    assert "Café Central" in txt and "admin" in txt
