"""P3.9 (T9): /clientes/{id}/editar dietary section shows live counts.

Operators can't tell at-a-glance how many restrictions or preferences
a customer has without counting checkboxes. Add count badges:
  - "Restricciones (3)" — 3 currently-checked
  - "Preferencias (5)" — 5 currently-rendered rows

Counts must reflect the server-rendered state (not just live JS), so
the operator sees the right number on page load.

Acceptance:
  - GET /clientes/{id}/editar returns 200.
  - The dietary restrictions label has a count badge matching the
    number of currently-checked restriction checkboxes.
  - The dietary preferences label has a count badge matching the
    number of currently-rendered preference rows.
"""

from __future__ import annotations

import re
import uuid

from tests.factories import make_customer


def test_cliente_editar_dietary_counts(client, session_factory):
    """P3.9: Restricciones/Preferencias labels include count badges."""
    s = session_factory()
    try:
        cust = make_customer(s, name=f"diet-count-{uuid.uuid4().hex[:6]}")
        # Pre-populate dietary profile with known restrictions + 1 preference.
        # dietary_restrictions is a comma-separated string in the model.
        from app.rms.models import Customer

        c: Customer = s.get(Customer, cust.id)
        c.dietary_restrictions = "gluten,lactosa"
        c.dietary_preferences = '[{"tag":"integral","rank":1,"note":""}]'
        s.commit()
        cid = cust.id
    finally:
        s.close()

    r = client.get(f"/clientes/{cid}/editar")
    assert r.status_code == 200
    body = r.text

    # Find the restrictions label and assert a (2) badge nearby.
    m = re.search(r"Restricciones\s*\((\d+)\)", body)
    assert m, "Restricciones label must include a count like 'Restricciones (N)'"
    n = int(m.group(1))
    assert n == 2, f"expected 2 restrictions; got {n}"

    # Preferences: count should be 1 (we persisted 1).
    m2 = re.search(r"Preferencias[^<]*?\((\d+)\)", body)
    assert m2, "Preferencias label must include a count badge"
    n2 = int(m2.group(1))
    assert n2 == 1, f"expected 1 preference; got {n2}"
