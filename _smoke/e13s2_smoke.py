"""E13.S2 — Venta libre smoke check.

Verifies the route context + template renders the venta libre tile
with a populated product id, and that the cart price column header is in
place. NOT a pytest test — just a one-shot script for the dev to run.
"""
from __future__ import annotations
from typing import Any

import os

os.environ.setdefault("AIW_SASKIA_INTERNAL_ROUTES", "1")
os.environ.setdefault("SASKIA_TEST_AUTH_DISABLED", "1")

import tempfile
from pathlib import Path

tmp = Path(tempfile.mkdtemp())
os.environ["AIW_SASKIA_DB_PATH"] = str(tmp / "test.sqlite")
os.environ["AIW_SASKIA_DATA_DIR"] = str(tmp / "data")
os.environ["AIW_SASKIA_BACKUP_DIR"] = str(tmp / "backups")
os.environ["AIW_SASKIA_LOG_DIR"] = str(tmp / "logs")

from app.rms import main as main_module
from app.rms.db import init_db, make_engine, make_session_factory

engine = make_engine(f"sqlite:///{tmp}/test.sqlite")
init_db(engine)
sf = make_session_factory(engine)


def _make_for_test(url: Any=None, *, for_tests: Any=False):
    return engine
main_module.make_engine_dialect = _make_for_test

from app.rms.seed import seed_demo_data

with sf() as s:
    seed_demo_data(s)

from fastapi.testclient import TestClient

with TestClient(main_module.app, raise_server_exceptions=False) as c:
    main_module.app.state.engine = engine
    main_module.app.state.session_factory = sf
    r = c.get("/ventas")
    print("STATUS", r.status_code)
    body = r.text
    print("HAS_VL_BTN", 'id="venta-libre-btn"' in body)
    print("HAS_PRICE_COL", '<th style="text-align:right;width:110px">Precio</th>' in body)
    print("HAS_CSS_VL", 'quick-sell-btn--varios' in body)
    import re
    m = re.search(r'id="venta-libre-btn"[^>]*data-product-id="(\d+)"', body)
    print("VL_PID", m.group(1) if m else None)
    m2 = re.search(r'class="quick-sell-btn"[^>]*data-product-id="(\d+)"', body)
    print("SAMPLE_PID", m2.group(1) if m2 else None)
    # Confirm a Venta libre row exists in DB
    from app.rms.models import Product
    with sf() as s:
        p = s.query(Product).filter_by(sku="VAR-001").one()
        print("DB_VL_NAME", p.name, "price", p.sale_price_gs, "cat", p.category)
