"""A.1 regression test — every destructive template MUST use the confirm modal.

Per saskia-only-roadmap.md P0 (cerrar-puertas): no destructive action may
ship without a confirm hook. This test walks every template that ships a
destructive form/button and asserts the appropriate hook is present.

Two patterns are acceptable:
  1. **Form-level** — `<form method="post" ... class="js-confirm-form" ...>`
     Used by: ingrediente_detalle, pedidos, shopping_list, suppliers,
     ventas_historial.
  2. **JS-level** — buttons with `data-action="delete-*"` wrapped by
     `SaskiaConfirmModal.show(...)` inside a click handler.
     Used by: settings_catalog.

The test must check for EITHER pattern per template, and fail loudly if
someone removes the confirm hook from any destructive form. This is the
last line of defense against accidental "click → delete" without a guard.

If this test fails: a destructive button no longer asks the user to
confirm before firing. Add the modal hook back, do NOT relax the test.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ─── Form-level templates ────────────────────────────────────────────────
#
# Each entry says: every <form method="post"> whose `action` attribute ends
# with one of `action_suffixes` must include class="js-confirm-form".
#
# Why only form-level (not link/button-level): the form-level contract is
# the canonical, copy-paste pattern across the app — anything else we add
# later should also be a `<form class="js-confirm-form" ...>` so a future
# maintainer can grep for the class and find every destructive action.

DESTRUCTIVE_TEMPLATES: list[tuple[str, list[str | None]]] = [
    # Variant delete (per-variant, but a destructive state change).
    ("app/templates/ingrediente_detalle.html", ["/eliminar"]),
    # Bulk cancel of pending pedidos.
    ("app/templates/pedidos.html", ["/bulk-cancel"]),
    # Shopping list item delete.
    ("app/templates/shopping_list.html", ["/delete"]),
    # Supplier delete.
    ("app/templates/suppliers.html", ["/eliminar"]),
    # Sale void (anular) — refunds stock + writes audit.
    ("app/templates/ventas_historial.html", ["/anular"]),
    # settings_catalog uses JS-level modal, handled in its own test.
    ("app/templates/settings_catalog.html", [None]),
]


# ─── Helpers ─────────────────────────────────────────────────────────────


def _form_action_ends_with(content: str, action_suffix: str) -> bool:
    """True iff there is a <form method="post" ... action="...<suffix>"> in content."""
    # We accept attributes in any order, so use two patterns.
    # Form: <form ... action="X" ... method="post"> or <form ... method="post" ... action="X">
    escaped = re.escape(action_suffix)
    pattern_with_action_first = r'<form\b[^>]*action="[^"]*' + escaped + r'"[^>]*method="post"'
    pattern_with_method_first = r'<form\b[^>]*method="post"[^>]*action="[^"]*' + escaped + r'"'
    return bool(re.search(pattern_with_action_first, content, re.DOTALL)) or bool(
        re.search(pattern_with_method_first, content, re.DOTALL)
    )


def _form_has_js_confirm_class(content: str, action_suffix: str) -> bool:
    """True iff every form posting to `action_suffix` carries class="js-confirm-form".

    Implementation: split the template by `<form ...>` tokens and inspect
    each one's attributes. This is more robust than a single regex because
    the action URL may contain Jinja substitutions like `{{ s.id }}`.
    """
    # Match each <form ...> opening tag (greedy up to the next `>`).
    form_opens = re.findall(r"<form\b[^>]*>", content, re.DOTALL)
    for tag in form_opens:
        # Pull the action="..." attr (handles Jinja `{{ ... }}`).
        m = re.search(r'action="([^"]*)"', tag)
        if m is None:
            continue
        action = m.group(1)
        # Compare on the literal suffix, but the action may contain a Jinja
        # expression — be permissive: if the suffix appears anywhere in the
        # rendered action attribute, this form matches.
        if action_suffix not in action:
            continue
        if "js-confirm-form" not in tag:
            return False
    return True


# ─── Tests ───────────────────────────────────────────────────────────────


def test_all_destructive_forms_have_confirm():
    """A.1 regression: every destructive <form method="post"> must carry
    class="js-confirm-form". If someone removes the class from a delete
    form, this test fails. Per-template error messages tell the author
    which exact form lost its guard.
    """
    repo_root = Path(__file__).resolve().parents[1]
    failures: list[str] = []

    for rel_path, actions in DESTRUCTIVE_TEMPLATES:
        path = repo_root / rel_path
        assert path.exists(), f"template missing: {rel_path}"
        content = path.read_text(encoding="utf-8")

        for action_suffix in actions:
            # Skip the JS-only template — covered by the next test.
            if action_suffix is None:
                continue
            # Only assert when there is at least one matching form.
            if not _form_action_ends_with(content, action_suffix):
                # No form posting to that action — that's fine, it means
                # the destructive action was removed from this template.
                continue
            if not _form_has_js_confirm_class(content, action_suffix):
                failures.append(
                    f'{rel_path}: <form ... action="*{action_suffix}" method="post"> '
                    f'is missing class="js-confirm-form". Add the class + '
                    f"data-confirm-* attrs (see supplier template for the pattern)."
                )

    assert not failures, (
        "Destructive forms without confirm modal hook found:\n  - " + "\n  - ".join(failures)
    )


def test_settings_catalog_uses_saskia_confirm_modal():
    """A.1 regression for settings_catalog: every data-action="delete-*"
    button must be wrapped by SaskiaConfirmModal.show(...) inside its click
    handler. The 8 data-actions currently wired: cat, channel, payment,
    tier, stock, storage, preset, template.

    If someone removes the .then(...) check from one handler, this test
    fails. We do NOT trust raw button markup — we trust the handler code
    that runs when the user clicks.
    """
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / "app/templates/settings_catalog.html"
    assert path.exists(), "settings_catalog.html missing"
    content = path.read_text(encoding="utf-8")

    # Every data-action="delete-*" attribute used in the markup.
    delete_actions = set(re.findall(r'data-action="(delete-[a-z]+)"', content))
    assert delete_actions, (
        'settings_catalog.html has no data-action="delete-*" attributes — '
        "either the template changed shape or the destructives were removed. "
        "Update this test if that's intentional."
    )

    failures: list[str] = []
    for action in sorted(delete_actions):
        # The handler pattern is the forEach that grabs [data-action="X"]
        # followed (within ~500 chars) by a SaskiaConfirmModal.show call.
        # The .+? is non-greedy so we don't span across handlers.
        handler_pattern = (
            r"\[data-action=\"" + re.escape(action) + r'"\]'
            r".*?SaskiaConfirmModal\.show"
        )
        if not re.search(handler_pattern, content, re.DOTALL):
            failures.append(
                f'settings_catalog.html: button data-action="{action}" is not '
                f"wrapped by SaskiaConfirmModal.show(). Add the modal wrapper "
                f"inside the .forEach() handler."
            )

    assert not failures, (
        "settings_catalog delete buttons without confirm modal hook:\n  - "
        + "\n  - ".join(failures)
    )


@pytest.mark.parametrize(
    ("rel_path", "action_suffix"),
    [
        ("app/templates/ingrediente_detalle.html", "/eliminar"),
        ("app/templates/pedidos.html", "/bulk-cancel"),
        ("app/templates/shopping_list.html", "/delete"),
        ("app/templates/suppliers.html", "/eliminar"),
        ("app/templates/ventas_historial.html", "/anular"),
    ],
)
def test_each_destructive_form_individually(rel_path: str, action_suffix: str):
    """Granular per-form assertion — when the main test fails, this
    pinpoint tells you exactly which form to fix.

    Failures from this test carry the exact (template, action_suffix)
    pair so the error message names the form. The main test is the
    authority; this is just for nicer diagnostics.
    """
    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / rel_path
    content = path.read_text(encoding="utf-8")

    if not _form_action_ends_with(content, action_suffix):
        pytest.skip(f"{rel_path} no longer has a form posting to ...{action_suffix}")

    assert _form_has_js_confirm_class(content, action_suffix), (
        f'{rel_path}: <form action="*{action_suffix}"> lost its '
        f'class="js-confirm-form". A.1 (cerrar-puertas) regression.'
    )
