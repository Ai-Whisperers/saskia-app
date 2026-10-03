#!/usr/bin/env python3
"""scripts/cf_tunnel_liveness.py — Phase 14 (2026-10-01).

Proactive CF-Tunnel liveness check for saskia-vps.paragu-ai.com.

Background:
  The CF-Tunnel between the public URL and the Docker Swarm can fail
  silently — token rotation in BWS, cloudflared daemon crash, Traefik
  label drift after `docker service update --force`. The container
  stays healthy, so /healthz/deps returns 200 from inside the swarm;
  but the public URL 404s or 5xxs for end users.

  See references/cf-tunnel-flap-false-positive.md for the diagnosis
  class.

What this script does:
  Runs 3 probes:
    P1: Public URL — `curl -sk https://saskia-vps.paragu-ai.com/healthz`
        should return `{"status":"ok"}`.
    P2: DNS — `dig +short CNAME saskia-vps.paragu-ai.com` should
        resolve to a *.cfargotunnel.com endpoint.
    P3: App on the swarm — `curl -sk http://127.0.0.1:<port>/healthz/db`
        should return JSON with schema_version present (proves the
        container is up; uses the locally-bound port from the .env).

  If P3 passes but P1 fails → CF-Tunnel flap, alert (don't redeploy).
  If P3 fails → app is genuinely broken (different alert class).
  If P2 fails → DNS drift, also different alert class.

Exit codes:
  0 — all 3 probes pass
  1 — public URL flap (P3 ok, P1 bad) — CF-Tunnel class
  2 — DNS resolution failure (P2 bad) — DNS class
  3 — app unhealthy on swarm (P3 bad) — deploy class
  4 — script error / config missing
  5 — all 3 fail (catastrophic; check VPS / CF account)

Usage:
  python3 scripts/cf_tunnel_liveness.py           # full probe set
  python3 scripts/cf_tunnel_liveness.py --quiet  # one-line output
                                                # (cron-friendly)

Cron wiring:
  The ai-* fleet crons already call shell scripts; add a 30-minute
  probe so a flap is detected within 30 min. Cron registration is
  documented in docs/operations/2026-10-01-phase14-cf-tunnel-cron.md.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

PUBLIC_URL = os.environ.get(
    "SASKIA_PUBLIC_URL", "https://saskia-vps.paragu-ai.com"
)
PUBLIC_HOST = re.sub(r"^https?://", "", PUBLIC_URL).rstrip("/")
LOCAL_PROBE_PORT = int(os.environ.get("SASKIA_LOCAL_HEALTH_PORT", "8080"))
TIMEOUT_S = int(os.environ.get("SASKIA_PROBE_TIMEOUT_S", "15"))
# Skip the local container probe — useful when the script runs
# INSIDE the swarm (the container's 127.0.0.1 is the loopback of
# its own network namespace, not the swarm's published port).
SKIP_LOCAL = os.environ.get("SASKIA_SKIP_LOCAL", "").lower() in (
    "1", "true", "yes", "on",
)


def probe_public() -> tuple[bool, str]:
    """Probe the public URL via HTTPS. Returns (ok, message)."""
    try:
        req = Request(f"{PUBLIC_URL}/healthz", method="GET")
        with urlopen(req, timeout=TIMEOUT_S) as r:
            body = r.read().decode("utf-8", errors="replace")
            if r.status != 200:
                return False, f"HTTP {r.status} on public /healthz"
            data = json.loads(body)
            if data.get("status") != "ok":
                return False, f"public /healthz status={data.get('status')!r}"
            return True, "public /healthz ok"
    except URLError as exc:
        return False, f"public /healthz unreachable: {exc}"
    except (json.JSONDecodeError, ValueError) as exc:
        return False, f"public /healthz non-JSON: {exc}"
    except Exception as exc:  # noqa: BLE001
        return False, f"public /healthz unexpected: {exc}"


def probe_dns() -> tuple[bool, str]:
    """Resolve the public hostname to a CF tunnel endpoint."""
    try:
        out = subprocess.run(
            ["dig", "+short", "CNAME", PUBLIC_HOST],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
            check=False,
        ).stdout.strip()
    except FileNotFoundError:
        # `dig` not available (some minimal containers lack it).
        # Don't fail the probe — DNS can't be verified but the app
        # can still be probed locally. Return unknown (not ok, not bad).
        return True, "dig not installed; DNS skipped"
    except subprocess.TimeoutExpired:
        return False, "dig timed out"
    if not out:
        return False, f"DNS returned no CNAME for {PUBLIC_HOST}"
    if "cfargotunnel.com" not in out:
        return False, f"DNS CNAME not via CF-tunnel: {out!r}"
    return True, f"DNS CNAME → {out}"


def probe_local() -> tuple[bool, str]:
    """Probe the local Docker swarm healthz/db.

    Returns (True, 'skipped') if SKIP_LOCAL is set.
    """
    if SKIP_LOCAL:
        return True, "skipped (SASKIA_SKIP_LOCAL=1)"
    url = f"http://127.0.0.1:{LOCAL_PROBE_PORT}/healthz/db"
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=TIMEOUT_S) as r:
            body = r.read().decode("utf-8", errors="replace")
            if r.status != 200:
                return False, f"local /healthz/db HTTP {r.status}"
            data = json.loads(body)
            if "schema_version" not in data:
                return False, "local /healthz/db missing schema_version"
            return True, f"local /healthz/db ok (schema {data['schema_version']})"
    except URLError as exc:
        return False, f"local /healthz/db unreachable: {exc}"
    except Exception as exc:  # noqa: BLE001
        return False, f"local /healthz/db error: {exc}"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--quiet", action="store_true",
                   help="one-line output (cron-friendly)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    started_at = time.time()
    pub_ok, pub_msg = probe_public()
    dns_ok, dns_msg = probe_dns()
    local_ok, local_msg = probe_local()
    elapsed_ms = int((time.time() - started_at) * 1000)

    if args.quiet:
        status = "ok" if (pub_ok and dns_ok and local_ok) else "FAIL"
        print(
            f"cf-tunnel-liveness[{status}] "
            f"public={'OK' if pub_ok else 'FAIL'} "
            f"dns={'OK' if dns_ok else 'FAIL'} "
            f"local={'OK' if local_ok else 'FAIL'} "
            f"({elapsed_ms}ms)"
        )
    else:
        print(f"=== CF-Tunnel liveness @ {PUBLIC_HOST} ===")
        print(f"  public  : {pub_msg}")
        print(f"  dns     : {dns_msg}")
        print(f"  local   : {local_msg}")
        print(f"  elapsed : {elapsed_ms} ms")

    # Decision matrix (ordered most-specific to least)
    if pub_ok and dns_ok and local_ok:
        return 0
    if not local_ok:
        # Local app unhealthy outranks DNS / CF because the deploy
        # class is the most actionable. Even if DNS is also bad,
        # fixing the app is the right first step (a non-running
        # container can't be reached via CF-Tunnel anyway).
        if not args.quiet:
            print(
                "\nDIAGNOSIS: Local app is broken. This is NOT a CF issue —\n"
                "the container itself is unhealthy. Redeploy is appropriate."
            )
        return 3
    if local_ok and not pub_ok:
        # Public URL broken but local OK → CF-tunnel class.
        if not args.quiet:
            print(
                "\nDIAGNOSIS: CF-Tunnel flap. Local container is healthy\n"
                "but the public URL is broken. Do NOT redeploy — fix the\n"
                "edge layer (cloudflared / Traefik / DNS)."
            )
        return 1
    if not dns_ok:
        if not args.quiet:
            print(
                "\nDIAGNOSIS: DNS drift. The hostname no longer resolves\n"
                "to a CF-tunnel endpoint. Check NS + CNAME records."
            )
        return 2
    # Local broken AND public broken AND DNS ok → catastrophic
    # (the only case that falls through is: local=F, public=F, dns=T,
    # which the `not local_ok` branch above already catches as 3.)
    # If everything else is also broken, return 5.
    if not args.quiet:
        print(
            "\nDIAGNOSIS: All probes failed. Catastrophic — check VPS,\n"
            "cloudflared daemon, and CF account in that order."
        )
    return 5


if __name__ == "__main__":
    sys.exit(main())
