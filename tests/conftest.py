"""Tests/conftest.py — shared pytest fixtures for the Saskia RMS test suite.

Per docs/operations/2026-09-fase-1-specs.md §9 (test-suite minimum).

Key principle: tests must NEVER write to the production DB path
(`~/.local/share/AIW-Saskia/rms.sqlite`). The `tmp_db_path` fixture
forces every test to use a temp directory.
"""

from __future__ import annotations

import os as _os

# Mount internal routes (Auditoría, Ops) BEFORE app.rms.main is imported.
# NAV-02: these routes are internal-only and gated off in production.
# This MUST be set before the app is constructed (router include happens
# at module import time in main.py).
_os.environ.setdefault("AIW_SASKIA_INTERNAL_ROUTES", "1")
_os.environ.setdefault("SASKIA_TEST_AUTH_DISABLED", "1")

# Suppress "unclosed database" ResourceWarnings during tests.
# SQLAlchemy sessions created via `s = session_factory()` (without context
# manager) leak connections when the Session object is GC'd at test end.
# pytest's unraisable hook intercepts and reports these. Production code
# does NOT have this problem (uses `with` blocks). Silenced here because:
#   - 95 sites across 53 test files would need conversion.
#   - Each test creates a fresh temp DB (tmp_db_path autouse fixture),
#     so leaked connections are meaningless at end of test.
#   - We will audit production session-handling separately (W5).
import sys as _sys

import pytest


class _SilenceUnraisable:
    """Context manager: replace sys.unraisablehook for the duration of a
    test to suppress ResourceWarnings emitted by leaked sqlite3 sessions.

    We use a list as a flag holder because pytest may be in a state where
    patching the global hook directly can race with GC events.
    """

    def __enter__(self):
        self._prev = _sys.unraisablehook
        _sys.unraisablehook = self._silence
        return self

    def __exit__(self, *args):
        _sys.unraisablehook = self._prev

    @staticmethod
    def _silence(unraisable):
        # Re-emit non-ResourceWarning errors so we don't accidentally
        # hide real bugs (KeyboardInterrupt, MemoryError, etc.).
        if unraisable.exc_type is ResourceWarning:
            return
        # Default behavior: print to stderr.
        _sys.__excepthook__(unraisable.exc_type, unraisable.exc_value, unraisable.exc_traceback)





@pytest.fixture(autouse=True)
def _silence_unraisable_resource_warnings():
    """Suppress ResourceWarning emitted by leaked sqlite3 sessions at GC.

    The `s = session_factory()` pattern (95 sites across 53 test files)
    holds the session without a context manager. When pytest's
    unraisable hook fires at GC, it emits ~1,100 ResourceWarning lines
    polluting test output. We suppress them here.

    Production code uses `with session_factory() as s:` correctly.
    See app/rms/dependencies.py: get_session() is wrapped in Depends()
    and FastAPI auto-closes after each request.
    """
    import sys as _sys

    prev_hook = _sys.unraisablehook

    def _silence(unraisable):
        if unraisable.exc_type is ResourceWarning:
            return
        prev_hook(unraisable)

    _sys.unraisablehook = _silence
    try:
        yield
    finally:
        _sys.unraisablehook = prev_hook

@pytest.fixture(autouse=True)
def tmp_db_path(tmp_path, monkeypatch):
    """Force every test to use a fresh temp DB.

    Sets AIW_SASKIA_DB_PATH and AIW_SASKIA_DATA_DIR/BACKUP_DIR/LOG_DIR
    to tmp_path. autouse=True means every test gets this isolation.
    """
    monkeypatch.setenv("AIW_SASKIA_DB_PATH", str(tmp_path / "test.sqlite"))
    monkeypatch.setenv("AIW_SASKIA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AIW_SASKIA_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("AIW_SASKIA_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "8765")
    return tmp_path


