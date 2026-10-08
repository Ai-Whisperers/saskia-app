"""TDD: empty-state on /produccion must show a CTA to add the first row.

Bug: when plan_rows_view is empty (no sales history, no template, no
plan), the operator sees ONLY a passive message. The ad-hoc modal
(which lets them add product+qty via POST /produccion/ad-hoc) is hidden
inside the {% if plan_rows_view %} guard. So the operator literally
cannot add their first row without knowing to URL-hack /produccion/ad-hoc.

Fix: in every empty-state branch (no_sales, no_template, cold_plan,
no_rows, fallback 'unknown'), add a prominent CTA button that opens
the existing ad-hoc modal (data-action="open-adhoc-modal").

TDD: these tests fail before the fix and pass after.
"""

from __future__ import annotations

from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "app" / "templates" / "produccion.html"


def _empty_state_branches() -> dict[str, str]:
    """Return the body of each {% if/elif cold_start_kind == '...' %} block."""
    import re

    text = TEMPLATE.read_text()
    branches = {}
    # Match {% if cold_start_kind == "X" %} ... {% endif %}
    # AND {% elif cold_start_kind == "X" %} ... {% endif %}
    pat = re.compile(
        r'\{%\s*(?:if|elif)\s+cold_start_kind\s*==\s*"([^"]+)"\s*%\}(.*?)(?=\{%\s*(?:elif|else|endif))',
        re.DOTALL,
    )
    for m in pat.finditer(text):
        branches[m.group(1)] = m.group(2)
    return branches


class TestEmptyStateHasAdHocCTA:
    """Each empty-state branch must include a CTA to open the ad-hoc modal."""

    def test_no_sales_branch_has_adhoc_cta(self):
        branch = _empty_state_branches().get("no_sales", "")
        assert branch, "no_sales branch not found in template"
        assert "open-adhoc-modal" in branch, (
            "no_sales empty state must include a button with "
            "data-action='open-adhoc-modal' so the operator can add "
            "their first product even when there's no sales history."
        )

    def test_no_template_branch_has_adhoc_cta(self):
        branch = _empty_state_branches().get("no_template", "")
        assert branch, "no_template branch not found"
        assert "open-adhoc-modal" in branch, (
            "no_template empty state must include a button with data-action='open-adhoc-modal'."
        )

    def test_cold_plan_branch_has_adhoc_cta(self):
        branch = _empty_state_branches().get("cold_plan", "")
        assert branch, "cold_plan branch not found"
        assert "open-adhoc-modal" in branch, (
            "cold_plan empty state must include a button with data-action='open-adhoc-modal'."
        )

    def test_no_rows_branch_has_adhoc_cta_if_present(self):
        """If a no_rows branch exists, it must also have the CTA."""
        branch = _empty_state_branches().get("no_rows", "")
        if not branch:
            # no_rows branch may not exist (the route computes it but
            # the template falls through to the else). Skip.
            return
        assert "open-adhoc-modal" in branch, (
            "no_rows empty state must include a button with data-action='open-adhoc-modal'."
        )

    def test_fallback_else_branch_has_adhoc_cta(self):
        """The {% else %} (unknown cold_start_kind) branch — the most
        common case the operator hits — must also include the CTA."""
        text = TEMPLATE.read_text()
        import re

        # Find the structure: {% if cold_start_kind == "no_sales" %} ... {% elif ... %} ... {% else %} <body> {% endif %}
        # We use the cold-start div as anchor.
        m = re.search(
            r'<div class="card empty-state-cold-start".*?>'
            r".*?\{%\s*else\s*%\}(.*?)\{%%\s*endif\s*%%",
            text,
            re.DOTALL,
        )
        # The regex above may collide with the outer if/endif; use a
        # simpler approach: find the closing {% endif %} of the
        # cold_start_kind if/elif/else block.
        cold_start_open = text.find('{% if cold_start_kind == "no_sales" %}')
        assert cold_start_open != -1
        # Walk forward and find the matching endif (count if/endif)
        _i = cold_start_open
        depth = 0
        end = -1
        for m in re.finditer(r"\{%\s*(if|endif)\b", text[cold_start_open:]):
            token = m.group(1)
            if token == "if":
                depth += 1
            else:
                depth -= 1
                if depth == 0:
                    end = cold_start_open + m.end()
                    break
        assert end != -1
        # The body of the else branch is between {% else %} and {% endif %}
        else_start = text.rfind("{% else %}", cold_start_open, end)
        else_body = text[else_start:end]
        assert "open-adhoc-modal" in else_body, (
            "The fallback {% else %} (unknown cold_start_kind) empty "
            "state must include a button with data-action='open-adhoc-modal'. "
            f"Got body:\n{else_body[:600]}"
        )


