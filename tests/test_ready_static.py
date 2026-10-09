"""tests/test_ready_static.py — verify /static/* returns 503 during cold-start."""

from __future__ import annotations


def test_static_path_uses_ready_static_files():
    """The /static mount must be ReadyStaticFiles, not plain StaticFiles."""
    from app.rms.main import app
    from app.rms.ready_static import ReadyStaticFiles

    static_route = None
    for route in app.routes:
        if getattr(route, "path", "") == "/static" and not route.path.startswith("/static/"):
            static_route = route
            break

    assert static_route is not None, "No /static route found"
    # The actual mount app is in route.app
    mounted_app = getattr(static_route, "app", None)
    assert isinstance(mounted_app, ReadyStaticFiles), (
        f"/static must be mounted via ReadyStaticFiles, got {type(mounted_app).__name__}"
    )


def test_static_asset_loads_in_normal_mode(client):
    """When ready=True, /static/app.css returns 200 with the actual CSS."""
    resp = client.get("/static/app.css")
    assert resp.status_code == 200
    assert "body" in resp.text or "--" in resp.text  # CSS contains body{} or --var


def test_static_asset_returns_503_when_not_ready():
    """During cold-start, /static/app.css returns 503 with warming_up payload.

    We test the ReadyStaticFiles class directly (without lifespan firing)
    so we can simulate the unready state.
    """
    import asyncio

    from fastapi import FastAPI

    from app.rms.ready_static import ReadyStaticFiles

    app = FastAPI()
    # Make a fake mounted StaticFiles subclass instance for testing.
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Write a tiny file.
        path = os.path.join(tmpdir, "test.css")
        with open(path, "w") as f:
            f.write("body { color: red; }")
        ready_static = ReadyStaticFiles(directory=tmpdir)

        async def run_scope(ready_flag):
            captured = {}

            async def send(message):
                captured.setdefault(message["type"], message)

            scope = {
                "type": "http",
                "method": "GET",
                "path": "/test.css",
                "raw_path": b"/test.css",
                "headers": [],
                "query_string": b"",
                "root_path": "",
                "scheme": "http",
                "server": ("testserver", 80),
                "client": ("test", 1),
                "app": app,  # FastAPI app with state.ready
            }
            app.state.ready = ready_flag

            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}

            await ready_static(scope, receive, send)
            return captured

        # Unready: expect 503.
        result_unready = asyncio.run(run_scope(False))
        assert result_unready["http.response.start"]["status"] == 503, (
            f"Expected 503 when not ready, got {result_unready['http.response.start']['status']}"
        )

        # Ready: expect 200.
        result_ready = asyncio.run(run_scope(True))
        assert result_ready["http.response.start"]["status"] == 200, (
            f"Expected 200 when ready, got {result_ready['http.response.start']['status']}"
        )
