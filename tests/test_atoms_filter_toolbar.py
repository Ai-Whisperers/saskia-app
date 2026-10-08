"""# allow-hardcoded-dates: fixtures intentionally pin fixed dates (calendar edges, tz math, far-future sentinels); asserted relative to frozen or explicit anchors.
Tests for the filter_toolbar macro in app/templates/_components/atoms.html.

The macro renders a GET-form row with search/select/date inputs. 2026-10-01
extension adds a 'combo' type that renders <ui-combo> (A-1 atom) — see
form-ux-combo-system skill for the web-component contract.
"""

from __future__ import annotations

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape


@pytest.fixture
def jinja_env():
    env = Environment(
        loader=FileSystemLoader("app/templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=False,
        lstrip_blocks=False,
    )
    # Required by combo_field & filter_toolbar macros.
    env.globals["request"] = type("R", (), {"url": type("U", (), {"path": "/test"})()})()
    env.globals["tojson"] = lambda v, *_: (
        __import__("json").dumps(v, ensure_ascii=False) if v is not None else "null"
    )
    return env


def _render_toolbar(env, items, action="/list", applied=None):
    """Render the filter_toolbar macro and return the resulting HTML."""
    tmpl_src = (
        "{% from '_components/atoms.html' import filter_toolbar %}"
        "{{ filter_toolbar(items, action=action, applied=applied) }}"
    )
    tpl = env.from_string(tmpl_src)
    return tpl.render(items=items, action=action, applied=applied)


def test_filter_toolbar_search_renders_input(jinja_env):
    html = _render_toolbar(
        jinja_env,
        [
            {"type": "search", "name": "q", "label": "Buscar", "value": "pan"},
        ],
    )
    assert '<input type="search"' in html
    assert 'name="q"' in html
    assert 'value="pan"' in html


def test_filter_toolbar_select_renders_options(jinja_env):
    html = _render_toolbar(
        jinja_env,
        [
            {
                "type": "select",
                "name": "category",
                "options": [("all", "Todas"), ("bread", "Panadería")],
                "value": "bread",
            },
        ],
    )
    assert "<select" in html
    assert '<option value="all"' in html
    assert '<option value="bread" selected' in html


def test_filter_toolbar_date_renders_date_input(jinja_env):
    html = _render_toolbar(
        jinja_env,
        [
            {"type": "date", "name": "from", "value": "2026-10-01"},
        ],
    )
    assert '<input type="date"' in html
    assert 'name="from"' in html


def test_filter_toolbar_combo_renders_saskia_combo(jinja_env):
    """Combo type wires A-1 ui-combo into the toolbar."""
    html = _render_toolbar(
        jinja_env,
        [
            {
                "type": "combo",
                "name": "product",
                "endpoint": "/api/lookup/products?q=",
                "placeholder": "Producto…",
                "label": "Producto",
            },
        ],
    )
    assert "<ui-combo" in html
    assert 'name="product"' in html
    assert 'endpoint="/api/lookup/products?q="' in html
    assert 'placeholder="Producto…"' in html


def test_filter_toolbar_combo_uses_static_src(jinja_env):
    """Combo can take an inline list (src) instead of endpoint."""
    html = _render_toolbar(
        jinja_env,
        [
            {
                "type": "combo",
                "name": "category",
                "src": [
                    {"value": "bread", "label": "Panadería"},
                    {"value": "pastry", "label": "Bollería"},
                ],
                "value": "bread",
            },
        ],
    )
    assert "<ui-combo" in html
    assert '"value":"bread"' in html or '"value": "bread"' in html


def test_filter_toolbar_submit_and_clear(jinja_env):
    html = _render_toolbar(
        jinja_env,
        [{"type": "search", "name": "q", "label": "Buscar"}],
        action="/list",
        applied=False,
    )
    assert '<button type="submit"' in html

    html2 = _render_toolbar(
        jinja_env,
        [{"type": "search", "name": "q", "label": "Buscar"}],
        action="/list",
        applied=True,
    )
    assert 'class="filter-toolbar__clear"' in html2


def test_filter_toolbar_mixed_types(jinja_env):
    """Real-world: search + select + date + combo on one form."""
    html = _render_toolbar(
        jinja_env,
        [
            {"type": "search", "name": "q", "label": "Buscar"},
            {"type": "select", "name": "kind", "options": [("all", "Todos"), ("sale", "Venta")]},
            {"type": "date", "name": "from"},
            {"type": "combo", "name": "customer", "endpoint": "/api/lookup/customers?q="},
        ],
    )
    assert '<input type="search"' in html
    assert "<select" in html
    assert '<input type="date"' in html
    assert "<ui-combo" in html
    # One single form, one submit.
    assert html.count("<form") == 1
    assert html.count('<button type="submit"') == 1
