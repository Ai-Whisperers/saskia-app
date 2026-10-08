"""
data/generate_images.py — Run AI image generation for all 125 items.

Reads data/images/prompts.jsonl, calls the MiniMax image-01 API
(using the OAuth token from /opt/data/auth.json), downloads each
result, and saves to the target paths.

Usage:
    .venv/bin/python data/generate_images.py                  # all 125
    .venv/bin/python data/generate_images.py --only-slug babka # test 1
    .venv/bin/python data/generate_images.py --type product   # products only
    .venv/bin/python data/generate_images.py --type ingredient --limit 5
    .venv/bin/python data/generate_images.py --dry-run        # just validate, no API calls
    .venv/bin/python data/generate_images.py --candidates 3  # 3 candidates per item

For each item, generates 1 (or N) candidate image(s). Saves to:
  data/images/candidates/<slug>__cand<N>.jpg (working copies)
  app/static/products/<slug>.jpg or app/static/ingredients/<slug>.jpg (final, after QC)

QC is currently manual — the script picks candidate #1 as the final by default.
Use --candidate N to pick a different one, or --manual to skip picking and
just generate all candidates.

Resumable: skips items that already have a candidate file.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_PATH = ROOT / "data" / "images" / "prompts.jsonl"
CANDIDATES_DIR = ROOT / "data" / "images" / "candidates"
AUTH_PATH = Path("/opt/data/auth.json")

API_URL = "https://api.minimax.io/v1/image_generation"
ASPECT_TO_MINIMAX = {
    "1:1": "1:1",
    "4:3": "4:3",
    "3:2": "3:2",
    "16:9": "16:9",
    "2:3": "2:3",
    "3:4": "3:4",
    "9:16": "9:16",
    "21:9": "21:9",
}


def load_token() -> str:
    """Pull the minimax-oauth access_token from /opt/data/auth.json."""
    if not AUTH_PATH.exists():
        sys.exit(f"missing {AUTH_PATH}")
    auth = json.loads(AUTH_PATH.read_text())
    pool = auth.get("credential_pool", {}).get("minimax-oauth", [])
    if not pool:
        sys.exit("no minimax-oauth credential in auth.json")
    tok = pool[0].get("access_token")
    if not tok:
        sys.exit("minimax-oauth credential has no access_token")
    return tok


def call_minimax_image(prompt: str, aspect: str, token: str, *, max_retries: int = 3) -> str:
    """Call MiniMax image-01 and return the image URL. Raises on failure."""
    aspect = ASPECT_TO_MINIMAX.get(aspect, "4:3")
    body = {
        "model": "image-01",
        "prompt": prompt,
        "aspect_ratio": aspect,
        "n": 1,
        "response_format": "url",
        "prompt_optimizer": True,
    }
    last_err = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                API_URL,
                data=json.dumps(body).encode(),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read())
                base = data.get("base_resp", {})
                if base.get("status_code", 0) != 0:
                    raise RuntimeError(f"minimax error: {base.get('status_msg')}")
                urls = data.get("data", {}).get("image_urls", [])
                if not urls:
                    raise RuntimeError("minimax returned no image_urls")
                return urls[0]
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            last_err = e
            wait = 2**attempt
            print(f"  retry {attempt + 1}/{max_retries} after {wait}s: {e}", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"minimax image gen failed: {last_err}")


def download(url: str, dest: Path, *, max_retries: int = 3):
    """Download URL to dest. Retries on failure."""
    last_err = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "sazon-image-gen/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                dest.write_bytes(r.read())
            return
        except Exception as e:
            last_err = e
            wait = 2**attempt
            print(f"  download retry {attempt + 1}/{max_retries}: {e}", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"download failed: {last_err}")


def process_one(item: dict, token: str, *, candidates: int, out_dir: Path, sleep: float) -> dict:
    """Generate `candidates` images for one item, save them. Return summary."""
    results = {
        "id": item["id"],
        "slug": item["slug"],
        "name": item["name"],
        "type": item["type"],
        "candidates": [],
    }

    for c in range(1, candidates + 1):
        cand_path = out_dir / f"{item['slug']}__cand{c}.jpg"
        if cand_path.exists():
            results["candidates"].append(
                {"n": c, "path": str(cand_path), "status": "skipped (exists)"}
            )
            continue

        t0 = time.time()
        try:
            url = call_minimax_image(item["prompt"], item["aspect_ratio"], token)
            download(url, cand_path)
            dt = round(time.time() - t0, 2)
            sz = cand_path.stat().st_size
            results["candidates"].append(
                {
                    "n": c,
                    "path": str(cand_path),
                    "status": "ok",
                    "size_bytes": sz,
                    "elapsed_s": dt,
                }
            )
            print(f"  ✓ cand {c}: {cand_path.name} ({sz:,}B, {dt}s)", file=sys.stderr)
        except Exception as e:
            dt = round(time.time() - t0, 2)
            results["candidates"].append({"n": c, "status": f"FAIL: {e}", "elapsed_s": dt})
            print(f"  ✗ cand {c}: {e} ({dt}s)", file=sys.stderr)
        time.sleep(sleep)
    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--prompts", default=str(PROMPTS_PATH))
    p.add_argument("--out-dir", default=str(CANDIDATES_DIR))
    p.add_argument("--type", choices=["product", "ingredient"], default=None)
    p.add_argument("--only-slug", default=None)
    p.add_argument("--limit", type=int, default=None, help="cap items processed")
    p.add_argument("--candidates", type=int, default=1, help="candidates per item")
    p.add_argument("--start-from", type=int, default=0, help="skip first N items (for resuming)")
    p.add_argument("--sleep", type=float, default=1.0, help="seconds between API calls")
    p.add_argument("--dry-run", action="store_true", help="validate + show, no API calls")
    p.add_argument("--log", default=str(CANDIDATES_DIR / "run_log.jsonl"), help="per-item run log")
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not Path(args.prompts).exists():
        sys.exit(f"missing {args.prompts} — run build_image_prompts.py first")

    items = []
    with open(args.prompts) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))

    # Skip variant products (no outputs)
    items = [i for i in items if i.get("outputs")]
    if args.type:
        items = [i for i in items if i["type"] == args.type]
    if args.only_slug:
        items = [i for i in items if i["slug"] == args.only_slug]
    if args.start_from:
        items = items[args.start_from :]
    if args.limit:
        items = items[: args.limit]

    print("\n=== generate_images ===", file=sys.stderr)
    print(
        f"items: {len(items)}  candidates/item: {args.candidates}  sleep: {args.sleep}s  dry-run: {args.dry_run}",
        file=sys.stderr,
    )
    print(f"out-dir: {out_dir}", file=sys.stderr)

    if args.dry_run:
        for i, item in enumerate(items):
            print(
                f"  [{i + 1}/{len(items)}] {item['type']:10s} {item['slug']:40s} -> {item['aspect_ratio']}"
            )
        return

    token = load_token()
    print(f"token loaded (len={len(token)})", file=sys.stderr)

    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as logf:
        t0_total = time.time()
        for i, item in enumerate(items):
            print(
                f"\n[{i + 1}/{len(items)}] {item['type']}  {item['slug']}  ({item['name']})",
                file=sys.stderr,
            )
            results = process_one(
                item, token, candidates=args.candidates, out_dir=out_dir, sleep=args.sleep
            )
            logf.write(json.dumps(results, ensure_ascii=False) + "\n")
            logf.flush()
        dt_total = round(time.time() - t0_total, 2)
        print(f"\n=== done: {len(items)} items in {dt_total}s ===", file=sys.stderr)


if __name__ == "__main__":
    main()