class TestAdHocModalExistsOutsideGuard:
    """The ad-hoc modal itself must render even when plan_rows_view is
    empty, otherwise the CTA button has nothing to open."""

    def test_adhoc_modal_renders_outside_if_plan_rows_view(self):
        import re

        text = TEMPLATE.read_text()
        # The ad-hoc modal (id="adhoc-modal") must NOT be inside the
        # {% if plan_rows_view %} block. Easiest check: the matching
        # {% endif %} for plan_rows_view must come BEFORE the modal.
        m = re.search(r"\{%\s*if\s+plan_rows_view\s*%\}", text)
        assert m, "{% if plan_rows_view %} not found"
        # Find the FIRST {% endif %} after `m.end()` that lives at the
        # same indentation level — the comment after the endif tags
        # which view it ends. The day-view {% endif %} is followed by
        # `{# end day view #}` per the comment convention.
        idx = m.end()
        day_view_endif = text.find("{% endif %}{# end day view #}", idx)
        assert day_view_endif != -1, (
            "Could not find `{% endif %}{# end day view #}` marker after "
            "{% if plan_rows_view %}. Either the template restructured "
            "the day-view block or the marker convention changed."
        )
        modal_pos = text.find('<dialog id="adhoc-modal"')
        assert modal_pos != -1, "ad-hoc modal not found in template"
        assert modal_pos > day_view_endif, (
            f"The ad-hoc modal must render OUTSIDE the day-view block "
            f"(after `{{% endif %}}#{{# end day view #}}`). "
            f"Modal at char {modal_pos} (line {text[:modal_pos].count(chr(10)) + 1}), "
            f"day-view endif at char {day_view_endif} (line {text[:day_view_endif].count(chr(10)) + 1}). "
            "The empty-state CTA cannot open a modal that doesn't exist."
        )


class TestAdHocJSHandlerOpensModal:
    """The JS handler for data-action='open-adhoc-modal' must call
    showModal() on #adhoc-modal."""

    def test_static_js_handler_opens_modal(self):
        # The handler is in app/static/js files OR inline in the template
        text = TEMPLATE.read_text()
        # Inline scripts in template
        if "data-action" in text and "open-adhoc-modal" in text:
            # Find inline scripts that reference data-action
            import re

            scripts = re.findall(r"<script[^>]*>(.*?)</script>", text, re.DOTALL)
            for s in scripts:
                if "open-adhoc-modal" in s:
                    assert "showModal" in s or "getElementById" in s, (
                        "Inline script referencing open-adhoc-modal must "
                        "call showModal() or getElementById('adhoc-modal')."
                    )
                    return
        # Otherwise check static JS
        static = Path(__file__).resolve().parents[1] / "app" / "static"
        for js_path in static.rglob("*.js"):
            js = js_path.read_text()
            if "open-adhoc-modal" in js:
                assert "showModal" in js or "getElementById" in js, (
                    f"{js_path}: open-adhoc-modal handler must call "
                    "showModal() or getElementById('adhoc-modal')."
                )
                return
        # No handler found — that's a problem
        assert False, (
            "No JS handler found for data-action='open-adhoc-modal'. "
            "The button does nothing. Search both inline scripts and app/static/js/."
        )
