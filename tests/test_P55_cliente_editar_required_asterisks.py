"""P6: cliente_editar form shows asterisks (*) on required labels.

Accessibility win for operators and the rare screen-reader user.
A 'required' field's <label> gets a <span class='required' aria-label='obligatorio'>*</span>
suffix. The asterisk is purely visual; aria-required='true' is on the input.

Acceptance:
  - The form's first required field ('name') has a <span class='required'>
    in its label.
  - At least one label uses a <span class='required'> child (or sibling).
"""
from __future__ import annotations

import uuid

from tests.factories import make_customer


def test_cliente_editar_required_label_asterisks(client, session_factory):
    """P6: required fields show an asterisk in the label."""
    s = session_factory()
    try:
        cust = make_customer(s, name=f"req-asterisk-{uuid.uuid4().hex[:6]}")
        s.commit()
        cid = cust.id
    finally:
        s.close()

    r = client.get(f"/clientes/{cid}/editar")
    assert r.status_code == 200
    body = r.text

    # There must be at least one .required span (for the 'name' field).
    assert 'class="required"' in body, (
        "expected <span class='required'> in at least one label"
    )
    # The name label should include the asterisk.
    # The label is `<label for="name">Nombre</label>` and the input
    # has aria-required="true" — so the visual <span> must be near it.
    name_label_idx = body.find('<label for="name">')
    assert name_label_idx > 0
    nearby = body[name_label_idx:name_label_idx + 200]
    assert "required" in nearby, (
        f"expected 'required' marker near the 'name' label; got: {nearby[:200]}"
    )
