"""Alert dispatch (Tier 8.4, 2026-10-01).

Single entry point for sending anomaly / failure alerts. Centralised
so:
- Tests mock one function, not the email module
- Future changes (rate-limiting, batching, on-call rotation) live in
  one place
- The ``send_alert`` import path is stable

This module is intentionally tiny. The detectors (eod_anomaly) and
the trigger points (main.py lifespan, backup_scheduler hooks) live
elsewhere; this is the glue.
"""

from __future__ import annotations

from typing import Iterable

from app.observability.email import send_alert
from app.services.eod_anomaly import Anomaly

# Maximum alerts per process per day. Prevents a runaway loop from
# spamming the operator (e.g. a tight retry loop after a 500).
MAX_ALERTS_PER_DAY = 50


def dispatch_anomalies(anomalies: Iterable[Anomaly]) -> int:
    """Send one email per anomaly. Returns the count dispatched."""
    n = 0
    for a in anomalies:
        if n >= MAX_ALERTS_PER_DAY:
            break
        subject, body, severity = a.to_email()
        if send_alert(subject=subject, body=body, severity=severity):
            n += 1
    return n


def dispatch_failure(
    *,
    title: str,
    body: str,
    severity: str = "error",
) -> bool:
    """Single failure email. Returns True if the path ran (always True
    in dry-run / disabled mode; True/False from real send)."""
    return send_alert(
        subject=title,
        body=body,
        severity=severity,  # type: ignore[arg-type]
    )


__all__ = [
    "MAX_ALERTS_PER_DAY",
    "dispatch_anomalies",
    "dispatch_failure",
]
