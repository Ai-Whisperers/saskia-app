#!/usr/bin/env python3
"""scripts/capture_screenshots.py — login to live site + fetch every page's HTML.

Captures the rendered HTML for every authenticated page. Used to build
the user guide with realistic copy.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://sazon-rms.paragu-ai.com"
OUTPUT = Path("/tmp/sazon_pages")


def login_and_capture():
    OUTPUT.mkdir(exist_ok=True)
    pwd = Path("/tmp/_sazon_pwd").read_text()

    # Login
    cookie_jar = {}

    login_data = urllib.parse.urlencode(
        {
            "username": "demo@paragu-ai.com",
            "password": pwd,
        }
    ).encode()
    req = urllib.request.Request(
        f"{BASE}/login",
        data=login_data,
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        for h in resp.headers.get_all("Set-Cookie") or []:
            cookie = h.split(";")[0]
            k, _, v = cookie.partition("=")
            cookie_jar[k] = v
    except urllib.error.HTTPError as e:
        print(f"login failed: HTTP {e.code}")
        sys.exit(1)

    cookie_hdr = "; ".join(f"{k}={v}" for k, v in cookie_jar.items())
    print(f"got {len(cookie_jar)} cookies after login")

    # Capture each page
    pages = [
        "/",
        "/productos",
        "/productos/nuevo",
        "/recetas",
        "/inventario",
        "/ventas",
        "/clientes",
        "/produccion",
        "/eod",
        "/merma",
        "/reportes",
        "/reportes/iva",
        "/reportes/libro-ventas",
        "/reportes/diario",
        "/auditoria",
        "/ops/status",
        "/excel",
        "/excel/exportar",
        "/settings",
        "/reorder",
        "/healthz",
        "/healthz/db",
        "/healthz/deps",
        "/healthz/schema",
        "/healthz/errors",
        "/login",
        "/logout",
    ]

    results = {}
    for path in pages:
        req = urllib.request.Request(
            f"{BASE}{path}",
            headers={"Cookie": cookie_hdr},
        )
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            status = e.code
        results[path] = {"status": status, "size": len(body), "body": body[:500]}
        print(f"  {path:40s} HTTP {status} {len(body):>7d} bytes")

    out = OUTPUT / "summary.json"
    out.write_text(
        json.dumps(
            {p: {"status": r["status"], "size": r["size"]} for p, r in results.items()}, indent=2
        )
    )
    print(f"\nSummary: {out}")
    return results


if __name__ == "__main__":
    login_and_capture()
