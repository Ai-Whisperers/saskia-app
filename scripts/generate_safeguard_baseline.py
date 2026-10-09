"""Regenerate docs/security/safeguard-baseline.json from current findings.

The file uses fastapi-safeguard's native format: a top-level
``accepted_findings`` list of exact finding texts (what the scanner reads),
plus a ``rationales`` mapping (documentation for operators — ignored by the
scanner).

Usage:
    uv run --group tooling-tier2 python scripts/generate_safeguard_baseline.py [--check]

--check exits non-zero if NEW (un-baselined) findings exist — used by CI so
the baseline can't silently rot.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "app")

BASELINE_PATH = Path("docs/security/safeguard-baseline.json")

RATIONALES: dict[str, str] = {
    "/static/combo.js": "Public static asset; no auth by design.",
    "/favicon.svg": "Public static asset; no auth by design.",
    "/favicon.ico": "Public static asset; no auth by design.",
    "/proveedores": "Spanish alias: 303 redirect to /suppliers (which is authed); no data served.",
    "/metrics": "Prometheus endpoint; bound to 127.0.0.1 behind nginx, only mounted when PROMETHEUS_ENABLED=true.",
}
DEFAULT_RATIONALE = "Accepted by operator; see docs/operations/2026-10-09-tier2-adoption.md."


def _rationale_for(text: str) -> str:
    for route, rationale in RATIONALES.items():
        if route in text:
            return rationale
    return DEFAULT_RATIONALE


def main() -> int:
    from fastapi_safeguard import FastAPISafeguard, recommended_checks

    from app.rms.main import create_app

    app = create_app()
    sg = FastAPISafeguard(
        checks=recommended_checks(),
        baseline_path=str(BASELINE_PATH),
        update_baseline=False,
    )
    result = sg.collect(app)

    if "--check" in sys.argv:
        new = list(result.new)
        if new:
            print(f"FAIL: {len(new)} NEW safeguard findings not in baseline:")
            for f in new:
                print(f"  - {f.text}")
            print(
                "Fix them, or re-accept by running: "
                "uv run --group tooling-tier2 python scripts/generate_safeguard_baseline.py"
            )
            return 1
        print(
            f"OK: 0 new findings ({len(result.accepted_findings)} accepted, "
            f"{result.route_count} routes scanned)"
        )
        return 0

    findings = sorted({f.text for f in result.findings})
    payload = {
        "schema_version": 1,
        "generated_at": "2026-10-09",
        "generator": "scripts/generate_safeguard_baseline.py",
        "summary": (
            f"{len(findings)} accepted findings. Every entry needs a rationale; "
            f"regenerate after triage, review the diff in the PR."
        ),
        "accepted_findings": findings,
        "rationales": {t: _rationale_for(t) for t in findings},
    }
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"Baseline written: {BASELINE_PATH} ({len(findings)} findings)")
    for t in findings:
        print(f"  - {t}")
        print(f"      rationale: {_rationale_for(t)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
