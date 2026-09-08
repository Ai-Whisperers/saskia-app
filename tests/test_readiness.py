"""tests/test_readiness.py — readiness flag for /healthz + /healthz/deps.

Pre-fix: /healthz returned 200 always. During cold-start, the app
accepted requests before its lifespan completed, leading to 500s on
real routes that the operator saw as "broken".

Post-fix: /healthz returns 503 while app.state.ready is False. Once the
lifespan completes, it flips to 200. This lets operators distinguish
"warming up" from "actually broken".
"""
from __future__ import annotations


def test_healthz_503_when_not_ready(client):
    """/healthz returns 503 when app.state.ready is False."""
    from app.rms.main import app

    app.state.ready = False
    try:
        resp = client.get("/healthz")
        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "warming_up"
    finally:
        app.state.ready = True


def test_healthz_200_when_ready(client):
    """/healthz returns 200 when app.state.ready is True."""
    from app.rms.main import app

    app.state.ready = True
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_healthz_head_503_when_not_ready(client):
    """HEAD variant respects readiness too."""
    from app.rms.main import app

    app.state.ready = False
    try:
        resp = client.head("/healthz")
        assert resp.status_code == 503
    finally:
        app.state.ready = True


def test_healthz_deps_503_when_not_ready(client):
    """/healthz/deps also respects readiness."""
    from app.rms.main import app

    app.state.ready = False
    try:
        resp = client.get("/healthz/deps")
        assert resp.status_code == 503
    finally:
        app.state.ready = True
