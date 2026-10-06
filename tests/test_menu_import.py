"""tests/test_menu_import.py — real-menu importer (task B)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.rms.models_legacy import Product
from app.rms.seed.menu_import import import_menu_csv
from app.rms.seed.packs import seed_pack


@pytest.fixture()
def pizzeria_session():
    engine = create_engine("sqlite://")
    from app.rms.models import Base

    Base.metadata.create_all(engine)
    with Session(engine) as s:
        seed_pack(s, "Pizzería")
        yield s


CARTA = """nombre,precio,categoria
Muzzarella (mediana/8p),50000,Pizzas
Napolitana,55000,Pizzas
Empanada de Carne,8000,Empanadas
Torta de Cumpleaños,120000,Pastelería
"""


def _names(s: Session) -> set[str]:
    return {p.name for p in s.scalars(Product.__table__.select())} if False else {
        p.name for p in s.query(Product).all()
    }


def test_dry_run_touches_nothing(pizzeria_session):
    s = pizzeria_session
    before = sorted(_names(s))
    report = import_menu_csv(s, CARTA, dry_run=True)
    assert sorted(_names(s)) == before  # DB untouched
    c = report.counts
    assert c.get("created", 0) == 2  # would create: reported, not executed
    assert c.get("matched", 0) + c.get("price_updated", 0) + c.get("no_price_matched", 0) >= 2
    assert "DRY-RUN" in report.summary()


def test_import_updates_prices_and_creates_missing(pizzeria_session):
    s = pizzeria_session
    report = import_menu_csv(s, CARTA, dry_run=False)
    c = report.counts
    assert c.get("created", 0) >= 2  # Torta + whatever's not in the pack
    muzz = s.query(Product).filter(Product.name.ilike("%muzzarella%")).first()
    assert muzz is not None and muzz.sale_price_gs == 50000
    torta = s.query(Product).filter(Product.name.ilike("%cumple%")).first()
    assert torta is not None and torta.tags and "importado" in torta.tags
    assert "recosteo" in (torta.notes or "").lower()


def test_idempotent_second_pass(pizzeria_session):
    s = pizzeria_session
    import_menu_csv(s, CARTA, dry_run=False)
    again = import_menu_csv(s, CARTA, dry_run=False)
    c = again.counts
    assert c.get("price_updated", 0) == 0 and c.get("created", 0) == 0
