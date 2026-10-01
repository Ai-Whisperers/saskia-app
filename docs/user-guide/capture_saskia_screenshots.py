"""capture_saskia_screenshots.py — capture daily-use workflow screenshots.

Auth via curl cookie jar → inject into Playwright → screenshot each route.
Outputs PNGs into docs/user-guide/screenshots/, full_page=True for tall dashboards.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://saskia-vps.paragu-ai.com"
OUT = Path("/opt/data/profiles/ivan/scratch/saskia-app-work/docs/user-guide/screenshots")
OUT.mkdir(parents=True, exist_ok=True)
JAR = Path("/tmp/saskia-jar.txt")
CHROME = "/opt/data/home/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome"

# 14 daily-use routes (paths + label slug + wait_ms for slow pages)
ROUTES = [
    ("/ventas", "01-ventas-pos", 4000),
    ("/ventas/nueva", "02-ventas-nueva", 3500),
    ("/pedidos", "03-pedidos-board", 4000),
    ("/pedidos/nuevo", "04-pedidos-nuevo", 3500),
    ("/produccion", "05-produccion", 5000),
    ("/produccion/manana", "06-produccion-manana", 4000),
    ("/eod", "07-eod-checklist", 3000),
    ("/productos", "08-productos", 3500),
    ("/productos/nuevo", "09-productos-nuevo", 3500),
    ("/recetas", "10-recetas", 3500),
    ("/recetas/nueva", "11-recetas-nueva", 3500),
    ("/inventario", "12-inventario", 4000),
    ("/inventario/nuevo", "13-inventario-nuevo", 3500),
    ("/merma", "14-merma", 3000),
    ("/reorder", "15-reorder", 4000),
    ("/reportes/diario", "16-reportes-diario", 4000),
    ("/clientes", "17-clientes", 3500),
    ("/shopping-list", "18-shopping-list", 3000),
]


def load_cookies() -> list[dict]:
    cookies = []
    with open(JAR) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("# "):
                continue
            is_http_only = False
            if line.startswith("#HttpOnly_"):
                is_http_only = True
                line = line[len("#HttpOnly_"):]
            if line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            domain, _flag, path, secure, expires, name_, value = parts[:7]
            cookies.append({
                "name": name_,
                "value": value,
                "domain": domain,
                "path": path,
                "expires": int(expires) if expires.isdigit() else -1,
                "httpOnly": is_http_only,
                "secure": secure.upper() == "TRUE",
                "sameSite": "Lax",
            })
    assert len(cookies) >= 1, f"cookie jar empty: {JAR}"
    return cookies


def capture() -> dict:
    cookies = load_cookies()
    manifest = {"base": BASE, "routes": [], "bugs_found": []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=CHROME,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        ctx.add_cookies(cookies)
        page = ctx.new_page()

        # First navigate to confirm login worked
        page.goto(BASE + "/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2500)
        title = page.title()
        url = page.url
        if "/login" in url:
            print(f"NOT LOGGED IN. Title: {title}, URL: {url}")
            browser.close()
            return manifest

        for path, label, wait_ms in ROUTES:
            url = BASE + path
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(wait_ms)
                status = resp.status if resp else "?"
                # Detect errors
                body_text = page.evaluate("document.body ? document.body.innerText : ''")[:2000]
                is_error_page = (
                    status >= 400
                    or "Traceback" in body_text
                    or ("500" in body_text[:100] and "Internal" in body_text[:100])
                )
                fname = f"{label}.png"
                out_path = OUT / fname
                page.screenshot(path=str(out_path), full_page=True)
                size_kb = out_path.stat().st_size // 1024
                entry = {
                    "path": path,
                    "label": label,
                    "status": status,
                    "file": fname,
                    "size_kb": size_kb,
                    "errors": [],
                }
                if is_error_page:
                    entry["errors"].append("error page rendered")
                    manifest["bugs_found"].append({"path": path, "issue": "5xx / traceback in body"})
                manifest["routes"].append(entry)
                print(f"  {path:30s} -> {status} ({size_kb:,}KB)")
            except Exception as e:
                manifest["bugs_found"].append({"path": path, "issue": str(e)[:200]})
                print(f"  {path:30s} -> EXCEPTION {e}")

        browser.close()

    out_manifest = OUT / "manifest.json"
    out_manifest.write_text(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    m = capture()
    print()
    print(f"Captured {len(m['routes'])} routes")
    print(f"Bugs found: {len(m['bugs_found'])}")
    if m["bugs_found"]:
        for b in m["bugs_found"]:
            print(f"  - {b['path']}: {b['issue']}")