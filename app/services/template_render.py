"""app/services/template_render.py — Jinja2 template rendering helper.

Wraps FastAPI's Jinja2Templates with app-state globals (now_year, m, etc.).
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

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


# --- Money helpers exposed to templates as {{ m.gs(x) }}, etc. ---
# The dashboard and several other templates call these as `m.gs`, `m.gs_full`,
# `m.margin_pct`, and `m.top_list_card`. We bind them as Jinja globals so the
# templates can stay simple. Lazy-imported to keep template_render import-light.
def _make_money_helper():
    """Build the `m` namespace exposed to templates."""
    from app.rms.money import format_gs, to_decimal

    def gs(value):
        """Format integer Gs. as 'Gs. 8.696.000' (Paraguayan convention).

        Use {{ m.gs(x) }} — the result already includes the 'Gs. ' prefix.
        """
        return format_gs(value)

    def gs_plain(value):
        """Format integer Gs. as '8.696.000' WITHOUT the 'Gs.' prefix.
        Use in table cells where the column header already says 'Gs.'.
        """
        if value is None:
            return "—"
        return f"{value:,}".replace(",", ".") if value >= 0 else f"-{abs(value):,}".replace(",", ".")

    def gs_full(value):
        """Alias for gs() — kept for templates that already use this name."""
        return format_gs(value)

    def margin_pct(margen_gs, ventas_gs):
        """Compute gross margin percent (one decimal, Paraguayan style)."""
        if not ventas_gs:
            return "—"
        return f"{(margen_gs / ventas_gs * 100):.1f}%"

    def stock_badge(stock_qty, min_stock_qty):
        """Tier-based stock badge.

        stock == 0         → Agotado (solid red badge)
        0 < stock < min    → Bajo   (amber outline)
        stock >= min       → OK     (muted gray)
        stock < 0          → Negativo (solid red, louder than Agotado)
        """
        try:
            s = float(stock_qty or 0)
            mn = float(min_stock_qty or 0)
        except (TypeError, ValueError):
            return '<span class="badge">—</span>'
        if s < 0:
            return '<span class="badge--stock-out" title="Stock negativo">Negativo</span>'
        if s == 0:
            return '<span class="badge--stock-out" title="Sin stock">Agotado</span>'
        if s < mn:
            return '<span class="badge--stock-low" title="Stock bajo el mínimo">Bajo</span>'
        return '<span class="badge--stock-ok" title="Stock suficiente">OK</span>'

    def top_list_card(title, items, currency_prefix="", icon_id=None):
        """Render a top-N list as a compact card. Pure string builder
        because Jinja macros would need an extra import."""
        if not items:
            return f'<div class="card"><h3>{title}</h3><p class="muted">Sin datos.</p></div>'
        icon_html = (
            f'<svg class="icon"><use href="#{icon_id}"/></svg>' if icon_id else ""
        )
        rows = "".join(
            f'<li><span class="name">{it.get("name", "—")}</span>'
            f'<span class="value">{currency_prefix}{format_gs(it.get("value", 0))}</span></li>'
            for it in items
        )
        return (
            f'<div class="card top-list-card">{icon_html}'
            f'<h3>{title}</h3><ol>{rows}</ol></div>'
        )

    return SimpleNamespace(
        gs=gs,
        gs_plain=gs_plain,
        gs_full=gs_full,
        margin_pct=margin_pct,
        stock_badge=stock_badge,
        top_list_card=top_list_card,
    )


# Register as Jinja2 "global functions" so {{ now_year() }} works in templates.
# Without the parens Jinja would print the function repr.
templates.env.globals["now_year"] = _now_year
templates.env.globals["asset_version"] = _asset_version
templates.env.globals["m"] = _make_money_helper()


def render(
    request: Request,
    template_name: str,
    context: dict | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """Render a Jinja2 template with the standard context.

    Always injects `request` so templates can use {{ url_for(...) }}.
    Also injects `branding` (Phase 5 — operator-configurable) so every
    page can read {{ branding.business_name }}, {{ branding.tagline }},
    etc. The branding dict is loaded once per request from SettingsKV;
    failures fall back to DEFAULT_BRANDING so a missing/broken settings
    row never breaks the render path.
    """
    ctx = context or {}
    ctx.setdefault("request", request)

    # Phase 5 — load branding once per request. Lazy import keeps
    # template_render import-light.
    if "branding" not in ctx:
        try:
            from app.rms.db import make_session_factory, get_db_session
            from app.rms.settings_runtime import get_branding
            engine = request.app.state.engine if hasattr(request.app.state, "engine") else None
            if engine is not None:
                sf = make_session_factory(engine)
                with get_db_session(sf) as session:
                    ctx["branding"] = get_branding(session)
            else:
                from app.rms.settings_runtime import DEFAULT_BRANDING
                ctx["branding"] = DEFAULT_BRANDING
        except Exception:
            from app.rms.settings_runtime import DEFAULT_BRANDING
            ctx["branding"] = DEFAULT_BRANDING

    return templates.TemplateResponse(request, template_name, ctx, status_code=status_code)


__all__ = ["render", "templates"]
