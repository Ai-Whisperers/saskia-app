"""P3.4: /clientes/{id}/editar inline JS must use inline errors, not alert().

Currently the inline JS uses native window.alert() to report validation
errors and fetch failures. Native alerts block the UI thread, don't
match the rest of the app's design, and don't survive CSS theme changes.

Fix: replace alert() with an inline error banner that's appended near
the form actions.

Acceptance:
  - GET /clientes/{id}/editar returns 200.
  - The page contains an element with id='js-error-banner' (the target
    for showInlineError).
  - The page does NOT call alert( in any inline <script> block.
"""
from __future__ import annotations

import re
import uuid

from tests.factories import make_customer


def test_cliente_editar_no_alert_calls(client, session_factory):
    """P3.4: inline JS uses an inline error banner, not alert()."""
    s = session_factory()
    try:
        cust = make_customer(s, name=f"no-alert-{uuid.uuid4().hex[:6]}")
        s.commit()
        cid = cust.id
    finally:
        s.close()

    r = client.get(f"/clientes/{cid}/editar")
    assert r.status_code == 200
    body = r.text

    # No alert() calls in inline <script> blocks. We strip comments
    # first so a doc-string that mentions alert() doesn't false-positive.
    # Naive but adequate for this template.
    import re as _re
    no_comments = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    # Also strip JS-style line comments before checking (best-effort).
    no_line_comments = re.sub(r"//[^\n]*", "", no_comments)
    alert_calls = re.findall(r'\balert\s*\(', no_line_comments)
    assert not alert_calls, (
        f"expected no alert() calls in inline JS; found {len(alert_calls)}: "
        f"the page should use an inline error banner instead."
    )

    # An element with id='js-error-banner' should exist (the showInlineError target).
    assert 'id="js-error-banner"' in body, (
        "expected an inline error banner element with id='js-error-banner'"
    )