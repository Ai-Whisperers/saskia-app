"""Parametrized audit-row smoke for CRUD write actions.

Phase 2 increment #2: demonstrates the parametrization pattern that should
be applied to the long test files identified in the audit (5 files >500
lines). This file FOLLOWS the existing test_p0_audit_log_coverage.py
contract — same URL, same form data, same audit-row assertions — but
parametrized to demonstrate dedup without changing behavior.

NOTE: This file is ADDITIVE. The originals in test_p0_audit_log_coverage.py
remain untouched. If this parametrize case set runs identically to the
originals, the originals can be deleted in a follow-up commit. Until
then, both files run; pytest collection deduplication is not automatic
so the audit-row assertions are duplicated for safety.

Each parametrize row defines:
- (id): short label
- (url_template): either a fixed URL or a `/.../{id_key}/...` template
- (seed_for_update): which _seed_basic key to bind into {id_key}
- (request_kwargs): dict passed to authed_client.post(**request_kwargs)
- (audit_action, target_type): the audit row to look up
- (extra_assertions): optional list of (path, expected) tuples over
  the AuditLog row's `.detail` dict. e.g. ("name", "Receta QA")

Conventions match the existing audit tests:
- r.status_code < 500 (any 4xx-redirect is OK)
- _audit_rows(...) returns >= 1 row
- last = rows[-1]
"""

from __future__ import annotations

import pytest

from tests.test_p0_audit_log_coverage import _audit_rows, _seed_basic

# ─── Parametrize rows ─────────────────────────────────────────────────────────
#
# Each row is a complete spec for one audit-row smoke case. Adding a new
# write action = one new dict entry, no new function.

_RECIPE_CREATE = {
    "url": "/recetas/nueva",
    "request_kwargs": lambda data: {
        "url": "/recetas/nueva",
        "data": {
            "name": "Receta Auditada QA",
            "yield_qty": "12",
            "yield_unit": "und",
            "line_kind": ["ingredient"],
            "line_target_id": [str(data["ingredient_id"])],
            "line_qty": ["0.3"],
            "line_unit": ["kg"],
        },
        "follow_redirects": False,
    },
    "audit_action": "write.recipe.create",
    "target_type": "recipe",
    "extra_detail": [("name", "Receta Auditada QA")],
    "needs_seed": True,
    "needs_id": False,
}

_RECIPE_UPDATE = {
    "url": "/recetas/{recipe_id}/editar",
    "request_kwargs": lambda data: {
        "url": f"/recetas/{data['recipe_id']}/editar",
        "data": {
            "name": "Brownie QA Actualizada",
            "yield_qty": "12",
            "yield_unit": "und",
            "line_kind": ["ingredient"],
            "line_target_id": [str(data["ingredient_id"])],
            "line_qty": ["0.5"],
            "line_unit": ["kg"],
        },
        "follow_redirects": False,
    },
    "audit_action": "write.recipe.update",
    "target_type": "recipe",
    "extra_detail": [("name", "Brownie QA Actualizada")],
    "target_id_match": "recipe_id",
    "needs_seed": True,
    "needs_id": True,
}

_PRODUCT_CREATE = {
    "url": "/productos/nuevo",
    "request_kwargs": lambda data: {
        "url": "/productos/nuevo",
        "data": {
            "name": "Producto Auditado QA",
            "sale_price_gs": "3500",
            "portion_label": "1 unidad",
        },
        "follow_redirects": False,
    },
    "audit_action": "write.product.create",
    "target_type": "product",
    "extra_detail": [("name", "Producto Auditado QA")],
    "needs_seed": False,
    "needs_id": False,
}

_PRODUCT_UPDATE = {
    "url": "/productos/{product_id}/editar",
    "request_kwargs": lambda data: {
        "url": f"/productos/{data['product_id']}/editar",
        "data": {
            "name": "Brownie Producto QA Actualizado",
            "sale_price_gs": "3000",
            "portion_label": "1 unidad",
        },
        "follow_redirects": False,
    },
    "audit_action": "write.product.update",
    "target_type": "product",
    "extra_detail": [("name", "Brownie Producto QA Actualizado")],
    "target_id_match": "product_id",
    "needs_seed": True,
    "needs_id": True,
}

_CUSTOMER_CREATE = {
    "url": "/clientes/api/create",
    "request_kwargs": lambda data: {
        "url": "/clientes/api/create",
        "json": {"name": "Cliente Audit QA", "phone": "0981114444"},
    },
    "audit_action": "write.customer.create",
    "target_type": "customer",
    "extra_detail": [("name", "Cliente Audit QA")],
    "needs_seed": False,
    "needs_id": False,
}

_CUSTOMER_UPDATE = {
    "url": "/clientes/{customer_id}/editar",
    "request_kwargs": lambda data: {
        "url": f"/clientes/{data['customer_id']}/editar",
        "data": {"name": "Cliente QA Editado", "phone": "0981115555"},
        "follow_redirects": False,
    },
    "audit_action": "write.customer.update",
    "target_type": "customer",
    "extra_detail": [],
    "target_id_match": "customer_id",
    "needs_seed": True,
    "needs_id": True,
}


_CASES = [
    pytest.param(_RECIPE_CREATE, id="recipe-create"),
    pytest.param(_RECIPE_UPDATE, id="recipe-update"),
    pytest.param(_PRODUCT_CREATE, id="product-create"),
    pytest.param(_PRODUCT_UPDATE, id="product-update"),
    pytest.param(_CUSTOMER_CREATE, id="customer-create"),
    pytest.param(_CUSTOMER_UPDATE, id="customer-update"),
]


# ─── Driver ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("spec", _CASES)
def test_write_action_emits_audit_row(authed_client, session_factory, spec):
    """One parametrized test runs all six CRUD audit cases.

    Mirrors the test_<entity>_<verb>_audited functions in
    test_p0_audit_log_coverage.py — same URL, same payload, same audit-row
    assertions. The intent is to prove the parametrize shape preserves
    behavior so the originals can be deleted in a follow-up commit.
    """
    data = _seed_basic(session_factory) if spec["needs_seed"] else {}

    req = spec["request_kwargs"](data)
    r = authed_client.post(**req)
    assert r.status_code < 500, f"{spec['url']} returned {r.status_code}: {r.text[:200]}"

    rows = _audit_rows(session_factory, spec["audit_action"], target_type=spec["target_type"])
    assert len(rows) >= 1, f"no {spec['audit_action']} audit row"
    last = rows[-1]

    for key, expected in spec["extra_detail"]:
        actual = last.detail.get(key)
        assert actual == expected, (
            f"{spec['audit_action']}: detail.{key}={actual!r}, expected {expected!r}"
        )

    if spec.get("target_id_match"):
        seed_key = spec["target_id_match"]
        assert str(last.target_id) == str(data[seed_key]), (
            f"{spec['audit_action']}: target_id={last.target_id}, expected {data[seed_key]}"
        )


# ─── Meta-tests ──────────────────────────────────────────────────────────────


def test_parametrize_row_count():
    """Document the number of audit cases covered by this file."""
    assert len(_CASES) == 6


def test_every_case_has_required_keys():
    """Each parametrize row must have the keys the driver reads."""
    required = {
        "url",
        "request_kwargs",
        "audit_action",
        "target_type",
        "extra_detail",
        "needs_seed",
        "needs_id",
    }
    for case in _CASES:
        spec = case.values[0]
        missing = required - set(spec.keys())
        assert not missing, f"{case.id} missing keys: {missing}"
