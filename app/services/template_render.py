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


templates.env.globals["now_year"] = _now_year


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
