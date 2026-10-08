"""P-39: /eod must surface anomaly summary inline.

Currently /eod is a clean page (line 1-50+ of eod.html) with no anomaly
mention. The anomalies page (/eod/anomalies/run) is separate. A cashier
who needs to close the day has no signal that anomalies exist.

Fix: add an inline anomaly banner at the top of /eod with a link to
the full anomalies page. The banner shows count (e.g., "3 anomalías")
or a "Sin anomalías" success state.

Acceptance:
  - /eod contains either an "anomalías" / "anomalías:" string with a
    count, OR a "Sin anomalías" success state.
  - A link to /eod/anomalies (or similar route) is present.
"""

from __future__ import annotations


def test_eod_has_inline_anomaly_summary(client):
    """P-39: /eod shows anomaly count or success state inline."""
    r = client.get("/eod")
    assert r.status_code == 200
    body = r.text

    # Anomaly text in the body.
    has_anomaly_text = (
        "anomalía" in body.lower() or "anomalia" in body.lower() or "sin anomalías" in body.lower()
    )
    assert has_anomaly_text, (
        "expected anomaly summary text on /eod (e.g. '3 anomalías' or 'Sin anomalías')"
    )

    # A link to the anomalies page or a count of detected anomalies.
    # We accept any of these:
    has_link = (
        "/eod/anomalies" in body or 'id="eod-anomaly-count"' in body or "data-eod-anomalies" in body
    )
    assert has_link, "expected a link to /eod/anomalies or a count element on /eod"
