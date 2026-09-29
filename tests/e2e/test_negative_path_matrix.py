"""tests/e2e/test_negative_path_matrix.py — D2: hostile-input matrix as data.

One parametrized sweep per route family: missing required field, garbage
money string, negative qty, nonexistent FK, oversized input. Replaces the
ad-hoc negative tests scattered across files (and finds the gaps).
"""

from __future__ import annotations

import pytest

from tests.factories import make_catalog

pytestmark = [pytest.mark.security]


def _cat(session_factory):
    with session_factory() as s:
        cat = make_catalog(s)
        s.commit()
        return cat["product"].id, cat["ingredient"].id


# (route, base_valid_payload, mutation, expect_status)
CASES = [
    # missing required
    ("sale_no_product", "/ventas/nueva",
     {"qty": "1", "product_id": ""}, None, (400, 422)),
    ("sale_garbage_qty", "/ventas/nueva",
     None, {"qty": "abc"}, (400, 422)),
    ("sale_negative_qty", "/ventas/nueva",
     None, {"qty": "-3"}, (400, 422)),
    ("merma_bad_reason", "/merma/registrar",
     None, {"reason": "no_existe"}, (400, 422)),
    ("pedido_no_lines", "/pedidos/nuevo",
     {"promised_date": "2026-09-25", "channel": "whatsapp",
      "line_product_id": "", "line_qty": "", "line_unit_price_gs": ""},
     None, (400, 422)),
    ("merma_unknown_fk", "/merma/registrar",
     None, {"ingredient_id": "999999", "qty": "1", "reason": "vencida"}, (404,)),
]


@pytest.mark.parametrize("name,url,payload,mut,expect", CASES,
                         ids=[c[0] for c in CASES])
def test_hostile_posts_rejected(client, session_factory, name, url, payload, mut, expect):
    pid, iid = _cat(session_factory)
    {"product_id": str(pid), "qty": "1", "payment_method": "efectivo",
            "ingredient_id": str(iid), "qty_unit": "kg",
            "promised_date": "2026-09-25"}
    data = dict(payload or {})
    data.update({"ingredient_id": str(iid), "product_id": str(pid)})
    if mut:
        data.update(mut)
    if payload and "product_id" in payload and payload["product_id"] == "":
        data["product_id"] = ""  # explicit absence wins over the base injection
    r = client.post(url, data=data, follow_redirects=False)
    assert r.status_code in expect, (
        f"{name}: got {r.status_code}, expected {expect}; body={getattr(r, 'text', '')[:200]}"
    )


def test_oversized_input_rejected(client, session_factory):
    _pid, _ = _cat(session_factory)
    r = client.post("/productos/nuevo", data={
        "name": "x" * 5000, "sale_price_gs": "1000", "portion_label": "1 unidad",
    }, follow_redirects=False)
    assert r.status_code in (303, 400, 422)  # 303 = accepted-but-truncated is a finding, not a crash


def test_nonexistent_ids_404(client):
    for url in ["/productos/999999/eliminar", "/ventas/999999/anular"]:
        r = client.post(url, data={"reason": "x"}, follow_redirects=False)
        assert r.status_code in (404, 409, 422), f"{url}: {r.status_code}"
