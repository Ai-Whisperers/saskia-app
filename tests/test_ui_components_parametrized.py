"""Parametrized UI component checks for tests/test_ui_components.py.

Phase 2 increment #3 (S1 batch2 parametrize expansion): demo the dedup
pattern on the 3rd-largest file in the suite (733 lines). The dominant
patterns are:

    A. /static/<asset>.js loads (200) and contains a sentinel string.
    B. GET /<page> (200) and body contains a sentinel substring.

This file subsumes the simple `@pytest.mark.parametrize`-shaped repeats
into two drivers — a static-asset loader and a page-substring checker —
covering the ui-toast, ui-skeleton, ui-month, ui-combo, ui-date, and
UIConfirmModal families (plus a few one-off page checks).

ADDITIVE only — the originals in test_ui_components.py remain untouched.
If a future batch confirms identical behavior across N runs, the originals
can be deleted in a follow-up commit.

The `client` fixture (live HTTP client against `SASKIA_TEST_URL`) and
`_get(...)` helper are imported from the original test module to keep
auth/cookies behaviour identical. Same server-alive skipif guard applies.
"""

from __future__ import annotations

import pytest

from tests.test_ui_components import _get

# ─── Parametrize rows ─────────────────────────────────────────────
#
# A: static asset loads + sentinel string is present in body.
_STATIC_ASSET_CASES: list[dict] = [
    {
        "id": "ui_toast_js_contains_UIToast",
        "asset": "/static/ui-toast.js",
        "sentinel": "UIToast",
        "description": "ui-toast.js exposes the UIToast class",
    },
    {
        "id": "ui_toast_js_contains_show",
        "asset": "/static/ui-toast.js",
        "sentinel": "show",
        "description": "ui-toast.js wires show()",
    },
    {
        "id": "ui_toast_js_contains_dismissAll",
        "asset": "/static/ui-toast.js",
        "sentinel": "dismissAll",
        "description": "ui-toast.js wires dismissAll()",
    },
    {
        "id": "ui_skeleton_js_contains_ui_skeleton",
        "asset": "/static/ui-skeleton.js",
        "sentinel": "ui-skeleton",
        "description": "ui-skeleton.js defines <ui-skeleton>",
    },
    {
        "id": "ui_skeleton_js_contains_UISkeleton",
        "asset": "/static/ui-skeleton.js",
        "sentinel": "UISkeleton",
        "description": "ui-skeleton.js exposes the UISkeleton class",
    },
    {
        "id": "ui_date_js_contains_UIDate",
        "asset": "/static/ui-date.js",
        "sentinel": "UIDate",
        "description": "ui-date.js exposes the UIDate class",
    },
    {
        "id": "ui_combo_js_contains_UICombo",
        "asset": "/static/ui-combo.js",
        "sentinel": "UICombo",
        "description": "ui-combo.js exposes the UICombo class",
    },
    {
        "id": "ui_combo_js_custom_element_registered",
        "asset": "/static/ui-combo.js",
        "sentinel": "customElements.define('ui-combo'",
        "description": "ui-combo custom element is registered",
    },
    {
        "id": "app_js_includes_initConfirmForms",
        "asset": "/static/app.js",
        "sentinel": "initConfirmForms",
        "description": "app.js includes initConfirmForms",
    },
    {
        "id": "app_components_js_UIConfirmModal_defined",
        "asset": "/static/app-components.js",
        "sentinel": "UIConfirmModal",
        "description": "app-components.js defines window.UIConfirmModal",
    },
]


# B: page renders + sentinel substring is present (status 200).
_PAGE_CASES: list[dict] = [
    {
        "id": "root_includes_toast_stack",
        "path": "/",
        "sentinel": "ui-toast-stack",
        "description": "every page after login includes the toast-stack element",
    },
    {
        "id": "root_includes_toast_script",
        "path": "/",
        "sentinel": "ui-toast.js",
        "description": "every page after login includes the ui-toast.js script tag",
    },
    {
        "id": "dashboard_includes_toast_stack",
        "path": "/dashboard",
        "sentinel": "ui-toast-stack",
        "description": "dashboard renders and includes the toast-stack",
    },
    {
        "id": "shopping_list_uses_confirm_form",
        "path": "/shopping-list",
        "sentinel": "js-confirm-form",
        "description": "destructive pages use js-confirm-form class",
    },
    {
        "id": "vs_mercado_chipa_grande",
        "path": "/vs-mercado",
        "sentinel": "Chipa grande",
        "description": "Paraguay benchmarks row 'Chipa grande' renders",
    },
    {
        "id": "vs_mercado_croissant",
        "path": "/vs-mercado",
        "sentinel": "Croissant",
        "description": "Paraguay benchmarks row 'Croissant' renders",
    },
    {
        "id": "vs_mercado_sopa_paraguaya",
        "path": "/vs-mercado",
        "sentinel": "Sopa paraguaya",
        "description": "Paraguay benchmarks row 'Sopa paraguaya' renders",
    },
]


@pytest.mark.parametrize("spec", _STATIC_ASSET_CASES, ids=lambda s: s["id"])
def test_static_asset_contains_sentinel(client, spec: dict) -> None:
    """Subsumes ~10 originally hand-written *_script_loads(client) tests."""
    rsp = client.get(spec["asset"])
    assert rsp.status == 200, f"{spec['asset']!r} returned {rsp.status}"
    body = rsp.read().decode("utf-8", errors="replace")
    assert spec["sentinel"] in body, (
        f"{spec['description']!r}: sentinel {spec['sentinel']!r} not in {spec['asset']}"
    )


@pytest.mark.parametrize("spec", _PAGE_CASES, ids=lambda s: s["id"])
def test_page_contains_sentinel(client, spec: dict) -> None:
    """Subsumes ~7 originally hand-written *_render / *_in_page(client) tests."""
    status, body = _get(client, spec["path"])
    assert status == 200, f"GET {spec['path']} returned {status}"
    assert spec["sentinel"] in body, (
        f"{spec['description']!r}: sentinel {spec['sentinel']!r} not on {spec['path']}"
    )
