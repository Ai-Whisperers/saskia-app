"""Production-mode route check (isolated subprocess runner).

Used by tests/test_review_quick_wins.py to verify AIW_SASKIA_INTERNAL_ROUTES
gating without purging sys.modules in-process (which poisoned later tests).
Usage: python tests/_prod_mode_check.py /auditoria
"""

import sys

path = sys.argv[1]

import os

# The calling test controls AIW_SASKIA_INTERNAL_ROUTES precisely via the
# subprocess env — do NOT pop it here (default when absent: routes mounted).
os.environ.setdefault("SASKIA_TEST_AUTH_DISABLED", "1")

# PRO-SEC boot guard (app/rms/main.py) fires when SASKIA_TEST_AUTH_DISABLED
# is set OUTSIDE of pytest. The guard uses `sys.modules` to detect pytest,
# but we're a subprocess started by pytest, so sys.modules is fresh. Mark
# ourselves as under-test so the guard doesn't refuse to boot.
sys.modules.setdefault("pytest", __import__("importlib").import_module("pytest"))

from fastapi.testclient import TestClient

from app.rms.main import app

with TestClient(app, raise_server_exceptions=False) as c:
    print(c.get(path).status_code)
