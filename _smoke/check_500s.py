"""Hit every page with proper data + verify DB queries don't crash.

ProgrammingErrors happen when SQLAlchemy queries reference columns that
don't exist in the schema. This test:
  1. Hits every page route (GET)
  2. For pages that load model data, verifies the ORM query doesn't error
  3. Reports 500s with full traceback
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path("/opt/data/profiles/ivan/scratch/sazon-app-work")


def discover_routes():
    code = """
import json
from app.rms.main import app
routes = []
for r in app.routes:
    if hasattr(r, "methods") and hasattr(r, "path"):
        if "GET" in r.methods or "POST" in r.methods:
            # Skip static
            if r.path.startswith("/static"):
                continue
            routes.append({
                "path": r.path,
                "methods": sorted(r.methods),
            })
print(json.dumps(routes))
"""
    r = subprocess.run(
        ["uv", "run", "python", "-c", code],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    return json.loads(r.stdout)


def main() -> int:
    routes = discover_routes()
    # Filter out API JSON endpoints (those are tested separately)
    html_routes = [r for r in routes if "GET" in r["methods"] and "/api" not in r["path"]]
    print(f"Found {len(html_routes)} HTML GET routes")

    # Replace path params with realistic values
    replacements = {
        "{customer_id}": "1",
        "{ing_id}": "1",
        "{r_id}": "1",
        "{recipe_id}": "13",
        "{pedido_id}": "1",
        "{bench_id}": "1",
        "{item_id}": "1",
        "{sale_id}": "1",
        "{tx_id}": "1",
        "{waste_id}": "1",
        "{plan_id}": "1",
        "{setting_key}": "ui.theme",
        "{username}": "test",
        "{slug}": "test",
        "{token}": "abc123",
    }
    for r in html_routes:
        for k, v in replacements.items():
            r["test_path"] = r["path"].replace(k, v)
        if "{" in r["test_path"]:
            r["test_path"] = re.sub(r"\{[^}]+\}", "999999", r["test_path"])

    code = """
import json
import sys
from fastapi.testclient import TestClient
from app.rms.main import app

routes = json.loads(sys.argv[1])
client = TestClient(app, raise_server_exceptions=False)
# Prime CSRF
client.get('/inicio')
csrf = client.cookies.get('csrf_token', '')

errors = []
for r in routes:
    p = r['test_path']
    try:
        resp = client.get(p)
        if resp.status_code == 500:
            errors.append({
                'path': p,
                'status': resp.status_code,
                'body': resp.text[:500],
            })
    except Exception as e:
        errors.append({
            'path': p,
            'status': 'EXCEPTION',
            'body': str(e)[:300],
        })

print(json.dumps(errors))
"""
    # Save routes to a file and pass via stdin
    proc = subprocess.run(
        ["uv", "run", "python", "-c", code, json.dumps(html_routes)],
        capture_output=True,
        text=True,
        cwd=REPO,
        timeout=180,
    )
    if proc.returncode != 0:
        print(f"ERROR: {proc.stderr[:500]}")
        return 1
    errors = json.loads(proc.stdout)
    print(f"\nFound {len(errors)} routes with errors:")
    for e in errors:
        print(f"  {e['status']} {e['path']}")
        if "body" in e:
            print(f"    {e['body'][:300]}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
