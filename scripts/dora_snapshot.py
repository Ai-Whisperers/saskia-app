#!/usr/bin/env python3
"""scripts/dora_snapshot.py — snapshot the 4 DORA metrics for the current week.

Pulls data from the GitHub API + local git log + the VPS deploy state, then
writes a markdown snapshot to docs/operations/dora-snapshots/<iso-week>.md.

The 4 DORA metrics:
  1. Deployment Frequency   — count of successful production deploys / period
  2. Lead Time for Changes  — median PR open-to-merged time
  3. Change Failure Rate    — deploys followed by a rollback within 24h / total
  4. Mean Time to Recovery  — time from first bad deploy to rollback

Usage:
  # Default: snapshot the current ISO week (Monday-Sunday)
  uv run python scripts/dora_snapshot.py

  # Snapshot a specific week
  uv run python scripts/dora_snapshot.py --iso-week=2026-W41

  # Snapshot a date range
  uv run python scripts/dora_snapshot.py --since=2026-10-09 --until=2026-10-16

  # Dry run (print, don't write)
  uv run python scripts/dora_snapshot.py --dry-run

Dependencies: stdlib only (urllib + json + subprocess). The `gh` CLI is used
to talk to the GitHub API because auth is pre-configured on the operator
machine; in CI the GH_TOKEN env var is used instead via `gh auth`.

Per docs/operations/dora-2026-Q4.md (the Q4 dashboard). Run weekly on
Monday 09:00 UTC from .github/workflows/dora-snapshot.yml.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS_DIR = ROOT / "docs" / "operations" / "dora-snapshots"


def gh_api(endpoint: str) -> dict | list:
    """Run `gh api <endpoint>` and return the parsed JSON. Stdlib-only."""
    result = subprocess.run(
        ["gh", "api", endpoint], capture_output=True, text=True, check=True, timeout=30
    )
    return json.loads(result.stdout)


def iso_week_range(iso_week: str) -> tuple[dt.date, dt.date]:
    """Convert 'YYYY-Www' to (Monday, Sunday) of that week."""
    year, w = iso_week.split("-W")
    monday = dt.date.fromisocalendar(int(year), int(w), 1)
    sunday = monday + dt.timedelta(days=6)
    return monday, sunday


def current_iso_week() -> str:
    today = dt.date.today()
    return f"{today.isocalendar()[0]}-W{today.isocalendar()[1]:02d}"


def fetch_deployments(since: dt.date, until: dt.date) -> list[dict]:
    """Count CalVer tag pushes in [since, until] as proxy for prod deploys."""
    # List all tags with a date prefix, filter to the range
    r = subprocess.run(
        [
            "git",
            "tag",
            "--list",
            "v[0-9]*",
            "--sort=-creatordate",
            "--format=%(creatordate:iso-strict) %(refname:short)",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )
    out = []
    for line in r.stdout.splitlines():
        m = re.match(r"^(\S+)\s+(v\S+)$", line)
        if not m:
            continue
        date_str, tag = m.group(1), m.group(2)
        tag_date = dt.datetime.fromisoformat(date_str).date()
        if since <= tag_date <= until:
            out.append({"tag": tag, "date": tag_date.isoformat()})
    return out


def fetch_lead_times(since: dt.date, until: dt.date) -> list[float]:
    """Median PR-cycle-time in hours (open-to-merged).

    Uses the GitHub search API (more reliable than the private pulls
    endpoint for cross-page pagination) to find merged PRs in [since, until].
    """
    # Search returns at most 1000 results per query; for a 1-week window
    # that's plenty. For longer windows, paginate.
    out: list[float] = []
    page = 1
    while True:
        endpoint = (
            f"search/issues?q=repo:Ai-Whisperers/saskia-app"
            f"+is:pr+is:merged"
            f"+merged:{since.isoformat()}..{until.isoformat()}"
            f"&sort=updated&order=desc&per_page=100&page={page}"
        )
        try:
            data = gh_api(endpoint) or {}
        except subprocess.CalledProcessError:
            break
        items = data.get("items") or []
        if not items:
            break
        for pr in items:
            # Search API returns PRs with `merged_at` at the top level
            # (since the search index merges PR + issue views). Older
            # responses had it nested under `pull_request.merged_at`;
            # accept both for forward compat.
            merged_at = pr.get("merged_at") or ((pr.get("pull_request") or {}).get("merged_at"))
            if not merged_at:
                continue
            created = dt.datetime.fromisoformat(pr["created_at"].rstrip("Z"))
            merged = dt.datetime.fromisoformat(merged_at.rstrip("Z"))
            delta_h = (merged - created).total_seconds() / 3600
            out.append(delta_h)
        if len(items) < 100:
            break
        page += 1
        if page > 10:  # safety cap
            break
    return sorted(out)


def median(xs: list[float]) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    n = len(xs)
    if n % 2:
        return xs[n // 2]
    return (xs[n // 2 - 1] + xs[n // 2]) / 2


def fetch_change_failures(since: dt.date, until: dt.date) -> tuple[int, int]:
    """Count of prod deploys that were reverted/rolled back within 24h.

    Returns (failed_count, total_count).
    """
    # Cheap heuristic: count `revert:` commits in [since, until] as a
    # lower bound on rollback count. We compare against prod tag pushes
    # in the same window.
    r = subprocess.run(
        [
            "git",
            "log",
            "--oneline",
            f"--since={since.isoformat()}",
            f"--until={(until + dt.timedelta(days=1)).isoformat()}",
            "--grep=^revert:",
            "--grep=^Revert",
            "--regexp-ignore-case",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )
    revert_count = sum(1 for line in r.stdout.splitlines() if line.strip())
    deploys = fetch_deployments(since, until)
    return revert_count, len(deploys)


def fetch_mttr(since: dt.date, until: dt.date) -> float:
    """Estimate MTTR: time between a bad deploy (revert: in next 24h) and
    the revert commit.

    The actual production MTTR is harder to capture from git alone; this
    is a best-effort estimate from the commit timestamps.
    """
    # For each revert, get the time difference between the reverted
    # commit and the revert commit. We approximate by using the
    # `Revert "..."` pattern in the revert commit message.
    r = subprocess.run(
        [
            "git",
            "log",
            "--oneline",
            "--format=%H %s",
            f"--since={since.isoformat()}",
            f"--until={(until + dt.timedelta(days=1)).isoformat()}",
            "--grep=^Revert",
            "--grep=^revert:",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )
    deltas_min = []
    for line in r.stdout.splitlines():
        # "sha Revert '...': original subject"
        m = re.match(r"^(\S+)\s+(?:Revert|revert)\s+['\"]?(.+?)['\"]?:?\s*(.*)$", line)
        if not m:
            continue
        sha = m.group(1)
        # Revert commit timestamp; the parent (sha^) is the bad deploy.
        # Both can fail silently on missing refs.
        try:
            revert_ts = int(
                subprocess.run(
                    ["git", "show", "-s", "--format=%ct", sha],
                    capture_output=True,
                    text=True,
                    check=True,
                    cwd=ROOT,
                ).stdout.strip()
            )
            bad_ts = int(
                subprocess.run(
                    ["git", "log", "-1", "--format=%ct", f"{sha}^"],
                    capture_output=True,
                    text=True,
                    check=True,
                    cwd=ROOT,
                ).stdout.strip()
            )
        except (ValueError, subprocess.CalledProcessError):
            continue
        if revert_ts > bad_ts:
            deltas_min.append((revert_ts - bad_ts) / 60)
    if not deltas_min:
        return 0.0
    return sum(deltas_min) / len(deltas_min)  # mean in minutes


def fmt_metric(
    value: float, unit: str, target: float, target_unit: str = "", lower_is_better: bool = True
) -> str:
    """Format a metric value with a target and a status emoji."""
    if lower_is_better:
        status = "✅ on target" if value <= target else "⚠️ above target"
    else:
        status = "✅ on target" if value >= target else "⚠️ below target"
    if value == 0 and not lower_is_better:
        status = "✅ no failures"
    return f"{value:.1f}{unit} (target: {target}{target_unit}) {status}"


def write_snapshot(iso_week: str, monday: dt.date, sunday: dt.date, dry_run: bool) -> Path:
    deploys = fetch_deployments(monday, sunday)
    leads = fetch_lead_times(monday, sunday)
    cfr_failed, cfr_total = fetch_change_failures(monday, sunday)
    cfr_display = f"{cfr_failed} of {cfr_total}" if cfr_total else "no deploys"
    mttr_min = fetch_mttr(monday, sunday)

    deploy_count = len(deploys)
    lead_median_h = median(leads)
    cfr_pct = (cfr_failed / cfr_total * 100) if cfr_total else 0
    mttr_h = mttr_min / 60

    lines = [
        f"# DORA Snapshot — {iso_week} ({monday} → {sunday})",
        "",
        "Auto-generated by `scripts/dora_snapshot.py`. "
        "See `docs/operations/dora-2026-Q4.md` for definitions, targets, "
        "and methodology.",
        "",
        "## Metrics",
        "",
        "| Metric | Value | Target | Status |",
        "|---|---|---|---|",
        f"| Deployment Frequency (prod) | {deploy_count} | ≥2/week | "
        f"{'✅ on target' if deploy_count >= 2 else '⚠️ below target'} |",
        f"| Lead Time for Changes (median) | {lead_median_h:.1f}h | ≤24h | "
        f"{'✅ on target' if lead_median_h <= 24 else '⚠️ above target'} |",
        f"| Change Failure Rate | {cfr_pct:.0f}% ({cfr_display}) | "
        f"≤15% | {'✅ on target' if cfr_pct <= 15 else '⚠️ above target'} |",
        f"| MTTR | {mttr_h:.1f}h | ≤1h | {'✅ on target' if 0 < mttr_h <= 1 else '— n/a'} |",
        "",
        "## Prod deploys",
        "",
    ]
    if deploys:
        lines.extend(f"- **{d['date']}** — `{d['tag']}`" for d in deploys)
    else:
        lines.append("_(none)_")
    lines.append("")
    lines.append("## Merged PRs in window")
    lines.append("")
    lines.append(f"Count: {len(leads)}")
    if leads:
        lines.append(
            f"Hours: min {min(leads):.1f} / median {lead_median_h:.1f} / max {max(leads):.1f}"
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"_Generated: {dt.datetime.now(dt.timezone.utc).isoformat()}_")

    out = "\n".join(lines) + "\n"

    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SNAPSHOTS_DIR / f"{iso_week}.md"
    if dry_run:
        print(out)
        print(f"\n# (dry run; would write to {out_path})")
    else:
        out_path.write_text(out)
        print(f"Wrote {out_path} ({out_path.stat().st_size} bytes)")
    return out_path


def main() -> int:
    p = argparse.ArgumentParser(
        description="Snapshot the 4 DORA metrics for the current week.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--iso-week", help="e.g. 2026-W41 (default: current week)")
    p.add_argument("--since", help="YYYY-MM-DD (overrides --iso-week)")
    p.add_argument("--until", help="YYYY-MM-DD (overrides --iso-week)")
    p.add_argument("--dry-run", action="store_true", help="print the snapshot, don't write it")
    args = p.parse_args()

    if args.since and args.until:
        monday = dt.date.fromisoformat(args.since)
        sunday = dt.date.fromisoformat(args.until)
        iso_week = f"{monday.isocalendar()[0]}-W{monday.isocalendar()[1]:02d}"
    elif args.iso_week:
        monday, sunday = iso_week_range(args.iso_week)
        iso_week = args.iso_week
    else:
        iso_week = current_iso_week()
        monday, sunday = iso_week_range(iso_week)

    write_snapshot(iso_week, monday, sunday, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
