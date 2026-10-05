"""tests/browser/helpers.py — browser fixtures. The ONLY file that knows
how to start the app + the browser. Everything else uses `pw_page`.

Strategy: run the real FastAPI app on a real localhost port with a seeded
temp DB (factories), auth-test-mode enabled, then drive it with headless
Chromium. This is the real front end — real JS, real CSS, real clicks.
"""

from __future__ import annotations

import threading
import time

import pytest

from . import CHROME

pytestmark = pytest.mark.browser


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch(
            executable_path=CHROME,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        yield b
        b.close()


def _build_app_engine():
    """Fresh engine + schema, same wiring the pytest client fixture uses."""
    import os
    import tempfile

    os.environ.setdefault("SASKIA_TEST_AUTH_DISABLED", "1")

    from app.rms.db import init_db, make_engine

    d = tempfile.mkdtemp(prefix="pw-sazon-")
    engine = make_engine(f"sqlite:///{d}/pw.sqlite")
    init_db(engine)
    return engine


@pytest.fixture()
def pw_page(browser, request):
    """A logged-in browser page against a fresh seeded app instance."""
    import uvicorn

    from app.rms.db import make_session_factory
    from app.rms.main import app as fastapi_app
    from tests.factories import (
        make_catalog,
        make_customer,
        make_product,
    )

    engine = _build_app_engine()
    sf = make_session_factory(engine)

    # CRITICAL: make the app's OWN engine resolution use our engine (same
    # trick as tests/conftest.py client fixture) so the lifespan/get_session
    # see the seeded DB. Patch both the main-module binding AND the source
    # module (lifespan imports from db).
    from app.rms import db as db_module
    from app.rms import main as main_module

    main_module.make_engine_dialect = lambda *a, **k: engine
    db_module.make_engine_dialect = lambda *a, **k: engine

    # seed a small world through the factories
    from datetime import datetime, timedelta, timezone

    with sf() as s:
        cat = make_catalog(s, price_gs=10_000)  # product+recipe+ingredient
        make_product(s, name="Café con leche", sale_price_gs=7_000)
        make_customer(s, name="María López", notes="alergia: gluten")
        make_customer(s, name="Pedro Giménez")
        # quick-sell panel needs recent sales
        from tests.factories import make_sale

        t0 = datetime.now(timezone.utc) - timedelta(hours=2)
        for _ in range(3):
            make_sale(s, product=cat["product"], qty=1, at=t0)
            t0 += timedelta(minutes=10)
        s.commit()

    fastapi_app.state.engine = engine
    fastapi_app.state.session_factory = sf

    config = uvicorn.Config(fastapi_app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    # wait for the ephemeral port to bind
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    port = server.servers[0].sockets[0].getsockname()[1]
    base = f"http://127.0.0.1:{port}"

    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page._saskia_base = base  # stashed for the page objects
    page._saskia_factory = sf
    page.goto(base + "/dashboard")

    yield page

    ctx.close()
    server.should_exit = True
    thread.join(timeout=5)
    engine.dispose()
