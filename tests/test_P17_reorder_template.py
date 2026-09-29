"""tests/test_P17_reorder_template.py — regression test for /reorder template bug.

P-17: the "Reponer" form column in app/templates/reorder.html:130-155 was
structurally broken:

  - {{ ui.combo_field(...) }} started INSIDE an already-closed <input> tag
    (line 137 starts the macro inside the prior input's attribute list).
  - `value='{{ item.unit }}'` was passed as a Python string literal
    containing raw `{{ }}` syntax, which Jinja does not re-process inside
    an already-quoted argument.
  - The `<input name="price_gs">` was missing its `value=` attribute, with
    the attribute then appearing FLOATING outside the tag on line 147,
    so the rendered HTML contained literal `value="..."` and
    `aria-label="..."` text inside the form column.

Visible symptoms to users: literal `{{ item.unit }}`, literal
`value='4500'`, and a bare `aria-label="..."` chunk showing in the
restock column.

This test reproduces the broken render. It should FAIL before the fix
and PASS after.
"""
from __future__ import annotations

import uuid
from html.parser import HTMLParser

from sqlalchemy.orm import sessionmaker

from tests.factories import make_ingredient


def test_reorder_template_renders_valid_html(client, session_factory):
    """P-17: /reorder must render valid HTML with no Jinja leakage in the form."""
    unique = f"reorder-test-{uuid.uuid4().hex[:8]}"
    s = sessionmaker(bind=session_factory.kw["bind"])()
    try:
        # unit='kg' is one of the standard options; suggested_qty derived from
        # min_stock_qty - stock_qty. purchase_price_gs=4500 matches the
        # literal that was leaking in the screenshot.
        make_ingredient(
            s,
            name=unique,
            unit="kg",
            stock_qty=1.0,
            min_stock_qty=10.0,
            purchase_price_gs=4500,
        )
        s.commit()
    finally:
        s.close()

    r = client.get("/reorder")
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:500]}"

    body = r.text

    # --- No Jinja leakage (the user-visible symptom) -----------------
    # The broken template leaked raw `{{ item.unit }}` onto the page.
    assert "{{ item.unit }}" not in body, (
        f"raw {{ item.unit }} visible in rendered HTML:\n{body[:2000]}"
    )
    # No other raw Jinja delimiters should leak either.
    assert "{{" not in body, "raw {{ ... }} visible in rendered HTML"
    assert "{%" not in body, "raw {% ... %} visible in rendered HTML"

    # --- The price_gs input MUST have its value attribute INSIDE the tag ---
    # In the broken version, `value="4500"` was a text node sitting in the
    # form column, not an attribute of <input name="price_gs">.
    assert 'name="price_gs"' in body, "price_gs input missing from form"
    # Every <input> that has a value should have it as an attribute, not as
    # a floating text node. We expect value="..." to appear at least 5
    # times: ingredient_id (hidden), notes (hidden), qty, qty_unit
    # (combo), price_gs.
    assert body.count('value="') >= 5, (
        f"expected >=5 value=\" attrs in body (ingredient_id, notes, qty, "
        f"qty_unit, price_gs); got {body.count('value=\"')}\n"
        f"first 2KB of body:\n{body[:2000]}"
    )

    # --- Well-formedness check ---------------------------------------
    # html.parser is forgiving (it accepts broken markup silently), so we
    # can't use it to detect the orphan-attribute bug directly. But it
    # WILL choke if an attribute value contains an unescaped `"` mid-tag,
    # which is what happened when `value='{{ item.unit }}'` got rendered
    # literally as text. Use a strict parser that reports unbalanced tags
    # via the error callback.
    class StrictParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.errors: list[str] = []

        def error(self, message):
            self.errors.append(message)

    p = StrictParser()
    p.feed(body)
    # Don't fail on warnings — only on hard parse errors. The strict
    # parser doesn't raise on broken HTML, but if any `error()` calls
    # fire we want to know.
    assert not p.errors, f"HTML parser reported errors: {p.errors[:5]}"

    # --- The form must contain all the expected inputs by NAME --------
    for name in ("ingredient_id", "qty", "price_gs", "notes"):
        assert f'name="{name}"' in body, f"form is missing input name={name!r}"

    # --- The Reponer button must be there ----------------------------
    assert ">Reponer<" in body, "submit button 'Reponer' missing from form"