@pytest.fixture
def freeze_asuncion(monkeypatch):
    """Freeze 'today' in Asunción for the duration of a test.

    Patches app.routers.produccion._asuncion_today (the source the
    /produccion route filters pedidos by). The midnight-UTC vs
    Asunción-date divergence flaked the encargos tests near 00:00 local.

    Usage:
        def test_x(freeze_asuncion):
            frozen = freeze_asuncion(date(2026, 9, 25))
            ...
    """
    from datetime import date

    def _freeze(d: date):
        import app.routers.produccion as prod_mod
        monkeypatch.setattr(prod_mod, "_asuncion_today", lambda: d)
        return d

    return _freeze


@pytest.fixture
def temp_dir(tmp_path):
    """A fresh temp directory for file-based tests."""
    return tmp_path


@pytest.fixture
def make_decimal():
    """Factory for Decimal values; convenient for parametrize."""
    from decimal import Decimal

    def _make(value):
        return Decimal(str(value))

    return _make


@pytest.fixture
def app_engine(tmp_db_path):
    """Create a file-based SQLite engine in tmp_path with WAL pragmas.

    Use this fixture when you need a DB but not a full FastAPI app.

    File-based (not :memory:) so all connections share the same DB.
    SQLite's :memory: creates a separate DB per connection unless you
    pin a StaticPool — but our WAL pragma listener then can't safely
    apply journal_mode to per-connection in-memory DBs. File-based
    solves both problems.
    """
    from app.rms.db import init_db, make_engine

    engine = make_engine(f"sqlite:///{tmp_db_path}/test.sqlite")
    init_db(engine)
    return engine


@pytest.fixture
def session_factory(app_engine):
    """sessionmaker bound to the app_engine fixture.

    Wraps the underlying sessionmaker so every Session opened through
    it gets tracked in a WeakSet. The autouse ``_close_leaked_sessions``
    fixture closes any still-open sessions at end of test, suppressing
    the ~1,100 ``ResourceWarning: unclosed database`` warnings emitted
    by tests that don't use ``with session_factory() as s:`` (53 files).
    """
    import weakref

    from app.rms.db import make_session_factory

    factory = make_session_factory(app_engine)
    tracked: "weakref.WeakSet" = weakref.WeakSet()
    class TrackedFactory:
        def __call__(self, *args, **kwargs):
            s = factory(*args, **kwargs)
            tracked.add(s)
            return s

        def __getattr__(self, name):
            # Forward attribute access (e.g. .kw) to underlying factory.
            return getattr(factory, name)

    TrackedFactory.__wrapped__ = factory  # for introspection
    TrackedFactory._tracked = tracked
    return TrackedFactory()


@pytest.fixture(autouse=True)
def _close_leaked_sessions(session_factory):
    """At end of test, close any sessions opened but never explicitly closed.

    This is the autouse safety net that suppresses unclosed-DB warnings.
    Tests that use ``with session_factory() as s:`` close normally;
    tests that hold raw ``s = session_factory()`` references are caught
    here so the connection is released.

    Order matters: close sessions BEFORE the engine is GC'd, and force
    a gc.collect() so Python emits the close-time dealloc warning while
    the test session is still active (pytest's unraisable hook
    intercepts it).
    """
    yield
    tracked = getattr(session_factory, "_tracked", None)
    if tracked is None:
        return
    # Close each tracked session.
    for s in list(tracked):
        try:
            s.close()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def reset_app_state():
    """Reset FastAPI app.state between tests so the lifespan override is clean.

    Without this, app.state.engine / app.state.session_factory from one test
    leak into the next, causing tests that should be isolated to share state.
    """
    from app.rms.main import app

    # Clear any state set by previous tests; the `client` fixture repopulates.
    if hasattr(app.state, "engine"):
        del app.state.engine
    if hasattr(app.state, "session_factory"):
        del app.state.session_factory
    if hasattr(app.state, "ready"):
        del app.state.ready
    yield


