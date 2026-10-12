"""tests/_lib — extracted test machinery (conftest stays fixture-only).

Centralizes test infrastructure that was previously duplicated across many
test files. All helpers here are designed to be importable without side
effects (no DB, no network, no monkeypatching at import time).

Public API:
- tests._lib.auth: fresh_client, auth_required_client, assert_safe_response
- tests._lib.clock: FROZEN_NOW, FROZEN_TS, asuncion_now, utc_now, FrozenClock
- tests._lib.seed: quick_ingredient, quick_product, quick_sale, quick_supplier, quick_customer
- tests._lib.http: SAFE_CODES, AUTH_CODES, LOGIN_CODES, LOGIN_POST_CODES, etc
"""
