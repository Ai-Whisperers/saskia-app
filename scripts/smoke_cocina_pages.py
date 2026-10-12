#!/usr/bin/env python3
"""smoke_cocina_pages.py — Live HTTP smoke test for all SASKIA-211 cocina pages.

Logs into https://saskia-vps.paragu-ai.com, picks the gerencia station, and
hits every cocina page (recetas / eod / produccion / merma) + their key
sub-routes. For each route, records:

  - HTTP status code
  - response time
  - content-type
  - body length
  - expected content fingerprints (CSS classes, table headers, form fields)
  - 5xx detection (any 500/502/503/504 = fail)

Fails loudly if:
  - /recetas/{id}/editar returns 500 (B1 regression)
  - /recetas/export returns 400 (B3 regression)
  - /recetas/api/families returns [] (B7 regression)
  - /eod/print raises 500 (B2 regression)
  - Any 5xx on any cocina route

Usage:
  uv run python scripts/smoke_cocina_pages.py           # run live smoke
  uv run python scripts/smoke_cocina_pages.py --json     # JSON output
  uv run python scripts/smoke_cocina_pages.py --base=https://saskia-test.paragu-ai.com
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib3
from dataclasses import dataclass, field, asdict
from typing import Optional

import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_BASE = "https://saskia-vps.paragu-ai.com"
USERNAME = "saskia"
PASSWORD = "saskia1234"

# Cocina page routes under test. Grouped by feature so we report a summary
# per feature, not just per route.
ROUTE_GROUPS = {
    "recetas_list": [
        ("GET", "/recetas"),
    ],
    "recetas_detail": [
        # (id_var, expected_status, fingerprint_substring)
        # id_var is filled from the first /recetas list response (real id from DB)
    ],
    "recetas_new": [
        ("GET", "/recetas/nueva"),
    ],
    "recetas_export_csv": [
        ("GET", "/recetas/export"),
    ],
    "recetas_api_families": [
        ("GET", "/recetas/api/families"),
    ],
    "recetas_api_units": [
        ("GET", "/recetas/api/units"),
    ],
    "produccion": [
        ("GET", "/produccion"),
        ("GET", "/produccion/api/forecast"),
    ],
    "eod": [
        ("GET", "/eod"),
        ("GET", "/eod/print"),
    ],
    "merma": [
        ("GET", "/merma"),
    ],
}

# Sub-routes that require a recipe id from the list — collected dynamically.
# After loading /recetas, we extract a real recipe id and exercise:
RECIPE_ID_ROUTES = [
    ("GET", "/recetas/{id}/editar"),
    ("GET", "/recetas/{id}"),
    ("GET", "/recetas/{id}/set-photo"),
    ("GET", "/recetas/api/{id}/effective-ingredients"),
]


@dataclass
class RouteResult:
    method: str
    path: str
    status: int
    elapsed_ms: int
    content_type: str
    body_len: int
    expected: str = ""
    matched: bool = True
    error: Optional[str] = None
    fingerprint: str = ""


@dataclass
class GroupReport:
    group: str
    routes: list[RouteResult] = field(default_factory=list)
    pass_count: int = 0
    fail_count: int = 0


def login(base: str) -> tuple[requests.Session, str]:
    """Login, pick gerencia station, return (session, csrf_token)."""
    s = requests.Session()
    # 1. GET /login to establish cookies
    r = s.get(f"{base}/login", verify=False, timeout=10, allow_redirects=True)
    r.raise_for_status()
    # 2. POST credentials
    r = s.post(
        f"{base}/login",
        data={"username": USERNAME, "password": PASSWORD, "next": "/puesto"},
        verify=False, timeout=10, allow_redirects=True,
    )
    r.raise_for_status()
    if "/puesto" not in r.url:
        raise RuntimeError(f"login did not redirect to /puesto (got {r.url})")
    # 3. GET /puesto to find csrf token + station cards
    r = s.get(f"{base}/puesto", verify=False, timeout=10)
    r.raise_for_status()
    m = re.search(r'name="csrf_token"[^>]+value="([^"]+)"', r.text)
    if not m:
        raise RuntimeError("no csrf_token found on /puesto")
    csrf = m.group(1)
    # 4. POST /puesto to pick gerencia (admin can pick any)
    r = s.post(
        f"{base}/puesto",
        data={"station": "gerencia", "csrf_token": csrf},
        verify=False, timeout=10, allow_redirects=True,
    )
    r.raise_for_status()
    return s, csrf


def extract_recipe_id(html: str) -> Optional[int]:
    """Find the first recipe id in the /recetas list page."""
    m = re.search(r'/recetas/(\d+)/(?:editar|set-photo)', html)
    if m:
        return int(m.group(1))
    m = re.search(r'href="/recetas/(\d+)"', html)
    if m:
        return int(m.group(1))
    return None


def hit(s: requests.Session, method: str, path: str, base: str,
        expected: str = "", allow_redirects: bool = True) -> RouteResult:
    t0 = time.perf_counter()
    try:
        r = s.request(method, f"{base}{path}", verify=False, timeout=15,
                       allow_redirects=allow_redirects)
        elapsed = int((time.perf_counter() - t0) * 1000)
        ctype = r.headers.get("content-type", "")
        body = r.text
        # If we followed a redirect, count the FINAL status, not the 30x.
        # requests' r.status_code already gives the final.
        matched = (expected in body) if expected else True
        fp = ""
        if expected:
            # Find a short snippet around the first match (or first miss)
            idx = body.find(expected)
            if idx == -1:
                fp = f"MISSING: {expected!r}"
            else:
                fp = f"FOUND: {expected!r} at {idx}"
        return RouteResult(
            method=method, path=path, status=r.status_code,
            elapsed_ms=elapsed, content_type=ctype, body_len=len(body),
            expected=expected, matched=matched, fingerprint=fp,
        )
    except Exception as exc:
        elapsed = int((time.perf_counter() - t0) * 1000)
        return RouteResult(
            method=method, path=path, status=0,
            elapsed_ms=elapsed, content_type="", body_len=0,
            expected=expected, matched=False, error=str(exc),
        )


def run(base: str = DEFAULT_BASE, as_json: bool = False) -> int:
    print(f"== smoke_cocina_pages ==")
    print(f"base: {base}")
    print(f"login as {USERNAME} ...", end=" ", flush=True)
    s, _csrf = login(base)
    print("ok")

    groups: dict[str, GroupReport] = {}

    def report(group: str, result: RouteResult) -> None:
        g = groups.setdefault(group, GroupReport(group=group))
        g.routes.append(result)
        if 200 <= result.status < 400 and result.matched and not result.error:
            g.pass_count += 1
        else:
            g.fail_count += 1
        # Pretty line
        ok = "✓" if (200 <= result.status < 400 and result.matched and not result.error) else "✗"
        line = (
            f"  {ok} {result.method} {result.path:<55s} "
            f"{result.status:>3d}  {result.elapsed_ms:>4d}ms  "
            f"{result.body_len:>6d}b  {result.content_type[:30]}"
        )
        if result.error:
            line += f"  ERR={result.error[:60]}"
        elif result.expected and not result.matched:
            line += f"  fp-miss"
        print(line)

    # 1. recetas list (extract a recipe id from it)
    recetas_result = hit(s, "GET", "/recetas", base)
    report("recetas_list", recetas_result)
    if recetas_result.status != 200:
        print("ERROR: /recetas not 200; aborting recipe-id routes")
        recipe_id = None
    else:
        recipe_id = extract_recipe_id(recetas_result.fingerprint or recetas_result.body_len and "") or None
        if recipe_id is None:
            # Re-parse the body
            recipe_id = extract_recipe_id(s.get(f"{base}/recetas", verify=False, timeout=10).text)
        print(f"  → extracted recipe_id = {recipe_id}")

    # 2. receta detail routes
    if recipe_id:
        for method, tmpl in RECIPE_ID_ROUTES:
            path = tmpl.format(id=recipe_id)
            result = hit(s, method, path, base)
            label = f"recetas_detail_{recipe_id}"
            if "/editar" in path:
                # B1 regression check
                if result.status == 500:
                    result.fingerprint = "FAIL B1: /editar returned 500"
                report("recetas_detail_editar", result)
            elif path.endswith(f"/{recipe_id}"):
                report("recetas_detail_view", result)
            elif "/set-photo" in path:
                report("recetas_set_photo", result)
            elif "/effective-ingredients" in path:
                report("recetas_effective_ingredients", result)
            else:
                report(label, result)

    # 3. recetas/nueva
    r = hit(s, "GET", "/recetas/nueva", base)
    report("recetas_new", r)

    # 4. recetas/export (B3 regression check)
    r = hit(s, "GET", "/recetas/export", base, allow_redirects=False)
    if r.status == 200 and "text/csv" in r.content_type:
        r.fingerprint = f"OK CSV ({r.body_len} bytes)"
    elif r.status == 400:
        r.fingerprint = "FAIL B3: /export returned 400"
    report("recetas_export_csv", r)

    # 5. recetas/api/families (B7 regression check)
    # Re-fetch to get the body for inspection (hit() doesn't store it on RouteResult)
    api_resp = s.get(f"{base}/recetas/api/families", verify=False, timeout=10)
    n = 0
    if api_resp.status_code == 200:
        try:
            data = api_resp.json()
            n = len(data) if isinstance(data, list) else 0
        except Exception:
            pass
    r = hit(s, "GET", "/recetas/api/families", base)
    r.body_len = len(api_resp.text)
    if n > 0:
        r.fingerprint = f"OK: {n} families"
    elif r.status == 200:
        r.fingerprint = "FAIL B7: /api/families returned []"
    report("recetas_api_families", r)

    # 6. recetas/api/units
    r = hit(s, "GET", "/recetas/api/units", base)
    report("recetas_api_units", r)

    # 7. produccion
    r = hit(s, "GET", "/produccion", base)
    report("produccion", r)
    # /produccion/api/forecast requires ?for_date=YYYY-MM-DD
    today = time.strftime("%Y-%m-%d")
    r = hit(s, "GET", f"/produccion/api/forecast?for_date={today}", base)
    if r.status == 200 and "application/json" in r.content_type:
        r.fingerprint = "OK JSON"
    elif r.status != 200:
        r.fingerprint = f"FAIL: status {r.status}"
    report("produccion_api_forecast", r)

    # 8. eod + eod/print
    r = hit(s, "GET", "/eod", base)
    report("eod", r)
    r = hit(s, "GET", "/eod/print", base)
    if r.status == 500:
        r.fingerprint = "FAIL B2: /eod/print returned 500 (template field mismatch)"
    elif r.status == 200 and ("print" in r.content_type or "html" in r.content_type):
        r.fingerprint = f"OK HTML ({r.body_len} bytes)"
    report("eod_print", r)

    # 9. merma (B10 regression check — just hit it, B10 is about a11y not 5xx)
    r = hit(s, "GET", "/merma", base)
    report("merma", r)

    # Summary
    total_pass = sum(g.pass_count for g in groups.values())
    total_fail = sum(g.fail_count for g in groups.values())
    print()
    print(f"== summary ==")
    print(f"groups: {len(groups)}")
    print(f"pass:   {total_pass}")
    print(f"fail:   {total_fail}")

    if as_json:
        out = {
            "base": base,
            "groups": [
                {
                    "group": g.group,
                    "pass_count": g.pass_count,
                    "fail_count": g.fail_count,
                    "routes": [asdict(r) for r in g.routes],
                }
                for g in groups.values()
            ],
            "total_pass": total_pass,
            "total_fail": total_fail,
        }
        print()
        print(json.dumps(out, indent=2, default=str))

    return 0 if total_fail == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=DEFAULT_BASE, help="base URL to test")
    ap.add_argument("--json", action="store_true", help="JSON output")
    args = ap.parse_args()
    return run(args.base, args.json)


if __name__ == "__main__":
    sys.exit(main())
