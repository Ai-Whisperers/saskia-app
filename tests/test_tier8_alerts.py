"""Tier 8.4 (2026-10-01) — Alert dispatch (Resend wrapper).

Smoke tests for ``app.observability.alerts.dispatch_anomalies`` and
``dispatch_failure``. Verifies that the dispatch function calls
``send_alert`` once per anomaly and respects MAX_ALERTS_PER_DAY.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.observability import alerts
from app.services.eod_anomaly import Anomaly


def _anomaly(key: str, severity: str = "warn") -> Anomaly:
    return Anomaly(
        key=key,
        severity=severity,  # type: ignore[arg-type]
        title=f"title-{key}",
        body=f"body-{key}",
    )


def test_dispatch_anomalies_calls_send_alert_per_item() -> None:
    """Each Anomaly in the list triggers exactly one ``send_alert``
    call with the right args."""
    items = [_anomaly("eod.voided_rate"), _anomaly("eod.uninvoiced_factura", "error")]
    with patch("app.observability.alerts.send_alert", return_value=True) as mock:
        count = alerts.dispatch_anomalies(items)
    assert count == 2
    assert mock.call_count == 2
    first_call = mock.call_args_list[0]
    assert first_call.kwargs["subject"] == "title-eod.voided_rate"
    assert first_call.kwargs["body"] == "body-eod.voided_rate"
    assert first_call.kwargs["severity"] == "warn"


def test_dispatch_anomalies_respects_max() -> None:
    """When the list exceeds MAX_ALERTS_PER_DAY, only the first N
    are dispatched. The remaining are dropped (no flood)."""
    items = [_anomaly(f"eod.k{i}") for i in range(alerts.MAX_ALERTS_PER_DAY + 10)]
    with patch("app.observability.alerts.send_alert", return_value=True) as mock:
        count = alerts.dispatch_anomalies(items)
    assert count == alerts.MAX_ALERTS_PER_DAY
    assert mock.call_count == alerts.MAX_ALERTS_PER_DAY


def test_dispatch_anomalies_empty_list() -> None:
    with patch("app.observability.alerts.send_alert", return_value=True) as mock:
        assert alerts.dispatch_anomalies([]) == 0
    assert mock.call_count == 0


def test_dispatch_anomalies_counts_only_successful_sends() -> None:
    """A failing send_alert returns False; dispatch_anomalies should
    count only the ones that succeeded."""
    items = [_anomaly("a"), _anomaly("b"), _anomaly("c")]

    def fake_send(subject, body, severity, **_):
        return subject != "title-b"  # one fails

    with patch("app.observability.alerts.send_alert", side_effect=fake_send):
        count = alerts.dispatch_anomalies(items)
    assert count == 2


def test_dispatch_failure_passes_through() -> None:
    with patch("app.observability.alerts.send_alert", return_value=True) as mock:
        result = alerts.dispatch_failure(
            title="migrate fail",
            body="oops",
            severity="error",
        )
    assert result is True
    mock.assert_called_once_with(
        subject="migrate fail", body="oops", severity="error"
    )
