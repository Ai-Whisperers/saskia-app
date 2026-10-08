"""Alert dispatch (Tier 8.4, 2026-10-01) + Batch B3 extraction (2026-10-07).

Single entry point for sending anomaly / failure alerts. Centralised
so:
- Tests mock one function, not the email module
- Future changes (rate-limiting, batching, on-call rotation) live in
  one place
- The ``send_alert`` import path is stable

This module is intentionally tiny. The detectors (eod_anomaly) and
the trigger points (main.py lifespan, backup_scheduler hooks) live
elsewhere; this is the glue.

Batch B3 (2026-10-07): the rate limit (``MAX_ALERTS_PER_DAY``) is
now operator-tunable via the SettingsKV registry (key
``alerts.max_per_day``, ``SettingGroup.ALERTS``). ``dispatch_anomalies``
accepts an optional ``max_per_day`` int kwarg that overrides the
default when provided.
"""

from __future__ import annotations

from typing import Iterable, Optional

from app.observability.email import send_alert
from app.services.eod_anomaly import Anomaly

# Batch B3 (2026-10-07): defaults for the operator-tunable rate limit.
# Mirror of the entry in app/rms/settings.py:SETTINGS under
# SettingGroup.ALERTS.
DEFAULT_ALERTS_CONFIG: dict[str, int] = {
    "max_per_day": 50,  # rate limit on dispatch_anomalies()
}

# Backward-compat constant. New code should use DEFAULT_ALERTS_CONFIG
# or pass max_per_day= explicitly. Kept because external callers
# (scripts/notification tests, monitor scripts) import this name.
MAX_ALERTS_PER_DAY = DEFAULT_ALERTS_CONFIG["max_per_day"]


def dispatch_anomalies(
    anomalies: Iterable[Anomaly],
    *,
    max_per_day: Optional[int] = None,
) -> int:
    """Send one email per anomaly. Returns the count dispatched.

    Args:
      anomalies: iterable of Anomaly objects (typically the result
        of ``eod_anomaly.detect_anomalies``).
      max_per_day: optional override for the rate limit. When None,
        DEFAULT_ALERTS_CONFIG["max_per_day"] is used. Production code
        should pass ``alerts_cfg["max_per_day"]`` from
        ``get_alerts_config(session)``.

    Returns:
      Number of anomalies actually dispatched (capped at max_per_day).
    """
    cap = max_per_day if max_per_day is not None else DEFAULT_ALERTS_CONFIG["max_per_day"]
    n = 0
    for a in anomalies:
        if n >= cap:
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
    "DEFAULT_ALERTS_CONFIG",
    "MAX_ALERTS_PER_DAY",
    "dispatch_anomalies",
    "dispatch_failure",
]
