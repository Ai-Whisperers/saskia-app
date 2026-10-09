"""tests/e2e/conftest.py — e2e-layer fixtures + marker wiring (C2).

The `e2e` marker is registered in pyproject (C5). This conftest exists so
the e2e package has an explicit import point for flows/factories and any
future e2e-only fixtures (role clients, seeded worlds).
"""
