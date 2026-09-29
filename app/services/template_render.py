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
    return datetime.now().year  # noqa: DTZ005 — naive is OK, year is tz-independent


def _now():
    """Jinja global `now()` — current Asuncion-local time, **naive**.

    Returns a NEW datetime on each call so templates using `{{ now }}`
    always see the freshest value, even if the render loop runs twice
    in the same request.

    Pedidos and other tz-aware routes used to pass `now` in via the
    context. The /clientes/{id} detail page had been crashing for months
    with 'now' is undefined because the route handler forgot it.

    Naive (no tzinfo) on purpose: SQLAlchemy in this codebase stores
    DateTime columns as naive (DB has no tz awareness). If `now` were
    tz-aware, `now - db_column_xxx` would crash with
    "can't subtract offset-naive and offset-aware" — proven by the
    /clientes/{id} 500 we just fixed. Routes that need tz-aware
    arithmetic should still pass their own `now` from context.

    The Asuncion wall-clock value isn't lost: when the system's local
    tz is set to America/Asuncion (server runtime tz), `datetime.now()`
    returns the Asuncion local time without tzinfo.
    """
    return datetime.now()  # noqa: DTZ005 — intentional naive, see docstring


def _now_local():
    """Jinja global `now_local()` — current local-time formatted for
    `<input type="datetime-local">` (`YYYY-MM-DDTHH:MM`)."""
    return _now().strftime("%Y-%m-%dT%H:%M")


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
    from app.rms.money import format_gs

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

    def margin_pct(margen_gs, ventas_gs) -> str:
        """Compute gross margin percent (one decimal, Paraguayan style)."""
        if not ventas_gs:
            return "—"
        return f"{(margen_gs / ventas_gs * 100):.1f}%"

    def stock_badge(stock_qty, min_stock_qty) -> str:
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

    def top_list_card(title, items, currency_prefix="", icon_id=None) -> str:
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

# F-track formatters (redesign base layer — 02-REUSE-ABSTRACTION.md §2)
from app.rms import display as _display
from app.rms.nav import crumbs_for as _crumbs_for
from app.rms.nav import status_es as _status_es

templates.env.globals["fmt"] = SimpleNamespace(
    money=_display.fmt_money,
    qty=_display.fmt_qty,
    pct=_display.fmt_pct,
    date=_display.fmt_date,
    delta=_display.delta,
    entity_name=_display.entity_name,
    status_es=_status_es,
    crumbs_for=_crumbs_for,
)


def _now_str() -> str:
    """Human date+time for the topbar (Asunción tz, es-PY style)."""
    try:
        from app.rms.config import ASUNCION_TZ

        _DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        _MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
        _n = datetime.now(ASUNCION_TZ)
        return f"{_DIAS[_n.weekday()]} {_n.day} {_MESES[_n.month-1]} {_n.year} · {_n.strftime('%H:%M')}"  # locale set below
    except Exception:  # noqa: BLE001 — topbar date must never break a page
        return datetime.now().strftime("%d/%m/%Y %H:%M")  # noqa: DTZ005 — see _now() docstring


templates.env.globals["now_str"] = _now_str


def _greeting() -> str:
    """Time-aware Spanish greeting (Asunción tz)."""
    try:
        from app.rms.config import ASUNCION_TZ
        h = datetime.now(ASUNCION_TZ).hour
    except Exception:  # noqa: BLE001
        h = datetime.now().hour  # noqa: DTZ005 — hour is tz-independent for greeting purposes
    if 12 <= h < 19:
        return "Buenas tardes"
    if h >= 19 or h < 4:
        return "Buenas noches"
    return "Buen día"


templates.env.globals["greeting"] = _greeting


def _csrf_token_for_request(request: Request | None) -> str:
    """Return the current CSRF token for the active request, or empty
    string outside an active request context (template previews, tests).

    Reads the signed cookie set by the CSRF middleware; if absent,
    generates a fresh token so the form input still renders something
    the verify path can validate.
    """
    from app.rms.csrf import _CSRF_COOKIE as cookie_name
    from app.rms.csrf import generate_csrf_token

    if request is not None:
        token = request.cookies.get(cookie_name)
        if token:
            return token
    return generate_csrf_token()


templates.env.globals["csrf_token"] = _csrf_token_for_request
# Note: `now` and `now_local` are NOT registered as env.globals because
# globals are evaluated once at import time (stale until process restart).
# Instead they're injected per-request via render() with setdefault(), so
# tz-aware Asuncion time is current on every render and route-level
# overrides still win.


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

    ctx["csrf_token"] = _csrf_token_for_request(request)
    # Inject Asuncion-local time + tz-aware datetime on every render.
    # Existing routes that pass their own `now`/`now_local` win (setdefault).
    ctx.setdefault("now_local", _now_local())
    ctx.setdefault("now", _now())

    # Phase 5 — load branding once per request. Lazy import keeps
    # template_render import-light.
    # auth state for chrome (hide nav/search on the login screen).
    # Fail CLOSED: if we can't determine auth state, hide the chrome
    # rather than leak the entire app nav structure to anonymous users.
    try:
        from app.auth import get_current_user, is_auth_disabled

        if is_auth_disabled():
            # Test/dev bypass: auth is disabled, user is always logged in
            ctx.setdefault("is_logged_in", True)
        else:
            # Production: call get_current_user (may raise if no session)
            ctx.setdefault("is_logged_in", get_current_user(request) is not None)
    except Exception:  # noqa: BLE001 — chrome must never break a page
        ctx.setdefault("is_logged_in", False)

    # SS-1: sidebar/nav renders from the nav table (app/rms/nav.py)
    if "nav_groups" not in ctx:
        try:
            from app.rms.nav import NAV_GROUPS
            ctx["nav_groups"] = NAV_GROUPS
        except Exception:  # noqa: BLE001 — nav must never break a page
            ctx["nav_groups"] = []

    if "branding" not in ctx:
        try:
            from app.rms.db import get_db_session, make_session_factory
            from app.rms.settings_runtime import get_branding
            engine = request.app.state.engine if hasattr(request.app.state, "engine") else None
            if engine is not None:
                sf = make_session_factory(engine)
                with get_db_session(sf) as session:
                    ctx["branding"] = get_branding(session)
            else:
                from app.rms.settings_runtime import DEFAULT_BRANDING
                ctx["branding"] = DEFAULT_BRANDING
        except Exception:  # noqa: BLE001 — defensive default — guarded by surrounding try
            from app.rms.settings_runtime import DEFAULT_BRANDING
            ctx["branding"] = DEFAULT_BRANDING

    return templates.TemplateResponse(request, template_name, ctx, status_code=status_code)


__all__ = ["render", "templates"]
