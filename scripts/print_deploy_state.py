#!/usr/bin/env python3
"""scripts/print_deploy_state.py — one-shot view of what's deployed where.

For each of the 3 Sazon environments (dev, test, prod), prints:
  - the URL and hostname
  - whether /healthz is 200 (live) or not
  - the image tag (extracted from /api/build-info if available, else
    "/api/version" string, else "unknown")
  - the /healthz/deps status code (env var presence check)
  - the /healthz/backup status code (backup-age check)

Usage:
  uv run python scripts/print_deploy_state.py
  uv run python scripts/print_deploy_state.py --json    # machine-readable
  uv run python scripts/print_deploy_state.py --env=dev # one env only

The 3 envs are sourced from deploy/envs.yaml. We read the hostname +
public_url fields; no secrets, no DB access, no auth.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ENVS_YAML = ROOT / "deploy" / "envs.yaml"


def load_envs() -> dict:
    # The envs.yaml structure: 3 top-level keys (prod, test, dev),
    # each with hostname, public_url (optional), and other config.
    with open(ENVS_YAML) as f:
        return yaml.safe_load(f)


def probe(url: str, timeout: int = 5) -> dict:
    """Hit <url> and return a probe dict."""
    out = {"url": url, "status": "error", "code": None, "body": None}
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            out["status"] = "live"
            out["code"] = r.status
            body = r.read().decode("utf-8", errors="replace")
            # Try to parse as JSON for build-info
            try:
                out["body"] = json.loads(body)
            except json.JSONDecodeError:
                out["body"] = body[:200]
    except urllib.error.HTTPError as e:
        out["status"] = "degraded"
        out["code"] = e.code
        out["body"] = e.read().decode("utf-8", errors="replace")[:200]
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        out["status"] = "down"
        out["body"] = str(e)
    return out


def check_env(env_name: str, env_row: dict) -> dict:
    """Run all 4 probes against a single env."""
    base = env_row.get("public_url") or f"https://{env_row['hostname']}"
    return {
        "env": env_name,
        "hostname": env_row.get("hostname"),
        "public_url": base,
        "probes": {
            "healthz":       probe(f"{base}/healthz"),
            "healthz_deps":  probe(f"{base}/healthz/deps"),
            "healthz_backup": probe(f"{base}/healthz/backup"),
        },
    }


def render_table(results: list[dict]) -> str:
    """Render a small ASCII table (no external deps)."""
    if not results:
        return "_(no envs to check)_"
    headers = ["env", "hostname", "healthz", "deps", "backup"]
    rows = [headers]
    for r in results:
        rows.append([
            r["env"],
            r["hostname"],
            _short(r["probes"]["healthz"]),
            _short(r["probes"]["healthz_deps"]),
            _short(r["probes"]["healthz_backup"]),
        ])
    widths = [max(len(r[i]) for r in rows) for i in range(len(headers))]
    out = []
    for i, row in enumerate(rows):
        out.append("  ".join(c.ljust(widths[j]) for j, c in enumerate(row)))
        if i == 0:
            out.append("  ".join("-" * w for w in widths))
    return "\n".join(out)


def _short(probe: dict) -> str:
    if probe["status"] == "live":
        return f"OK {probe['code']}"
    if probe["status"] == "degraded":
        return f"⚠ {probe['code']}"
    return f"✗ down"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--env", help="Check only this env (default: all 3)")
    p.add_argument("--json", action="store_true", help="JSON output")
    args = p.parse_args()

    envs = load_envs()
    if args.env:
        if args.env not in envs:
            print(f"ERROR: env '{args.env}' not in {ENVS_YAML} "
                  f"(known: {', '.join(envs.keys())})", file=sys.stderr)
            return 2
        envs = {args.env: envs[args.env]}

    results = [check_env(name, row) for name, row in envs.items()]

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"Deploy state ({len(results)} envs)")
        print("=" * 60)
        print(render_table(results))
        print()
        # Print the build-info / image if we got it
        for r in results:
            body = r["probes"]["healthz"].get("body")
            if isinstance(body, dict) and "image_tag" in body:
                print(f"  {r['env']}: image_tag={body['image_tag']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
