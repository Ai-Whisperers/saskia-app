"""P3.1: /clientes/{id}/editar must re-render the form with form values preserved
when server-side validation fails (e.g., empty name, invalid birthday).

Currently the route raises HTTPException(400), which shows FastAPI's
default error page and loses all user input. The form should re-render
with the typed values intact and a visible error message.

Acceptance:
  - GET /clientes/{id}/editar returns 200 (no error).
  - POST /clientes/{id}/editar with empty name returns 200 (NOT 400),
    re-renders the form, preserves the user's typed values, and shows
    a visible error message.
"""

from __future__ import annotations

import uuid

from tests.factories import make_customer


def test_cliente_editar_re_renders_on_validation_error(client, session_factory):
    """P3.1: empty name on submit re-renders form with preserved values."""
    s = session_factory()
    try:
        cust = make_customer(s, name=f"original-{uuid.uuid4().hex[:6]}")
        s.commit()
        cid = cust.id
    finally:
        s.close()

    # Submit with empty name and a valid phone/email/cedula/birthday.
    r = client.post(
        f"/clientes/{cid}/editar",
        data={
            "name": "",
            "phone": "+595 991 555 555",
            "email": "test@example.com",
            "cedula": "1234567",
            "notes": "test note",
            "csrf_token": "test",
        },
        follow_redirects=False,
    )
    # Must NOT be 400/422 — should re-render the form.
    assert r.status_code == 200, (
        f"expected 200 (re-render) but got {r.status_code}; "
        f"server-side validation should re-render the form, not raise."
    )
    body = r.text
    # The user's typed phone/email/notes must be preserved.
    assert "+595 991 555 555" in body or "595 991 555 555" in body, (
        "expected the typed phone to be preserved in the re-rendered form"
    )
    assert "test note" in body, "expected the typed notes to be preserved"
    # A visible error about name being required.
    assert "nombre" in body.lower() and (
        "obligatorio" in body.lower() or "required" in body.lower()
    ), "expected an error message about nombre being required"
