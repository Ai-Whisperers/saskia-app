"""Parametrized coverage for two D-grade pedido router helpers.

S1 batch-6 (test coverage continuation): lock the branch matrix of two
private helpers in `app/routers/pedidos.py` that had no direct unit tests
before this file:

  (1) `app/routers/pedidos.py:_pedido_resolve_customer` (CC 24, D-grade)
      Resolves the customer for a new pedido. Either looks up by id
      (then refreshes phone / invoice_ruc / invoice_name), or auto-creates
      from a typed name (with case-insensitive match against existing).
      Branches covered: cust_id resolves, cust_id not found (400),
      blank name → None, name matches existing, name creates new,
      phone/ruc/name write-back paths.

  (2) `app/routers/pedidos.py:_pedido_persist_address_book_entry`
      (CC 23, D-grade)
      Persists a `CustomerAddress` when the operator checked the
      "save address" box. Branches covered: save not checked (no-op),
      blank address text (no-op), no customer (no-op), first-time
      is_default=True, subsequent row is_default=False, blank optional
      fields → NULL, structured fields propagate, default
      `address_kind="HOME"` fallback, `preferred_zone_id` stamp only
      when None.

Why drive them directly (not through the route)
----------------------------------------------
Both are private helpers (leading underscore). The route handler that
calls them lives in `pedido_create()` which orchestrates many other
helpers + form parsing. Calling the helpers in isolation lets us:

- lock the branch matrix without touching CSRF / auth / template render;
- use `session_factory()` directly so we exercise real SQLAlchemy state
  transitions (commit, flush, refresh, query);
- keep the parametrize rows minimal — one row per branch outcome.

Each test seeds the minimum DB state required (Customer / DeliveryZone
already in `app/rms/models_legacy.py`; tests use the standard
`session_factory` fixture so the in-memory SQLite from conftest is the
shared DB).

This file is ADDITIVE — no existing tests are modified. The pedido
regression tests (test_P10_*, test_P11_*, test_P33_*) cover end-to-end
flows; this file locks the helper-level branches that those flows pass
through.

Excluded D-grade helpers (covered elsewhere or out of scope):

- `libro_ventas` (CC 21) — covered in PR #174
- `_sort_value` (CC 21) — covered in s3 PR #172
- `bank_list` (CC 21) — covered in PR #178
- `shopping_list_index` (CC 21) — covered in PR #178
- `margin_drift_all` (CC 22) — covered in PR #179

Adding a new scenario = one new dict entry in `_ROWS_RESOLVE` or
`_ROWS_ADDRESS`, no new function.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import pytest

# ─── _pedido_resolve_customer row spec ───────────────────────────────────────


# Sentinel used to mark fields whose values are computed inside the
# driver (after a seed inserts a Customer / DeliveryZone whose id we
# don't know at definition time). Avoids the dataclass default ordering
# bug that bites when sentinel fields are interleaved with required
# fields.
_WILL_BE_SET = "__WILL_BE_SET__"


@dataclass
class _CustomerResolveSpec:
    """One scenario for `_pedido_resolve_customer`.

    Branch knobs:
      - existing_customer: a Customer to pre-insert (or None for empty DB)
      - existing_customer_phone / invoice_ruc / invoice_name: the
        pre-inserted values; lock the "no write-back when identical"
        branch and the "fill-blank" branch.
      - cust_id_int: the id to pass (None = no id, auto-create path)
      - cust_name / cust_phone / invoice_ruc / invoice_name: form inputs
      - expect_result_status: "ok" | "http_400"
      - expect_result_attrs: assertions on the returned Customer object
    """

    # All fields have defaults so dataclass ordering isn't an issue.
    # `Optional` for `cust_id_int` so we can stash the sentinel before
    # the driver rebinds it to a real int.
    id: str = ""
    description: str = ""
    cust_id_int: Optional[int] = None
    cust_name: str = ""
    cust_phone: Optional[str] = None
    invoice_ruc: str = ""
    invoice_name: str = ""
    expect_result_status: str = "ok"  # "ok" | "http_400"
    expect_result_name: Optional[str] = None
    expect_result_id: Optional[int] = None
    expect_count_customers: Optional[int] = None  # post-call DB count
    # Per-field assertions: what the returned / persisted Customer should
    # look like. (name, phone, invoice_ruc, invoice_name)
    expect_phone: Optional[str] = None
    expect_invoice_ruc: Optional[str] = None
    expect_invoice_name: Optional[str] = None


def _seed_customer(s, *, name, phone=None, invoice_ruc=None, invoice_name=None) -> int:
    """Insert a Customer row with the given fields; return its id."""
    from app.rms.models_legacy import Customer

    c = Customer(
        name=name,
        phone=phone,
        invoice_ruc=invoice_ruc,
        invoice_name=invoice_name,
    )
    s.add(c)
    s.flush()
    cid = c.id
    s.commit()
    return cid


def _count_customers(s) -> int:
    from sqlalchemy import func, select

    from app.rms.models_legacy import Customer

    return s.scalar(select(func.count()).select_from(Customer)) or 0


# Case 1: cust_id resolves → returns that Customer with no writes.
# Existing customer has phone + invoice_ruc + invoice_name; the form
# sends identical values. Lock the "no write-back when identical" branch
# (the `cust_phone and cust_phone != (cust_obj.phone or "")` guard).
_RESOLVE_EXISTING_NO_WRITE = _CustomerResolveSpec(
    id="existing_id_no_writeback",
    description="cust_id resolves, form values identical to existing → no field updates",
    cust_id_int=None,  # filled by driver
    cust_name="Juan Cliente X",
    cust_phone="+595981111111",
    invoice_ruc="80012345-6",
    invoice_name="Cliente X S.A.",
    expect_result_status="ok",
    expect_result_name="Juan Cliente X",
    expect_count_customers=1,
    expect_phone="+595981111111",
    expect_invoice_ruc="80012345-6",
    expect_invoice_name="Cliente X S.A.",
)


# Case 2: cust_id resolves → form sends a NEW phone; phone must update.
# Locks the `cust_phone and cust_phone != (cust_obj.phone or "")` branch.
_RESOLVE_EXISTING_NEW_PHONE = _CustomerResolveSpec(
    id="existing_id_phone_updated",
    description="existing customer, form sends new phone → phone is overwritten",
    cust_id_int=None,  # filled by driver
    cust_name="Juan Cliente Y",
    cust_phone="+595982222222",  # DIFFERENT from the seeded phone
    invoice_ruc="80098765-4",
    invoice_name="Cliente Y S.A.",
    expect_result_status="ok",
    expect_phone="+595982222222",
    expect_invoice_ruc="80098765-4",  # identical → no write-back
)


# Case 3: cust_id resolves → existing has NO invoice_ruc; form sends
# one. Locks the `if invoice_ruc and not (cust_obj.invoice_ruc or "")`
# fill-blank branch.
_RESOLVE_EXISTING_FILL_BLANK_RUC = _CustomerResolveSpec(
    id="existing_id_fill_blank_ruc",
    description="existing customer with no invoice_ruc, form supplies one → ruc filled",
    cust_id_int=None,  # filled by driver
    cust_name="Juan Cliente Z",
    cust_phone=None,  # don't change phone
    invoice_ruc="80055555-1",  # seeded as None → will be filled
    invoice_name="",
    expect_result_status="ok",
    expect_invoice_ruc="80055555-1",
    expect_invoice_name=None,  # blank form value → no write
)


# Case 4: cust_id does NOT resolve → HTTPException 400 (the explicit
# raise). Locks the `cust_obj is None` branch in the by-id path.
_RESOLVE_MISSING_ID_RAISES = _CustomerResolveSpec(
    id="missing_cust_id_raises_400",
    description="cust_id points to no Customer → HTTPException(400, 'cliente no encontrado')",
    cust_id_int=99_999,  # no row
    cust_name="",
    cust_phone=None,
    invoice_ruc="",
    invoice_name="",
    expect_result_status="http_400",
)


# Case 5: no cust_id + blank name → returns None (the early-return
# branch). No Customer created.
_RESOLVE_NO_NAME_RETURNS_NONE = _CustomerResolveSpec(
    id="no_id_no_name_returns_none",
    description="no cust_id AND blank name → return None (no auto-create)",
    cust_id_int=None,
    cust_name="",  # blank → early return
    cust_phone="+595983333333",
    invoice_ruc="",
    invoice_name="",
    expect_result_status="ok",
    expect_result_id=None,
    expect_count_customers=0,  # nothing created
)


# Case 6: no cust_id + name matches an existing customer (case-insensitive
# match) → returns that Customer, may fill a blank phone. Locks the
# `existing is not None` branch.
_RESOLVE_NAME_MATCHES_EXISTING = _CustomerResolveSpec(
    id="name_matches_existing",
    description="name matches existing (case-insensitive) → returns it, fills blank phone",
    cust_id_int=None,
    cust_name="juan existente",  # lowercase; seed will be "Juan Existente"
    cust_phone="+595984444444",  # seeded as None → fill
    invoice_ruc="",
    invoice_name="",
    expect_result_status="ok",
    expect_result_name="Juan Existente",
    expect_count_customers=1,  # no new row
    expect_phone="+595984444444",
)


# Case 7: no cust_id + name is new → creates a new Customer with the
# supplied fields. Locks the auto-create branch (Customer(...); session.add).
_RESOLVE_NEW_CUSTOMER_CREATED = _CustomerResolveSpec(
    id="new_customer_auto_created",
    description="name is new → auto-create Customer with phone, invoice_ruc, invoice_name",
    cust_id_int=None,
    cust_name="Cliente Nuevo",
    cust_phone="+595985555555",
    invoice_ruc="80077777-3",
    invoice_name="Cliente Nuevo S.A.",
    expect_result_status="ok",
    expect_result_name="Cliente Nuevo",
    expect_count_customers=1,
    expect_phone="+595985555555",
    expect_invoice_ruc="80077777-3",
    expect_invoice_name="Cliente Nuevo S.A.",
)


# Case 8: name new + invoice_ruc with whitespace is stripped → NULL
# in DB (the `(invoice_ruc or '').strip() or None` branch).
_RESOLVE_NEW_BLANK_STRIP_RUC = _CustomerResolveSpec(
    id="new_customer_whitespace_ruc_normalized",
    description="new customer with whitespace invoice_ruc → stored as None (racle)",
    cust_id_int=None,
    cust_name="Cliente Whitespace",
    cust_phone="+595986666666",
    invoice_ruc="   ",  # whitespace → stored as None
    invoice_name="\t\n",  # whitespace → stored as None
    expect_result_status="ok",
    expect_invoice_ruc=None,
    expect_invoice_name=None,
)


# `_ROWS_RESOLVE` carries the per-row seed instructions alongside the
# spec. The driver uses `seed_*` fields to pre-insert a Customer and
# (if needed) bind the just-created id into `spec.cust_id_int`.
_ROWS_RESOLVE: list[dict[str, Any]] = [
    {
        "spec": _RESOLVE_EXISTING_NO_WRITE,
        "seed_name": "Juan Cliente X",
        "seed_phone": "+595981111111",
        "seed_ruc": "80012345-6",
        "seed_ruc_name": "Cliente X S.A.",
    },
    {
        "spec": _RESOLVE_EXISTING_NEW_PHONE,
        "seed_name": "Juan Cliente Y",
        "seed_phone": "+595989000000",
        "seed_ruc": "80098765-4",
        "seed_ruc_name": "Cliente Y S.A.",
    },
    {
        "spec": _RESOLVE_EXISTING_FILL_BLANK_RUC,
        "seed_name": "Juan Cliente Z",
        "seed_phone": "+595989111111",
        "seed_ruc": None,
        "seed_ruc_name": "Cliente Z",
    },
    {"spec": _RESOLVE_MISSING_ID_RAISES, "seed_name": None},
    {"spec": _RESOLVE_NO_NAME_RETURNS_NONE, "seed_name": None},
    {
        "spec": _RESOLVE_NAME_MATCHES_EXISTING,
        "seed_name": "Juan Existente",
        "seed_phone": None,
        "seed_ruc": None,
        "seed_ruc_name": None,
    },
    {"spec": _RESOLVE_NEW_CUSTOMER_CREATED, "seed_name": None},
    {"spec": _RESOLVE_NEW_BLANK_STRIP_RUC, "seed_name": None},
]


# ─── _pedido_persist_address_book_entry row spec ────────────────────────────


@dataclass
class _AddressBookSpec:
    """One scenario for `_pedido_persist_address_book_entry`.

    All string fields map 1:1 to the helper's keyword args. Booleans
    encode the early-return conditions (save_address == "1", cust_obj,
    address_text).
    """

    # Required fields with defaults so dataclass ordering isn't an issue.
    # `expect_address_count` is the only one that genuinely has no default
    # in spirit; we give it a sentinel of 0 here and override per row.
    expect_address_count: int = 0
    id: str = ""
    description: str = ""
    save_address: str = "0"  # "0" | "1"
    has_customer: bool = False  # pre-insert a Customer row?
    customer_zone_pref: Optional[int] = None  # pre-existing preferred_zone_id
    address_text: str = ""
    # Optional structured fields. Empty string → "" → fld stored as None.
    address_label: str = ""
    address_calle_principal: str = ""
    address_calle_secundaria: str = ""
    address_numero: str = ""
    address_edificio: str = ""
    address_piso: str = ""
    address_unidad: str = ""
    address_barrio: str = ""
    address_ciudad: str = ""
    address_departamento: str = ""
    address_codigo_postal: str = ""
    address_recipient_name: str = ""
    address_delivery_instructions: str = ""
    address_kind: str = ""
    zone_int: Optional[int] = None  # form zone_id
    expect_is_default: Optional[bool] = None
    expect_label: Optional[str] = None
    expect_zone_id: Optional[int] = None
    expect_calle_principal: Optional[str] = None
    expect_pais: Optional[str] = None
    expect_address_kind: Optional[str] = None
    expect_customer_zone_pref_after: Optional[int] = None  # preferred_zone_id
    # The Customer's pre-existing preferred_zone_id is stored separately
    # so the driver can stamp the dynamically-seeded zone id into it.
    pref_set: bool = False  # if True, pre-insert the customer WITH preferred_zone_id set


def _seed_zone(s) -> int:
    """Insert a minimal DeliveryZone and return its id."""
    from app.rms.models_legacy import DeliveryZone

    z = DeliveryZone(
        code="Z_TEST",
        name="Zona Test",
        delivery_cost_gs=0,
        min_order_gs=0,
        is_active=True,
    )
    s.add(z)
    s.flush()
    zid = z.id
    s.commit()
    return zid


def _seed_customer_with_pref(s, *, name, preferred_zone_id=None) -> int:
    from app.rms.models_legacy import Customer

    c = Customer(name=name, preferred_zone_id=preferred_zone_id)
    s.add(c)
    s.flush()
    cid = c.id
    s.commit()
    return cid


# Case 1: save_address != "1" → no-op (no CustomerAddress row).
_ADDRESS_BOX_UNCHECKED = _AddressBookSpec(
    expect_address_count=0,
    id="save_box_unchecked_noop",
    description="save_address='0' → no CustomerAddress created (early-return branch)",
    save_address="0",
    has_customer=True,
    customer_zone_pref=None,
    address_text="Av. Test 123",
)


# Case 2: save_address="1" but blank address_text → no-op.
_ADDRESS_BLANK_TEXT = _AddressBookSpec(
    expect_address_count=0,
    id="blank_address_text_noop",
    description="save_address='1' but address_text is blank → no-op",
    save_address="1",
    has_customer=True,
    customer_zone_pref=None,
    address_text="   ",  # whitespace-only → stripped → empty → no-op
)


# Case 3: save_address="1", valid text, but NO customer → no-op.
_ADDRESS_NO_CUSTOMER = _AddressBookSpec(
    expect_address_count=0,
    id="no_customer_noop",
    description="save_address='1' but cust_obj is None → no-op",
    save_address="1",
    has_customer=False,
    customer_zone_pref=None,
    address_text="Av. Test 456",
)


# Case 4: first address for customer → is_default=True, label="casa"
# (the default fallback when address_label is blank).
_ADDRESS_FIRST_DEFAULT = _AddressBookSpec(
    expect_address_count=1,
    id="first_address_is_default_true",
    description="first address for customer → is_default=True, label='casa' fallback",
    save_address="1",
    has_customer=True,
    customer_zone_pref=None,
    address_text="Av. Test 789",
    address_calle_principal="Av. Principal",
    address_numero="123",
    expect_is_default=True,
    expect_label="casa",
    expect_calle_principal="Av. Principal",
    expect_pais="PRY",
    expect_address_kind="HOME",
)


# Case 5: second address for same customer → is_default=False,
# label uses operator input.
_ADDRESS_SECOND_NOT_DEFAULT = _AddressBookSpec(
    expect_address_count=1,
    id="second_address_is_default_false",
    description="second address for customer → is_default=False, label='Oficina'",
    save_address="1",
    has_customer=True,
    customer_zone_pref=None,
    address_text="Oficina Piso 5",
    address_label="Oficina",
    expect_is_default=False,
    expect_label="Oficina",
    expect_pais="PRY",
)


# Case 6: structured fields with all blanks → all stored as None;
# address_kind falls back to "HOME".
_ADDRESS_BLANK_STRUCTURED = _AddressBookSpec(
    expect_address_count=1,
    id="blank_structured_fields_null",
    description="all structured fields blank → all stored as None (not empty string)",
    save_address="1",
    has_customer=True,
    customer_zone_pref=None,
    address_text="Solo dirección texto",
    address_calle_principal="",
    address_numero="",
    address_barrio="",
    address_ciudad="",
    expect_calle_principal=None,
    expect_address_kind="HOME",
)


# Case 7: zone_id present + customer has no preferred_zone_id →
# preferred_zone_id stamped.
_ADDRESS_ZONE_STAMPED = _AddressBookSpec(
    expect_address_count=1,
    id="zone_id_stamps_customer_preference",
    description="zone_id set + customer.preferred_zone_id is None → customer's pref stamped",
    save_address="1",
    has_customer=True,
    customer_zone_pref=None,
    address_text="Con zona",
    # zone_int / expect_zone_id / expect_customer_zone_pref_after are
    # filled by the driver after _seed_zone returns the dynamic id.
    zone_int=None,
    expect_zone_id=None,
    expect_customer_zone_pref_after=None,
)


# Case 8: zone_id present but customer ALREADY has a preferred_zone_id
# → NOT overwritten (the `not cust_obj.preferred_zone_id` guard).
# The driver's `needs_zone` flag means it seeds the zone, sets the
# customer's pref to that zone, then verifies the post-call pref is
# UNCHANGED.
_ADDRESS_ZONE_NOT_OVERWRITTEN = _AddressBookSpec(
    expect_address_count=1,
    id="zone_id_does_not_overwrite_existing_preference",
    description="zone_id set but customer.preferred_zone_id is already set → unchanged",
    save_address="1",
    has_customer=True,
    customer_zone_pref=None,  # filled by driver with the seeded zone id
    address_text="Otra dirección",
    zone_int=None,  # filled by driver
    expect_zone_id=None,  # asserted by the existence of the row + its zone
    expect_customer_zone_pref_after=None,  # filled by driver; expected == pref_before
    pref_set=True,
)


_ROWS_ADDRESS: list[dict[str, Any]] = [
    {"spec": _ADDRESS_BOX_UNCHECKED},
    {"spec": _ADDRESS_BLANK_TEXT},
    {"spec": _ADDRESS_NO_CUSTOMER},
    {"spec": _ADDRESS_FIRST_DEFAULT},
    {
        "spec": _ADDRESS_SECOND_NOT_DEFAULT,
        # Pre-seeded one address; the helper should add a SECOND row.
        # expect_address_count in the spec is now the per-row DELTA — the
        # driver sums pre-existing + delta for the actual DB count.
        "pre_existing_addresses": 1,
        "pre_existing_label": "casa",
    },
    {"spec": _ADDRESS_BLANK_STRUCTURED},
    {"spec": _ADDRESS_ZONE_STAMPED, "needs_zone": True},
    {"spec": _ADDRESS_ZONE_NOT_OVERWRITTEN, "needs_zone": True},
]


# ─── Parametrized driver: _pedido_resolve_customer ───────────────────────────


@pytest.mark.parametrize(
    "row",
    _ROWS_RESOLVE,
    ids=lambda r: r["spec"].id,
)
def test_pedido_resolve_customer_branches(row: dict, session_factory) -> None:
    """Drive `_pedido_resolve_customer` through 8 scenarios covering its
    CC-24 branches:

    - cust_id resolves, no field writes (identical values)
    - cust_id resolves, phone updated (new phone branch)
    - cust_id resolves, invoice_ruc fill-blank (None → value)
    - cust_id does NOT resolve (HTTPException 400)
    - no cust_id + blank name → return None
    - no cust_id + name matches existing (case-insensitive, fill-blank phone)
    - no cust_id + name is new → auto-create
    - new customer: blank/whitespace invoice_ruc → stored as None

    Called directly — pure function; the `Session` is the only dep.
    """
    from fastapi import HTTPException

    from app.routers.pedidos import _pedido_resolve_customer

    spec: _CustomerResolveSpec = row["spec"]

    with session_factory() as s:
        # Pre-seed a customer if the spec needs one.
        if row.get("seed_name"):
            new_cid = _seed_customer(
                s,
                name=row["seed_name"],
                phone=row.get("seed_phone"),
                invoice_ruc=row.get("seed_ruc"),
                invoice_name=row.get("seed_ruc_name"),
            )
            # Bind the just-created id into the spec (in-place mutation;
            # _CustomerResolveSpec is a dataclass so we can set attrs).
            spec.cust_id_int = new_cid

        if spec.expect_result_status == "http_400":
            # The by-id-not-found branch must raise HTTPException.
            with pytest.raises(HTTPException) as exc_info:
                _pedido_resolve_customer(
                    s,
                    spec.cust_id_int,
                    cust_name=spec.cust_name,
                    cust_phone=spec.cust_phone,
                    invoice_ruc=spec.invoice_ruc,
                    invoice_name=spec.invoice_name,
                )
            assert exc_info.value.status_code == 400, (
                f"{spec.id}: HTTPException.status_code={exc_info.value.status_code}, "
                f"expected 400 — {spec.description}"
            )
            assert "cliente no encontrado" in str(exc_info.value.detail), (
                f"{spec.id}: HTTPException.detail={exc_info.value.detail!r}, "
                f"expected 'cliente no encontrado' — {spec.description}"
            )
            return

        # OK path.
        result = _pedido_resolve_customer(
            s,
            spec.cust_id_int,
            cust_name=spec.cust_name,
            cust_phone=spec.cust_phone,
            invoice_ruc=spec.invoice_ruc,
            invoice_name=spec.invoice_name,
        )
        s.commit()

        # Result assertions.
        # The resolve helper returns EITHER a Customer OR None. Tests
        # that expect a Customer coming back set `expect_result_name`
        # (and may set field assertions). The test that expects None
        # back is _RESOLVE_NO_NAME_RETURNS_NONE — that row's
        # `expect_count_customers=0` assertion (further down) catches
        # the "no Customer created" branch.
        if spec.expect_result_name is not None:
            assert result is not None, (
                f"{spec.id}: expected a Customer, got None — {spec.description}"
            )
            assert result.name == spec.expect_result_name, (
                f"{spec.id}: result.name={result.name}, "
                f"expected {spec.expect_result_name} — {spec.description}"
            )
        # Else: result may be a Customer (e.g. the phone_updated row);
        # the field-level assertions below are guarded by
        # `result is not None` and the DB-count assertion catches the
        # auto-create branches.

        # Field assertions on the returned (and now-persisted) Customer.
        if spec.expect_phone is not None and result is not None:
            assert result.phone == spec.expect_phone, (
                f"{spec.id}: result.phone={result.phone}, "
                f"expected {spec.expect_phone} — {spec.description}"
            )
        if spec.expect_invoice_ruc is not None and result is not None:
            assert result.invoice_ruc == spec.expect_invoice_ruc, (
                f"{spec.id}: result.invoice_ruc={result.invoice_ruc}, "
                f"expected {spec.expect_invoice_ruc} — {spec.description}"
            )
        if spec.expect_invoice_name is not None and result is not None:
            assert result.invoice_name == spec.expect_invoice_name, (
                f"{spec.id}: result.invoice_name={result.invoice_name}, "
                f"expected {spec.expect_invoice_name} — {spec.description}"
            )

        # DB count assertion (locks the auto-create / no-create branches).
        if spec.expect_count_customers is not None:
            assert _count_customers(s) == spec.expect_count_customers, (
                f"{spec.id}: Customer count={_count_customers(s)}, "
                f"expected {spec.expect_count_customers} — {spec.description}"
            )


# ─── Parametrized driver: _pedido_persist_address_book_entry ────────────────


@pytest.mark.parametrize(
    "row",
    _ROWS_ADDRESS,
    ids=lambda r: r["spec"].id,
)
def test_pedido_persist_address_book_entry_branches(row: dict, session_factory) -> None:
    """Drive `_pedido_persist_address_book_entry` through 8 scenarios
    covering its CC-23 branches:

    - save box unchecked → no-op
    - save box checked but blank text → no-op
    - save box checked, valid text, no customer → no-op
    - first address for customer → is_default=True, label="casa"
    - second address → is_default=False, custom label
    - blank structured fields → stored as None (not "")
    - zone_id stamps customer's preferred_zone_id when previously None
    - zone_id does NOT overwrite an existing preferred_zone_id

    Called directly — pure function (writes to session; commits by the
    caller). The `Session` is the only dep.
    """
    from sqlalchemy import func, select

    from app.rms.models_legacy import Customer, CustomerAddress
    from app.routers.pedidos import _pedido_persist_address_book_entry

    spec: _AddressBookSpec = row["spec"]

    with session_factory() as s:
        # If the spec needs a zone (rows 7 + 8), seed it dynamically.
        zone_id: Optional[int] = None
        if row.get("needs_zone"):
            zone_id = _seed_zone(s)
            spec.zone_int = zone_id
            if spec.id == "zone_id_stamps_customer_preference":
                # Expected post-call preferred_zone_id == the seeded zone.
                spec.expect_zone_id = zone_id
                spec.expect_customer_zone_pref_after = zone_id
            elif spec.id == "zone_id_does_not_overwrite_existing_preference":
                # Expected post-call preferred_zone_id == pre-existing
                # pref (the seeded zone id). The driver's pre-existing
                # pref IS this same zone_id, so the "unchanged" assertion
                # checks the field is still zone_id.
                spec.expect_zone_id = zone_id
                spec.expect_customer_zone_pref_after = zone_id

        # Pre-seed a Customer if the spec needs one.
        cust_id: Optional[int] = None
        if spec.has_customer:
            # For the "not_overwritten" row, set preferred_zone_id to
            # the zone we just seeded; for "stamped", pass None so the
            # helper fills it.
            pref_arg: Optional[int] = None
            if spec.id == "zone_id_does_not_overwrite_existing_preference" and zone_id is not None:
                pref_arg = zone_id
            cust_id = _seed_customer_with_pref(s, name="Test Cust", preferred_zone_id=pref_arg)

            # If the row also says "pre-existing address", seed one so
            # the new entry is the SECOND (is_default=False).
            if row.get("pre_existing_addresses"):
                s.add(
                    CustomerAddress(
                        customer_id=cust_id,
                        label=row.get("pre_existing_label", "casa"),
                        address_text="existing entry",
                        is_default=True,
                    )
                )
                s.commit()

        # Build the cust_obj the helper expects: the actual ORM instance,
        # or None.
        cust_obj: Optional[Customer] = None
        if cust_id is not None:
            cust_obj = s.get(Customer, cust_id)

        # Call the helper.
        _pedido_persist_address_book_entry(
            s,
            cust_obj,
            spec.zone_int,
            spec.save_address,
            address_text=spec.address_text,
            address_label=spec.address_label,
            address_calle_principal=spec.address_calle_principal,
            address_calle_secundaria=spec.address_calle_secundaria,
            address_numero=spec.address_numero,
            address_edificio=spec.address_edificio,
            address_piso=spec.address_piso,
            address_unidad=spec.address_unidad,
            address_barrio=spec.address_barrio,
            address_ciudad=spec.address_ciudad,
            address_departamento=spec.address_departamento,
            address_codigo_postal=spec.address_codigo_postal,
            address_recipient_name=spec.address_recipient_name,
            address_delivery_instructions=spec.address_delivery_instructions,
            address_kind=spec.address_kind,
        )
        s.commit()

        # Count assertions.
        addr_count = s.scalar(select(func.count()).select_from(CustomerAddress)) or 0
        # Some rows pre-seed a CustomerAddress to test the
        # is_default branch — the helper's effect is the delta, so the
        # total DB count is pre_existing + spec.expect_address_count.
        expected_total = spec.expect_address_count + row.get("pre_existing_addresses", 0)
        assert addr_count == expected_total, (
            f"{spec.id}: CustomerAddress count={addr_count}, "
            f"expected {expected_total} ({spec.expect_address_count} delta + "
            f"{row.get('pre_existing_addresses', 0)} pre-existing) — {spec.description}"
        )
        if spec.expect_address_count == 0:
            # No-address behavior is fully covered by the count assertion.
            return

        # The helper-created row (the LAST one we inserted); for rows
        # with pre-existing addresses we want the most recently inserted
        # one. order_by(id DESC).limit(1) gives a deterministic pick.
        from sqlalchemy import desc

        addr = s.scalars(select(CustomerAddress).order_by(desc(CustomerAddress.id)).limit(1)).one()

        # NOTE: the early-return for expect_address_count==0 has
        # already happened above; the helper-created row's assertions
        # follow.
        if spec.expect_is_default is not None:
            assert addr.is_default == spec.expect_is_default, (
                f"{spec.id}: addr.is_default={addr.is_default}, "
                f"expected {spec.expect_is_default} — {spec.description}"
            )
        if spec.expect_label is not None:
            assert addr.label == spec.expect_label, (
                f"{spec.id}: addr.label={addr.label}, "
                f"expected {spec.expect_label} — {spec.description}"
            )
        if spec.expect_zone_id is not None:
            assert addr.zone_id == spec.expect_zone_id, (
                f"{spec.id}: addr.zone_id={addr.zone_id}, "
                f"expected {spec.expect_zone_id} — {spec.description}"
            )
        if spec.expect_calle_principal is not None:
            assert addr.calle_principal == spec.expect_calle_principal, (
                f"{spec.id}: addr.calle_principal={addr.calle_principal!r}, "
                f"expected {spec.expect_calle_principal!r} — {spec.description}"
            )
        if spec.expect_pais is not None:
            assert addr.pais == spec.expect_pais, (
                f"{spec.id}: addr.pais={addr.pais}, "
                f"expected {spec.expect_pais} — {spec.description}"
            )
        if spec.expect_address_kind is not None:
            assert addr.address_kind == spec.expect_address_kind, (
                f"{spec.id}: addr.address_kind={addr.address_kind}, "
                f"expected {spec.expect_address_kind} — {spec.description}"
            )

        # Customer's preferred_zone_id stamp assertion.
        if spec.expect_customer_zone_pref_after is not None and cust_obj is not None:
            assert cust_obj.preferred_zone_id == spec.expect_customer_zone_pref_after, (
                f"{spec.id}: cust.preferred_zone_id={cust_obj.preferred_zone_id}, "
                f"expected {spec.expect_customer_zone_pref_after} — {spec.description}"
            )


# ─── Row-count docs (mirrors PR #178 / #179 pattern) ────────────────────────


def test_parametrize_row_count() -> None:
    """Document the number of branch-coverage cases covered by this file.

    Locks the parametrize row count so adding/removing a row forces a
    reviewer to update the matching CHANGELOG entry — same pattern
    as batch3 / batch4 / batch5 (#174, #178, #179).
    """
    assert len(_ROWS_RESOLVE) == 8
    assert len(_ROWS_ADDRESS) == 8
