"""Production-mode route check (isolated subprocess runner).

Used by tests/test_review_quick_wins.py to verify AIW_SASKIA_INTERNAL_ROUTES
gating without purging sys.modules in-process (which poisoned later tests).
Usage: python tests/_prod_mode_check.py /auditoria
"""
import sys

path = sys.argv[1]

import os

os.environ.pop("AIW_SASKIA_INTERNAL_ROUTES", None)
os.environ.setdefault("SASKIA_TEST_AUTH_DISABLED", "1")

from fastapi.testclient import TestClient

from app.rms.main import app

with TestClient(app, raise_server_exceptions=False) as c:
    print(c.get(path).status_code)
