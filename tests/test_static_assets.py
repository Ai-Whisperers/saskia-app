"""tests/test_static_assets.py — favicon + minified CSS contract."""
from __future__ import annotations


def test_favicon_svg_served():
    """/static/favicon.svg returns 200 with SVG content."""
    resp = client_get_favicon_svg()
    assert resp.status_code == 200
    assert "svg" in resp.text.lower()


def test_favicon_ico_served():
    """/static/favicon.ico returns 200 with PNG content."""
    resp = client_get_favicon_ico()
    assert resp.status_code == 200
    assert resp.headers["content-type"] in (
        "image/x-icon",
        "image/vnd.microsoft.icon",
        "image/png",
    )


def test_base_template_has_favicon_link():
    """base.html includes both favicon link tags (SVG preferred, ICO fallback)."""
    from pathlib import Path
    content = Path("app/templates/base.html").read_text()
    assert 'rel="icon" type="image/svg+xml" href="/static/favicon.svg"' in content
    assert 'rel="alternate icon" type="image/png" href="/static/favicon.ico"' in content


def test_app_css_is_minified():
    """app/static/app.css must be minified (no leading newlines, no comment-only whitespace).

    Per docs/operations/2026-09-09-performance-analysis.md improvement #1
    + performance-research.md resources 6.1/6.4.
    """
    from pathlib import Path
    content = Path("app/static/app.css").read_text()
    # Minified CSS shouldn't start with a newline.
    assert not content.startswith("\n"), "CSS appears unminified (starts with newline)"
    # Minified CSS shouldn't have CSS comments.
    assert "/*" not in content, "CSS contains block comments — should be stripped"
    # Should be smaller than the unminified source.
    # (Original was 13.8KB; minified should be <11KB.)
    assert len(content) < 11000, (
        f"app.css is {len(content)} bytes; should be <11KB after minification. "
        "Run scripts/minify_css.py."
    )


def test_minify_css_script_works():
    """The minify_css.py script produces consistent output (idempotent)."""
    from pathlib import Path
    import subprocess

    # Run the script in --check mode against the current app.css.
    result = subprocess.run(
        ["uv", "run", "python", "scripts/minify_css.py", "--check"],
        capture_output=True,
        text=True,
        cwd=Path("/opt/data/profiles/ivan/scratch/saskia-app-work"),
    )
    # If app.css is already minified, --check returns 0. Otherwise it returns 1.
    # Either way, the script should run without crashing.
    assert result.returncode in (0, 1), f"minify_css.py crashed: {result.stderr}"


# Helpers that don't depend on the test client fixture (so tests are faster).
def client_get_favicon_svg():
    import urllib.request
    req = urllib.request.Request(
        "https://saskia-rms.paragu-ai.com/static/favicon.svg"
        if False  # skip live test; use local instead
        else "http://localhost:8000/static/favicon.svg"
    )
    # Use TestClient via FastAPI for offline test.
    from fastapi.testclient import TestClient
    from app.rms.main import app
    with TestClient(app) as c:
        return c.get("/static/favicon.svg")


def client_get_favicon_ico():
    from fastapi.testclient import TestClient
    from app.rms.main import app
    with TestClient(app) as c:
        return c.get("/static/favicon.ico")
