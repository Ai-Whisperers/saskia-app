"""
data/publish_images.py — Move selected candidate images to the final
app/static/... destinations.

For each item in items.json that has outputs, this script:
  1. Looks at data/images/candidates/<slug>__cand{1,2,3...}.jpg
  2. Picks one (default: cand1) OR the one passed via --pick
  3. Copies it to each of the item's output paths
  4. For products: also copies to receta-<slug>.jpg in app/static/recipes/
     (since per the design, recipes and products share the same image)

Usage:
    .venv/bin/python data/publish_images.py                       # publish all (cand1)
    .venv/bin/python data/publish_images.py --only-slug stroop_wafel
    .venv/bin/python data/publish_images.py --pick 2               # use cand2
    .venv/bin/python data/publish_images.py --dry-run              # show what would happen
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ITEMS_PATH = ROOT / "data" / "images" / "items.json"
CANDIDATES_DIR = ROOT / "data" / "images" / "candidates"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pick", type=int, default=1, help="which candidate (1, 2, ...)")
    p.add_argument("--only-slug", default=None)
    p.add_argument("--type", choices=["product", "ingredient"], default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true", help="overwrite existing final images")
    args = p.parse_args()

    items = json.loads(ITEMS_PATH.read_text())
    items = [i for i in items if i.get("outputs")]
    if args.only_slug:
        items = [i for i in items if i["slug"] == args.only_slug]
    if args.type:
        items = [i for i in items if i["type"] == args.type]

    print(f"=== publish_images ===")
    print(
        f"items: {len(items)}  pick: cand{args.pick}  force: {args.force}  dry-run: {args.dry_run}"
    )

    published = 0
    skipped = 0
    missing = 0
    for item in items:
        cand = CANDIDATES_DIR / f"{item['slug']}__cand{args.pick}.jpg"
        if not cand.exists():
            print(f"  ✗ {item['slug']:50s} no cand{args.pick} at {cand.name}")
            missing += 1
            continue
        for out in item["outputs"]:
            dest = ROOT / out["path"]
            if dest.exists() and not args.force:
                print(f"  · {item['slug']:50s} -> {dest.relative_to(ROOT)}  (exists, skip)")
                skipped += 1
                continue
            if args.dry_run:
                print(f"  ~ {item['slug']:50s} -> {dest.relative_to(ROOT)}  (dry-run)")
                published += 1
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(cand, dest)
                print(f"  ✓ {item['slug']:50s} -> {dest.relative_to(ROOT)}")
                published += 1

    print(f"\n=== done: {published} published, {skipped} skipped, {missing} missing ===")


if __name__ == "__main__":
    main()