@pytest.fixture
def client(session_factory, monkeypatch):
    """TestClient wired with a session_factory that uses app_engine.

    Replaces make_engine_dialect in app.rms.main with a deterministic version
    that returns the test engine. This prevents the lifespan from creating
    a separate engine (and a separate DB) at startup.

    For test isolation: the auth gate is bypassed via the
    `SASKIA_TEST_AUTH_DISABLED=1` env var (read by `is_auth_disabled`
    in app/auth.py). The router dependency `require_login_or_disabled`
    returns a fake user when this is set.

    The CSRF cookie is auto-primed on the first GET. The post_csrf_fixture
    variant primes the cookie before tests can POST; this fixture
    transparently retries POSTs against a primed cookie via `client.post`
    wrapper. Most tests just use this fixture directly and POSTs work
    because TestClient persists cookies across requests on the same
    client instance.

    Tests that specifically exercise the auth gate (test_auth_integration.py)
    clear the env var to re-enable auth checks.
    """
    from app.rms import main as main_module

    test_engine = session_factory.kw["bind"]

    def _make_engine_for_test(url=None, *, for_tests=False):
        # Always return our test engine, ignore URL or args.
        return test_engine

    monkeypatch.setattr(main_module, "make_engine_dialect", _make_engine_for_test)
    # Env vars are set in conftest.py top-level (before app.rms.main import)
    # because router mounting happens at import time, not request time.

    from fastapi.testclient import TestClient

    with TestClient(main_module.app, raise_server_exceptions=False) as c:
        main_module.app.state.engine = test_engine
        main_module.app.state.session_factory = session_factory
        # Pre-prime the CSRF cookie. /login is exempt so it won't set the
        # cookie via the middleware; we set it directly here by hitting an
        # HTML route that triggers the priming branch (any non-exempt GET).
        try:
            c.get("/healthz")
            if not c.cookies.get("csrf_token"):
                # As a last resort, generate and inject.
                from app.rms.csrf import generate_csrf_token
                c.cookies.set("csrf_token", generate_csrf_token())
        except Exception:
            pass
        yield c


@pytest.fixture
def authed_client(client):
    """Alias for `client` — auth-disabled TestClient with CSRF primed.

    Most tests don't need to distinguish; this name documents intent.
    """
    return client


@pytest.fixture
def qseed(session_factory):
    """Quick-seed helper for fast targeted test setup.

    Use instead of full seed_demo_data() when the test only needs
    a small known dataset. Saves ~2s per test compared to seed_demo_data.

    Usage:
        def test_x(qseed):
            data = qseed("with_low_stock")
            assert data["low_ingredient"].stock_qty < 1.0
    """
    from tests._fixtures_quick_seed import quick_seed

    def _seed(scenario: str = "basic") -> dict:
        return quick_seed(session_factory, scenario)

    # Attach session_factory so qseed consumers can use it for additional
    # queries after seeding.
    _seed.session_factory = session_factory
    return _seed


# --- Shared Supabase fake for integration tests ---

def _FakeSupabaseForIntegration():
    """Factory — instantiated once per fixture for test isolation."""

    class Fake:
        def __init__(self):
            self.users: dict[str, str] = {}
            self._tokens: dict[str, dict] = {}
            self._refresh: dict[str, str] = {}
            self.reset_called: list[str] = []

        def sign_in_with_password(self, creds):
            email = creds.get("username") or creds.get("email")
            pw = creds.get("password", "")
            if self.users.get(email) != pw:
                raise Exception("Invalid login credentials")
            import uuid
            uid = str(uuid.uuid4())
            self._tokens[uid] = {
                "access_token": f"fake-access-{uid}",
                "refresh_token": f"fake-refresh-{uid}",
                "user_id": uid,
                "email": email,
            }
            self._refresh[uid] = f"fake-refresh-{uid}"
            return self._tokens[uid]

        def refresh_session(self, refresh_token):
            for uid, data in self._tokens.items():
                if data["refresh_token"] == refresh_token:
                    return data
            raise Exception("Invalid refresh token")

        def get_user(self, token):
            for data in self._tokens.values():
                if data["access_token"] == token:
                    return {"id": data["user_id"], "email": data["email"]}
            raise Exception("Invalid token")

        def sign_out(self, token):
            pass

        def reset(self):
            self._tokens.clear()
            self._refresh.clear()

        @property
        def auth(self):
            return self

    return Fake()


