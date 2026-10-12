"""tests/_lib — extracted test machinery (conftest stays fixture-only).

Centralizes test infrastructure that was previously duplicated across many
test files. All helpers here are designed to be importable without side
effects (no DB, no network, no monkeypatching at import time).

Public API:
- fresh_client() / fresh_client_with_auth() / fresh_client_auth_enabled()
- freeze_now() / asuncion_now()
- new_seed() / reseed()
- make_test_ingredient() / make_test_product() / make_test_sale() (lightweight)
"""
