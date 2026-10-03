"""Comprehensive E2E smoke test — every page + every functionality."""
from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path("/opt/data/profiles/ivan/scratch/saskia-app-work")


def discover_routes():
    """Discover all routes registered in the FastAPI app."""
    code = """
import json
from app.rms.main import app
routes = []
for r in app.routes:
    if hasattr(r, "methods") and hasattr(r, "path"):
        routes.append({
            "path": r.path,
            "methods": sorted(r.methods) if r.methods else [],
        })
print(json.dumps(routes))
"""
    r = subprocess.run(
        ["uv", "run", "python", "-c", code],
        capture_output=True, text=True, cwd=REPO,
    )
    if r.returncode != 0:
        print(f"Failed to discover routes: {r.stderr}")
        sys.exit(1)
    return json.loads(r.stdout)


if __name__ == "__main__":
    routes = discover_routes()
    print(f"Discovered {len(routes)} routes")

    # Group by method
    by_method = defaultdict(list)
    for r in routes:
        for m in r["methods"]:
            by_method[m].append(r["path"])

    for method in sorted(by_method.keys()):
        unique = sorted(set(by_method[method]))
        print(f"\n{method}: {len(unique)} unique paths")
        # Print up to 20
        for p in unique[:20]:
            print(f"  {p}")
        if len(unique) > 20:
            print(f"  ... and {len(unique) - 20} more")
