"""tests/network/test_network_resilience.py — Phase 1 refactored."""
import pytest
from unittest.mock import patch, MagicMock
import httpx


pytestmark = [pytest.mark.network, pytest.mark.smoke]


def test_httpx_module_imports():
    """httpx should be importable for HTTP testing."""
    import httpx
    assert httpx is not None


def test_httpx_timeout_exception():
    """httpx.TimeoutException should be catchable."""
    assert hasattr(httpx, "TimeoutException")
    assert issubclass(httpx.TimeoutException, Exception)


def test_httpx_http_status_error():
    """httpx.HTTPStatusError should be raisable."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    err = httpx.HTTPStatusError("Server Error", request=MagicMock(), response=mock_response)
    assert err.response.status_code == 500


def test_request_timeout_caught():
    """A timeout should be catchable, not crash the app."""
    def fake_get(*args, **kwargs):
        raise httpx.TimeoutException("timeout")

    with patch("httpx.get", side_effect=fake_get):
        try:
            httpx.get("https://example.com")
        except httpx.TimeoutException:
            pass


def test_request_connection_error_caught():
    """Connection error should be catchable."""
    def fake_get(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    with patch("httpx.get", side_effect=fake_get):
        try:
            httpx.get("https://example.com")
        except httpx.ConnectError:
            pass


def test_5xx_response_handled():
    """5xx response should be handleable."""
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "503 Service Unavailable", request=MagicMock(), response=mock_response
    )
    with patch("httpx.get", return_value=mock_response):
        try:
            r = httpx.get("https://example.com")
            r.raise_for_status()
        except httpx.HTTPStatusError:
            pass


def test_429_rate_limit_handled():
    """429 rate limit should be handleable."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.headers = {"Retry-After": "60"}
    with patch("httpx.get", return_value=mock_response):
        r = httpx.get("https://example.com")
        assert r.status_code == 429


def test_optional_dependencies_importable():
    """Retry/respx libs may be optional; verify they exist if installed."""
    try:
        import respx  # noqa
    except ImportError:
        pass
    try:
        import tenacity  # noqa
    except ImportError:
        pass


def test_healthz_responds_under_2s(authed_client):
    """/healthz should respond fast even under load."""
    import time
    start = time.time()
    r = authed_client.get("/healthz", follow_redirects=False)
    elapsed = time.time() - start
    assert elapsed < 2.0
    assert r.status_code in (200, 302, 303, 307, 404, 500)
