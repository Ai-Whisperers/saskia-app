#!/usr/bin/env python3
"""Connect to a Chrome page WS and capture a full-page screenshot — no domain enable."""
import asyncio
import base64
import json
import sys
import urllib.request

import websockets


async def get_page_ws(port: int, url_substr: str) -> str:
    req = urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5)
    tabs = json.loads(req.read())
    for t in tabs:
        if t.get("type") == "page" and url_substr in t.get("url", ""):
            return t["webSocketDebuggerUrl"]
    raise RuntimeError(
        f"No tab with URL containing {url_substr!r}. Tabs: "
        f"{[(t['type'], t.get('url', '')[:60]) for t in tabs]}"
    )


async def take_screenshot(page_ws: str, out_path: str):
    async with websockets.connect(page_ws, max_size=128 * 1024 * 1024) as ws:
        next_id = [0]

        async def send(method, params=None, timeout=300):
            next_id[0] += 1
            payload = {"id": next_id[0], "method": method}
            if params is not None:
                payload["params"] = params
            await ws.send(json.dumps(payload))
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                resp = json.loads(raw)
                if "id" in resp:
                    if "error" in resp:
                        raise RuntimeError(f"CDP error in {method}: {resp['error']}")
                    return resp.get("result")

        # Page domain is enabled by default on a fresh page target.
        # Just take the screenshot.
        result = await send("Page.captureScreenshot", {
            "format": "png",
            "captureBeyondViewport": True,
        })
        png = base64.b64decode(result["data"])
        with open(out_path, "wb") as f:
            f.write(png)
        print(f"OK wrote {out_path} ({len(png)} bytes)")


async def main():
    port = int(sys.argv[1])
    url_substr = sys.argv[2]
    out_path = sys.argv[3]
    page_ws = await get_page_ws(port, url_substr)
    print(f"page ws: {page_ws}")
    await take_screenshot(page_ws, out_path)


if __name__ == "__main__":
    asyncio.run(main())