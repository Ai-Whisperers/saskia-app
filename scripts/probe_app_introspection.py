"""Probe the FastAPI app to confirm introspection works."""

import sys

# Trick main.py into thinking we're under pytest
sys.modules.setdefault("pytest", __import__("pytest"))

import os

os.environ.setdefault("SASKIA_TEST_AUTH_DISABLED", "1")

sys.path.insert(0, ".")

from app.rms.main import app

print(f"Routes: {len(app.routes)}")
for r in app.routes[:10]:
    if hasattr(r, "methods"):
        methods = ",".join(sorted(r.methods - {"HEAD"}))
        print(f"  {methods:12} {r.path}")
    else:
        print(f"  MOUNT        {r.path}")
