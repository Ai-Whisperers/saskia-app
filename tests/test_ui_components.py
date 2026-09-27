"""tests/test_ui_components.py — End-to-end tests for the new UI primitives.

Tests:
- saskia-toast: script loads + is included on every page
- saskia-skeleton: script loads + skeleton component is defined
- flash_toast macro: renders the SaskiaToast.show() call when ?flash=… is set
- js-confirm-form shim: app.js includes initConfirmForms + shopping-list uses the class

Uses the live FastAPI server. Skipped if no server.
"""
import http.client
import os
import urllib.parse
import urllib.request

import pytest


SERVER_URL = os.environ.get("SASKIA_TEST_URL", "http://127.0.0.1:8765")


def _server_alive() -> bool:
    try:
        with urllib.request.urlopen(SERVER_URL + "/healthz", timeout=1) as r:
            return r.status == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _server_alive(),
    reason="live server not running; start with: uvicorn app.rms.main:app --port 8765",
)


class _Client:
    """HTTP client that handles the secure session cookie via http.client."""
    def __init__(self):
        self.cookies = {}

    def _request(self, method, path, body=None, headers=None):
        host = SERVER_URL.split("://", 1)[1].split(":")[0]
        port = int(SERVER_URL.split(":")[-1])
        h = {"Cookie": "; ".join(f"{k}={v}" for k, v in self.cookies.items())}
        if body is not None:
            h["Content-Type"] = "application/x-www-form-urlencoded"
        if headers:
            h.update(headers)
        conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request(method, path, body=body, headers=h)
        rsp = conn.getresponse()
        for k, v in rsp.getheaders():
            if k.lower() == "set-cookie":
                cookie_pair = v.split(";")[0]
                name, _, val = cookie_pair.partition("=")
                self.cookies[name.strip()] = val.strip()
        return rsp

    def get(self, path):
        return self._request("GET", path)

    def post(self, path, data):
        return self._request("POST", path, body=urllib.parse.urlencode(data))


@pytest.fixture(scope="session")
def client():
    c = _Client()
    data = {"username": "demo", "password": "demo1234"}
    rsp = c.post("/login", data)
    assert rsp.status in (200, 303), f"login failed: status={rsp.status}"
    return c


def _get(client, path):
    rsp = client.get(path)
    body = rsp.read().decode("utf-8", errors="replace")
    return rsp.status, body


# ─── saskia-toast ───────────────────────────────────────────────────────────

def test_saskia_toast_script_loads(client):
    """saskia-toast.js is served and registers the SaskiaToast global."""
    rsp = client.get("/static/saskia-toast.js")
    body = rsp.read().decode()
    assert rsp.status == 200
    assert "SaskiaToast" in body
    assert "show" in body
    assert "dismissAll" in body


def test_saskia_toast_markup_in_page(client):
    """Every page after login includes the toast-stack element + script tag."""
    status, body = _get(client, "/")
    assert status == 200
    assert "saskia-toast-stack" in body
    assert "saskia-toast.js" in body


def test_flash_toast_macro_renders(client):
    """When ?flash=sale_created, the page must include the SaskiaToast.show call."""
    status, body = _get(client, "/ventas?flash=sale_created")
    assert status == 200
    assert "SaskiaToast.show" in body
    assert "Venta registrada correctamente." in body


# ─── saskia-skeleton ────────────────────────────────────────────────────────

def test_saskia_skeleton_script_loads(client):
    """saskia-skeleton.js is served and defines <saskia-skeleton>."""
    rsp = client.get("/static/saskia-skeleton.js")
    body = rsp.read().decode()
    assert rsp.status == 200
    assert "saskia-skeleton" in body
    assert "SaskiaSkeleton" in body


def test_saskia_skeleton_included_in_base(client):
    """base.html must reference saskia-skeleton.js."""
    status, body = _get(client, "/")
    assert status == 200
    assert "saskia-skeleton.js" in body


# ─── js-confirm-form shim ───────────────────────────────────────────────────

def test_app_js_confirm_form_shim(client):
    """app.js must include initConfirmForms and reference js-confirm-form."""
    rsp = client.get("/static/app.js")
    body = rsp.read().decode()
    assert rsp.status == 200
    assert "initConfirmForms" in body
    assert "js-confirm-form" in body


def test_js_confirm_form_used_on_destructive_page(client):
    """Pages with destructive actions should use js-confirm-form class."""
    status, body = _get(client, "/shopping-list")
    assert status == 200
    assert "js-confirm-form" in body


# ─── Bonus: source attribution footer ───────────────────────────────────────

def test_source_footer_on_reports(client):
    """Report pages should include the report-source-footer."""
    for path in [
        "/reportes/iva",
        "/reportes/cierre-mensual",
        "/reportes/top-productos",
        "/reportes/metodos-pago",
    ]:
        status, body = _get(client, path)
        assert status == 200, path
        assert "report-source-footer" in body, f"{path} missing footer"


# ─── Bonus: saskia-date still works ─────────────────────────────────────────

def test_saskia_date_script_loads(client):
    rsp = client.get("/static/saskia-date.js")
    body = rsp.read().decode()
    assert rsp.status == 200
    assert "SaskiaDate" in body


def test_dashboard_renders(client):
    status, body = _get(client, "/dashboard")
    assert status == 200
    # Dashboard must include saskia-toast-stack (every page should)
    assert "saskia-toast-stack" in body


# ─── /benchmarks anchor fixed ───────────────────────────────────────────────

def test_dashboard_anchor_is_vs_mercado(client):
    """The dashboard's /benchmarks anchor must now point at /vs-mercado."""
    status, body = _get(client, "/dashboard")
    assert status == 200
    # /benchmarks must NOT appear in the rendered HTML
    assert 'href="/benchmarks"' not in body, "/benchmarks still referenced"
    # /vs-mercado must appear (in the dashboard anchor + sidebar)
    assert 'href="/vs-mercado"' in body


# ─── /vs-mercado data ───────────────────────────────────────────────────────

def test_vs_mercado_has_rows(client):
    status, body = _get(client, "/vs-mercado")
    assert status == 200
    # Paraguay benchmarks should render
    assert "Chipa grande" in body
    assert "Croissant" in body
    assert "Sopa paraguaya" in body