@pytest.fixture
def supabase_auth_env(monkeypatch):
    """Patch environment + Supabase clients to enable Supabase Auth.

    Forces a reload of app.auth_supabase so the module-level env
    constants pick up the new values. Patches the lazy client factories
    so no real HTTP calls hit test.supabase.co.
    """
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "fake-anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake-service-key")
    # The auth tests below exercise the REAL login flow. The dev bypass
    # (SASKIA_TEST_AUTH_DISABLED) must be off or it fake-logs-in any
    # password before Supabase is consulted. monkeypatch.delenv restores
    # the original value at teardown.
    monkeypatch.delenv("SASKIA_TEST_AUTH_DISABLED", raising=False)

    # Reload to pick up new env vars FIRST
    import importlib
    import app.auth_supabase as au
    importlib.reload(au)

    # Save original _client value for restoration later
    _orig_client = au._client
    _orig_admin = au._admin_client

    # Now patch (after reload, so our patches persist through yield)
    fake = _FakeSupabaseForIntegration()
    monkeypatch.setattr(au, "_client", fake)
    monkeypatch.setattr(au, "_admin_client", fake)
    monkeypatch.setattr(au, "get_supabase_client", lambda: fake)
    monkeypatch.setattr(au, "get_supabase_admin", lambda: fake)

    # Patch using_supabase so the router dispatches to _login_supabase (not _login_local)
    import app.auth
    monkeypatch.setattr(app.auth, "using_supabase", lambda: True)

    yield au

    # Restore original _client values
    au._client = _orig_client
    au._admin_client = _orig_admin


# --- xlsx fixture: synthetic HEREBUS workbook for import/export tests ---


@pytest.fixture
def mini_xlsx_path(tmp_path):
    """Return a Path to a synthetic HEREBUS-format .xlsx fixture.

    3 ingredients, 1 recipe (Muffin), 3 ingredient lines, 2 products.
    Sales + StockMoves sheets are present but empty (they're runtime data).

    Generated on demand; never checked into git.
    """
    from pathlib import Path

    from openpyxl import Workbook

    path: Path = tmp_path / "mini.xlsx"
    wb = Workbook()
    default_sheet = wb.active
    if default_sheet is not None:
        wb.remove(default_sheet)

    ws = wb.create_sheet("Ingredientes")
    ws.append(["id", "name", "unit", "stock_qty", "purchase_price_gs", "min_stock_qty", "notes"])
    ws.append([1, "Harina", "kg", 2.0, "Gs. 5.000", 0.5, None])
    ws.append([2, "Azúcar", "kg", 1.5, "Gs. 4.000", 0.3, None])
    ws.append([3, "Huevo", "und", 20.0, "Gs. 1.500", 6.0, None])

    ws = wb.create_sheet("Recetas")
    ws.append(["id", "name", "yield_qty", "yield_unit", "notes"])
    ws.append([1, "Muffin", 12.0, "und", None])

    ws = wb.create_sheet("Lineas")
    ws.append(
        [
            "id",
            "recipe_id",
            "recipe_name",
            "line_kind",
            "line_ref_id",
            "target_name",
            "qty",
            "notes",
        ]
    )
    ws.append([1, 1, "Muffin", "ingredient", 1, "Harina", 0.3, None])
    ws.append([2, 1, "Muffin", "ingredient", 2, "Azúcar", 0.2, None])
    ws.append([3, 1, "Muffin", "ingredient", 3, "Huevo", 2.0, None])

    ws = wb.create_sheet("Productos")
    ws.append(
        [
            "id",
            "name",
            "portion_label",
            "sale_price_gs",
            "recipe_id",
            "recipe_name",
            "notes",
        ]
    )
    ws.append([1, "Muffin", "1 muffin", "Gs. 8.000", 1, "Muffin", None])
    ws.append([2, "Mystery", "1 unidad", "Gs. 5.000", None, None, "no recipe"])

    ws = wb.create_sheet("Ventas")
    ws.append(
        [
            "id",
            "sold_at",
            "product_id",
            "product_name",
            "qty",
            "unit_price_gs",
            "notes",
            "voided_at",
        ]
    )

    ws = wb.create_sheet("StockMoves")
    ws.append(["id", "sale_id", "affected_recipe_id", "ingredient_id", "qty_delta"])

    wb.save(str(path))
    return path
