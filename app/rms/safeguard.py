"""app/rms/safeguard.py — fastapi-safeguard integration (Tier 2 adoption).

What this does:
    Runs fastapi-safeguard's recommended security checks against the app
    (missing auth dependencies, CORS misconfig, debug mode, dangerous
    methods, sensitive query params, ...). 63 routes audited in ~50ms.

Activation (opt-in, mirrors SENTRY_DSN / OTEL_ENABLED pattern):
    SAFEGUARD_ENABLED=true          run checks at startup
    SAFEGUARD_FAIL_ON_FINDING=true  abort startup on NEW findings
                                    (baseline-accepted ones never abort)
    SAFEGUARD_BASELINE_PATH         default: docs/security/safeguard-baseline.json

Baseline policy:
    The baseline lists accepted findings (finding text -> rationale).
    Startup logs them as INFO; only NEW findings are surfaced as warnings
    (and can abort). Regenerate after triage:
        uv run --group tooling-tier2 python scripts/generate_safeguard_baseline.py

    Accepted (2026-10-09) — all upstream-nginx or public-asset concerns:
    - /static/combo.js, /favicon.svg, /favicon.ico  public assets, no auth by design
    - /proveedores                                   303 redirect alias to /suppliers
    - /metrics                                       Prometheus endpoint, bound to
                                                     127.0.0.1 behind nginx (never
                                                     exposed publicly; only mounted
                                                     when PROMETHEUS_ENABLED=true)

    Note: HTTPSRedirect / RateLimiting / TrustedHost middleware findings do
    not appear with recommended_checks() on this app; TLS, rate limits and
    host validation are handled upstream by nginx (deploy/nginx.conf).

References:
    docs/operations/2026-10-09-tier2-adoption.md
    docs/security/safeguard-baseline.json
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

DEFAULT_BASELINE = "docs/security/safeguard-baseline.json"


def _truthy(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def init_safeguard(app: "FastAPI") -> None:
    """Run fastapi-safeguard checks at startup. Never crashes the app.

    Behavior matrix:

    | SAFEGUARD_ENABLED | SAFEGUARD_FAIL_ON_FINDING | Effect                     |
    |-------------------|---------------------------|----------------------------|
    | unset/0           | (any)                     | no-op                      |
    | 1/true            | unset/0                   | report, never abort        |
    | 1/true            | 1/true                    | abort startup on NEW finds |
    """
    if not _truthy(os.getenv("SAFEGUARD_ENABLED")):
        return

    try:
        from fastapi_safeguard import FastAPISafeguard, recommended_checks
    except ImportError as exc:
        print(
            f"WARNING: fastapi-safeguard not installed ({exc}); "
            f"install with: uv sync --group tooling-tier2",
            file=sys.stderr,
        )
        return

    baseline_path = os.getenv("SAFEGUARD_BASELINE_PATH", DEFAULT_BASELINE)
    fail_on_new = _truthy(os.getenv("SAFEGUARD_FAIL_ON_FINDING"))

    try:
        sg = FastAPISafeguard(
            checks=recommended_checks(),
            baseline_path=baseline_path,
            update_baseline=False,
        )
        result = sg.collect(app)
    except Exception as exc:
        print(f"WARNING: safeguard scan failed: {exc}", file=sys.stderr)
        return

    accepted = list(result.accepted_findings)
    new = list(result.new)

    print(
        f"[safeguard] {result.route_count} routes scanned, "
        f"{len(result.findings)} findings "
        f"({len(accepted)} accepted, {len(new)} new)"
    )

    for f in accepted:
        print(f"[safeguard] accepted: {f.text}")

    for f in new:
        print(f"WARNING: [safeguard] new finding: {f.text}", file=sys.stderr)

    if new and fail_on_new:
        print(
            f"ERROR: [safeguard] {len(new)} NEW findings with "
            f"SAFEGUARD_FAIL_ON_FINDING=true — refusing to start. Fix them or "
            f"regenerate the baseline: {baseline_path}",
            file=sys.stderr,
        )
        raise SystemExit(1)
