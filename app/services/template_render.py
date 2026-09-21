"""app/services/template_render.py — Jinja2 template rendering helper.

Wraps FastAPI's Jinja2Templates with app-state globals (now_year, etc.).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# Single global Jinja2Templates instance; uses the app's templates dir.
templates = Jinja2Templates(directory="app/templates")


# Globals exposed to all templates
def _now_year() -> int:
    return datetime.now().year


def _asset_version() -> str:
    """Cache-busting suffix for static assets.

    Derived from the newest mtime among the static files, computed once
    at import. Any deploy that changes app.css / calendar.css / *.js
    changes the query string, so browsers drop their cached copy.
    (Static files are served with Cache-Control: max-age=3600 — without
    a version param a stale sheet can outlive a deploy by up to an hour,
    which broke the nav dropdown right after PR #10 shipped.)
    """
    import os

    try:
        static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
        newest = max(
            os.path.getmtime(os.path.join(static_dir, f))
            for f in os.listdir(static_dir)
            if os.path.isfile(os.path.join(static_dir, f))
        )
        return str(int(newest))
    except OSError:
        return "0"


# Register as Jinja2 "global functions" so {{ now_year() }} works in templates.
# Without the parens Jinja would print the function repr.
templates.env.globals["now_year"] = _now_year
templates.env.globals["asset_version"] = _asset_version


def render(
    request: Request,
    template_name: str,
    context: dict | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """Render a Jinja2 template with the standard context.

    Always injects `request` so templates can use {{ url_for(...) }}.
    """
    ctx = context or {}
    ctx.setdefault("request", request)
    return templates.TemplateResponse(request, template_name, ctx, status_code=status_code)


__all__ = ["render", "templates"]
