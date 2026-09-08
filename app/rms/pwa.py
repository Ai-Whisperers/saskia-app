"""app/rms/pwa.py — Progressive Web App seams (E11).

Per docs/plans/2026-09-07-saskia-complete-epic-plan-v3.md E11.

Adds (frontend-facing assets + helpers):
- static/manifest.webmanifest: PWA manifest (name, icons, theme)
- static/sw.js: service worker (cache-first for static, network-first
  for /api/, fallback offline page)
- static/offline.html: graceful offline page
- MobileBreakpoint: viewport helper for Jinja templates (CSS media query)
- is_mobile(request): heuristic User-Agent detection
- pwa_meta_tags(): inject <meta> tags + manifest link in <head>

Route wiring lives elsewhere (routers/pwa.py); this module is the
data + asset layer.
"""
from __future__ import annotations

import re

PWA_MANIFEST = {
    "name": "Saskia RMS",
    "short_name": "Saskia",
    "description": "Restaurant Management System for small bakeries",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#ffffff",
    "theme_color": "#7b3f00",
    "icons": [
        {
            "src": "/static/icons/icon-192.png",
            "sizes": "192x192",
            "type": "image/png",
            "purpose": "any maskable",
        },
        {
            "src": "/static/icons/icon-512.png",
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "any maskable",
        },
    ],
    "categories": ["business", "productivity"],
    "orientation": "portrait",
}


# Mobile-detection regex (Android, iOS, iPad, Windows Phone, BlackBerry, Opera Mini)
_MOBILE_RE = re.compile(
    r"Mobile|iP(hone|od|ad)|Android|BlackBerry|IEMobile|Kindle|"
    r"Silk-Accelerated|hpwOS|webOS|Opera M(obi|ini)",
    re.IGNORECASE,
)


def is_mobile(user_agent: str) -> bool:
    """Heuristic mobile detection based on User-Agent."""
    if not user_agent:
        return False
    return bool(_MOBILE_RE.search(user_agent))


# Routes that should be pre-cached for offline read-only access.
# Operator's daily check-in: dashboard + product list (read-only).
OFFLINE_CACHE_ROUTES: tuple[str, ...] = (
    "/",
    "/productos",
    "/inventario",
    "/recetas",
    "/offline",
)


SW_VERSION = "v1.4.0"


def service_worker_source() -> str:
    """Render the service worker JavaScript source as a string.

    The JS body is a small static script; we keep it inline so the
    version bumps are visible in git history.
    """
    cache_list = ", ".join(f'"{r}"' for r in OFFLINE_CACHE_ROUTES)
    return f"""
// Saskia RMS service worker — {SW_VERSION}
const CACHE = "saskia-{SW_VERSION}";
const ROUTES = [{cache_list}];

self.addEventListener("install", (event) => {{
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(ROUTES)).catch(() => {{}})
  );
  self.skipWaiting();
}});

self.addEventListener("activate", (event) => {{
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
}});

self.addEventListener("fetch", (event) => {{
  const url = new URL(event.request.url);
  // API: network-first
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/sales")) {{
    event.respondWith(
      fetch(event.request).catch(() =>
        new Response(JSON.stringify({{offline: true}}), {{
          headers: {{"Content-Type": "application/json"}},
          status: 503,
        }})
      )
    );
    return;
  }}
  // Static assets: cache-first
  if (url.pathname.startsWith("/static/")) {{
    event.respondWith(
      caches.match(event.request).then((cached) =>
        cached || fetch(event.request).then((resp) => {{
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(event.request, copy));
          return resp;
        }})
      )
    );
    return;
  }}
  // HTML: network-first with offline fallback
  if (event.request.headers.get("accept")?.includes("text/html")) {{
    event.respondWith(
      fetch(event.request).catch(() =>
        caches.match("/offline").then((cached) =>
          cached || new Response("Offline", {{status: 503}})
        )
      )
    );
    return;
  }}
}});
""".strip()


OFFLINE_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sin conexión — Saskia RMS</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 480px;
           margin: 4rem auto; padding: 1.5rem; text-align: center; }
    h1 { color: #7b3f00; }
    .wifi { font-size: 4rem; margin: 1rem 0; }
  </style>
</head>
<body>
  <div class="wifi">📡</div>
  <h1>Sin conexión</h1>
  <p>Saskia RMS no puede contactar al servidor en este momento.</p>
  <p>Verificá tu conexión Wi-Fi / datos y volvé a intentar.</p>
  <p><a href="/">Reintentar</a></p>
</body>
</html>
"""


def pwa_meta_tags() -> str:
    """Meta tags + manifest link for the <head>."""
    return "\n".join(
        [
            '<link rel="manifest" href="/static/manifest.webmanifest">',
            '<meta name="theme-color" content="#7b3f00">',
            '<meta name="apple-mobile-web-app-capable" content="yes">',
            '<meta name="apple-mobile-web-app-title" content="Saskia">',
            '<meta name="apple-mobile-web-app-status-bar-style" content="default">',
            '<link rel="apple-touch-icon" href="/static/icons/icon-192.png">',
        ]
    )


def register_service_worker_script() -> str:
    """Inline JS to register the service worker."""
    return (
        'if ("serviceWorker" in navigator) {\n'
        '  window.addEventListener("load", () => {\n'
        '    navigator.serviceWorker.register("/static/sw.js");\n'
        '  });\n'
        '}'
    )


__all__ = [
    "PWA_MANIFEST",
    "OFFLINE_CACHE_ROUTES",
    "SW_VERSION",
    "OFFLINE_HTML",
    "is_mobile",
    "service_worker_source",
    "pwa_meta_tags",
    "register_service_worker_script",
]
