"""capture_extra_screenshots.py — login + dashboard + admin pages."""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://sazon-vps.paragu-ai.com"
OUT = Path("/opt/data/profiles/ivan/scratch/sazon-app-work/docs/user-guide/screenshots")
JAR = Path("/tmp/sazon-jar.txt")
CHROME = "/opt/data/home/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome"

EXTRA = [
    ("/login", "00-login", 2000, False),  # no auth
    ("/", "00-dashboard", 3000, True),
    ("/auditoria", "19-auditoria", 3000, True),
    ("/settings", "20-settings", 3500, True),
    ("/ops/status", "21-ops", 3000, True),
    ("/excel", "22-excel", 3500, True),
]


def load_cookies() -> list:
    cookies = []
    with open(JAR) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("# "):
                continue
            is_http_only = False
            if line.startswith("#HttpOnly_"):
                is_http_only = True
                line = line[len("#HttpOnly_") :]
            if line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            cookies.append(
                {
                    "name": parts[5],
                    "value": parts[6],
                    "domain": parts[0],
                    "path": parts[2],
                    "expires": int(parts[4]) if parts[4].isdigit() else -1,
                    "httpOnly": is_http_only,
                    "secure": parts[3].upper() == "TRUE",
                    "sameSite": "Lax",
                }
            )
    return cookies


with sync_playwright() as pw:
    browser = pw.chromium.launch(
        headless=True, executable_path=CHROME, args=["--no-sandbox", "--disable-dev-shm-usage"]
    )
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    auth_cookies = load_cookies()
    page = ctx.new_page()

    for path, label, wait_ms, needs_auth in EXTRA:
        if needs_auth:
            ctx.add_cookies(auth_cookies)
        else:
            ctx.clear_cookies()
        page.goto(BASE + path, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(wait_ms)
        out_path = OUT / f"{label}.png"
        page.screenshot(path=str(out_path), full_page=True)
        size = out_path.stat().st_size // 1024
        print(f"  {path:30s} -> {out_path.name} ({size:,}KB)")

    browser.close()
print("done")
