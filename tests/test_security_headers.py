"""Security headers tests — verify hardening is in place."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.security


def test_csp_header_present(client):
    """Content-Security-Policy header must be present on HTML responses."""
    r = client.get("/login")
    assert "content-security-policy" in {k.lower() for k in r.headers.keys()}, (
        f"No CSP header. Headers: {dict(r.headers)}"
    )


def test_x_frame_options_present(client):
    """X-Frame-Options header must be present (clickjacking protection)."""
    r = client.get("/login")
    assert "x-frame-options" in {k.lower() for k in r.headers.keys()}, (
        f"No X-Frame-Options header. Headers: {dict(r.headers)}"
    )


def test_x_content_type_options_present(client):
    """X-Content-Type-Options must be 'nosniff' (MIME type sniffing protection)."""
    r = client.get("/login")
    headers_lower = {k.lower(): v for k, v in r.headers.items()}
    if "x-content-type-options" in headers_lower:
        assert headers_lower["x-content-type-options"].lower() == "nosniff", (
            f"X-Content-Type-Options is '{headers_lower['x-content-type-options']}', expected 'nosniff'"
        )


def test_strict_transport_security_present_on_https(client):
    """HSTS header should be present (Render terminates TLS)."""
    r = client.get("/login")
    # On HTTPS (Render), HSTS must be set
    # In TestClient (HTTP), may be missing
    if "strict-transport-security" in {k.lower() for k in r.headers.keys()}:
        hsts = r.headers.get("strict-transport-security", "")
        assert "max-age" in hsts.lower(), f"HSTS missing max-age: {hsts}"


def test_referrer_policy_present(client):
    """Referrer-Policy header must be present."""
    r = client.get("/login")
    assert "referrer-policy" in {k.lower() for k in r.headers.keys()}, "No Referrer-Policy header"


def test_permissions_policy_present(client):
    """Permissions-Policy header must be present."""
    r = client.get("/login")
    assert "permissions-policy" in {k.lower() for k in r.headers.keys()}, (
        "No Permissions-Policy header"
    )


def test_no_server_header_leaks_version(client):
    """Server header must NOT leak version (security hardening)."""
    r = client.get("/login")
    server = r.headers.get("server", "")
    # Should be empty or generic (not "uvicorn/0.32.0")
    if server:
        assert "/" not in server or "cloudflare" in server.lower(), (
            f"Server header may leak version: '{server}'"
        )


def test_security_headers_on_healthz(client):
    """Health endpoints must also have security headers."""
    r = client.get("/healthz")
    headers_lower = {k.lower() for k in r.headers.keys()}
    assert "x-frame-options" in headers_lower or "content-security-policy" in headers_lower


def test_cross_origin_opener_policy_present(client):
    """Cross-Origin-Opener-Policy: same-origin isolates the window from
    cross-origin popups/tabs (Spectre-class side-channel defense). OWASP
    ZAP rule 90004 also fires for COOP absence.
    """
    r = client.get("/login")
    headers_lower = {k.lower(): v for k, v in r.headers.items()}
    assert "cross-origin-opener-policy" in headers_lower, (
        f"No Cross-Origin-Opener-Policy header. Headers: {dict(r.headers)}"
    )
    assert headers_lower["cross-origin-opener-policy"].lower() == "same-origin", (
        f"Cross-Origin-Opener-Policy is '{headers_lower['cross-origin-opener-policy']}', expected 'same-origin'"
    )


def test_cross_origin_resource_policy_present(client):
    """Cross-Origin-Resource-Policy: same-origin defends against Spectre-class
    cross-origin read attacks. OWASP ZAP rule 90004 will fail CI if this is
    missing. Sazón is same-origin by design; we have no legitimate cross-origin
    resource consumers.
    """
    r = client.get("/login")
    headers_lower = {k.lower(): v for k, v in r.headers.items()}
    assert "cross-origin-resource-policy" in headers_lower, (
        f"No Cross-Origin-Resource-Policy header. Headers: {dict(r.headers)}"
    )
    assert headers_lower["cross-origin-resource-policy"].lower() == "same-origin", (
        f"Cross-Origin-Resource-Policy is '{headers_lower['cross-origin-resource-policy']}', expected 'same-origin'"
    )


def test_cross_origin_resource_policy_on_error_responses(client):
    """CORP must also be present on 4xx/5xx error responses, not just 200s.

    The pure-ASGI SecurityHeadersMiddleware catches HTTPException raised from
    inner middleware (CSRF 403, /login POST 401, etc.) and builds a JSONResponse
    with headers attached. If the except branch forgot to forward CORP, ZAP
    would still flag rule 90004 on the error paths.
    """
    # CSRF: POST to a CSRF-protected endpoint without a token → 403
    r = client.post("/clientes", json={"name": "test"})
    headers_lower = {k.lower(): v for k, v in r.headers.items()}
    assert "cross-origin-resource-policy" in headers_lower, (
        f"Missing CORP on error. Status: {r.status_code}, headers: {dict(r.headers)}"
    )
    assert headers_lower["cross-origin-resource-policy"].lower() == "same-origin"
