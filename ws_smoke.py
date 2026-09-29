#!/usr/bin/env python3
"""Quick WS smoke test."""
import asyncio
import json
import sys
import websockets


async def main():
    ws_url = sys.argv[1]
    async with websockets.connect(ws_url, max_size=64 * 1024 * 1024) as ws:
        print("WS connected; sending Target.getTargetInfo")
        await ws.send(json.dumps({"id": 1, "method": "Target.getTargetInfo"}))
        for i in range(5):
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            resp = json.loads(raw)
            print("got:", json.dumps(resp)[:200])
            if "id" in resp and resp.get("id") == 1:
                break


asyncio.run(main())