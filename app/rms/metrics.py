"""app/rms/metrics.py — minimal dependency-free Prometheus metrics.

Phase 14 (observability): replaces the existing silent failure mode
with a /metrics endpoint that exposes request count, latency, and
DB health in the Prometheus text exposition format. No external deps
— the format is just a handful of text conventions.

Metrics emitted:
- rms_requests_total{path, method, status} — counter
- rms_request_duration_seconds{path, method} — histogram (bucketed)
- rms_db_up — gauge (1 if SQLite WAL pragma succeeds, else 0)
- rms_app_info{version, schema_version} — info gauge (always 1)

Why not prometheus-fastapi-instrumentator? That library is great but
pulls in starlette_exporter + a few transitive deps. For this app we
need ~20 lines that work without them. Operators scrape /metrics from
a Prometheus server if they want to; otherwise the endpoint just exists.

Histogram buckets: 5ms / 10ms / 25ms / 50ms / 100ms / 250ms / 500ms
/ 1s / 2.5s / 5s / +Inf — covers the realistic web range for an RMS app
running on a single VPS.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any

# Histogram bucket boundaries (Prometheus convention: bucket is upper-bound,
# last bucket is +Inf which we represent as a sentinel larger than any
# expected duration).
_BUCKETS_MS: tuple[float, ...] = (5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000)
_BUCKETS_S: tuple[float, ...] = tuple(b / 1000 for b in _BUCKETS_MS)

# Lock for the in-memory counters/histograms. The middleware runs on
# every request; cheap operations and a debug path are fine with this
# lock.
_lock = threading.Lock()
_count_total: dict[tuple[str, str, int], int] = defaultdict(int)
# Histogram: (path, method) -> [<bucket_1>, ..., <bucket_N>, <+Inf>, <sum>, <count>]
# Layout: N buckets (one per _BUCKETS_S) + 1 +Inf + 1 sum + 1 count = N+3
_hist: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0] * (len(_BUCKETS_S) + 3))
_db_up: int = 1
_app_info: dict[str, str] = {}


def record_request(path: str, method: str, status: int, duration_s: float) -> None:
    """Called by the metrics middleware on every response."""
    # Normalize path so /ventas/123 and /ventas/456 don't fragment.
    norm = _normalize_path(path)
    key_total = (norm, method, status)
    key_hist = (norm, method)
    with _lock:
        _count_total[key_total] += 1
        h = _hist[key_hist]
        # Increment bucket counts (≤ dms)
        for i, ub in enumerate(_BUCKETS_S):
            if duration_s <= ub:
                h[i] += 1.0
        # +Inf bucket: always count
        h[len(_BUCKETS_S)] += 1.0
        # Sum + count (last two slots)
        h[-2] += duration_s
        h[-1] += 1.0


def set_db_up(up: bool) -> None:
    global _db_up
    with _lock:
        _db_up = 1 if up else 0


def set_app_info(version: str, schema_version: int) -> None:
    global _app_info
    with _lock:
        _app_info = {"version": version, "schema_version": str(schema_version)}


def render() -> str:
    """Render the Prometheus text exposition format."""
    lines: list[str] = []
    with _lock:
        # --- rms_requests_total ---
        lines.append("# HELP rms_requests_total Total HTTP requests handled.")
        lines.append("# TYPE rms_requests_total counter")
        # Stable sort: by path then method then status
        for (path, method, status), count in sorted(_count_total.items()):
            lines.append(
                f'rms_requests_total{{path="{_escape(path)}",method="{_escape(method)}",status="{status}"}} {count}'
            )

        # --- rms_request_duration_seconds ---
        lines.append("# HELP rms_request_duration_seconds HTTP request latency.")
        lines.append("# TYPE rms_request_duration_seconds histogram")
        inf_idx = len(_BUCKETS_S)  # +Inf bucket position
        sum_idx = len(_BUCKETS_S) + 1
        count_idx = len(_BUCKETS_S) + 2
        # Group by (path, method)
        for (path, method), h in sorted(_hist.items()):
            for i, ub in enumerate(_BUCKETS_S):
                le = _format_le(le=ub)
                lines.append(
                    f'rms_request_duration_seconds_bucket{{path="{_escape(path)}",method="{_escape(method)}",le="{le}"}} {int(h[i])}'
                )
            # +Inf bucket
            lines.append(
                f'rms_request_duration_seconds_bucket{{path="{_escape(path)}",method="{_escape(method)}",le="+Inf"}} {int(h[inf_idx])}'
            )
            # Sum
            lines.append(
                f'rms_request_duration_seconds_sum{{path="{_escape(path)}",method="{_escape(method)}"}} {_format_sum(h[sum_idx])}'
            )
            # Count
            lines.append(
                f'rms_request_duration_seconds_count{{path="{_escape(path)}",method="{_escape(method)}"}} {int(h[count_idx])}'
            )

        # --- rms_db_up ---
        lines.append("# HELP rms_db_up 1 if DB is reachable and writable.")
        lines.append("# TYPE rms_db_up gauge")
        lines.append(f"rms_db_up {_db_up}")

        # --- rms_app_info ---
        if _app_info:
            labels = ",".join(f'{k}="{_escape(v)}"' for k, v in sorted(_app_info.items()))
            lines.append("# HELP rms_app_info App version metadata.")
            lines.append("# TYPE rms_app_info gauge")
            lines.append(f"rms_app_info{{{labels}}} 1")

    return "\n".join(lines) + "\n"


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _format_le(le: float) -> str:
    """Format a bucket le value. <1 stays as a decimal, >=1 stays too."""
    return f"{le}"


def _format_sum(s: float) -> str:
    """Sum in seconds — use ms granularity to avoid float drift."""
    return f"{s:.6f}"


def _normalize_path(path: str) -> str:
    """Collapse numeric IDs in the path so /ventas/123 == /ventas/456.

    Cheap heuristic: replace any /<digit+> segment with /:id.
    """
    parts = path.split("/")
    out: list[str] = []
    for p in parts:
        if p.isdigit():
            out.append(":id")
        else:
            out.append(p)
    return "/".join(out)


def time_request(handler: Any):
    """Decorator for sync handlers (FastAPI sync deps) — no-op stub.

    Kept here so callers can swap to async timing later without breaking
    the import. Real timing happens in the middleware.
    """
