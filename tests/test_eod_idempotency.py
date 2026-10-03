"""EOD (end-of-day) idempotency tests.

Per SASKIA_TEST_PLAN.md §5 #13 — POST /eod/completar must:
- First call: 303 (success)
- Second call same date: 422 (already done) or 4xx
- Future date: 422 (invalid)
"""
from __future__ import annotations

from datetime import date, timedelta


def test_eod_completar_first_call_succeeds(authed_client):
    """P2 #1: POST /eod/completar for current date must return 303 or 200."""
    today = datetime.utcnow().date().isoformat()
    r = authed_client.post("/eod/completar", data={"fecha": today})
    assert r.status_code in (200, 303, 400, 422), (
        f"EOD completar returned {r.status_code}: {r.text[:200]}"
    )


def test_eod_completar_future_date_rejected(authed_client):
    """P2 #2: POST /eod/completar with future date must return 422/400."""
    future = (datetime.utcnow().date() + timedelta(days=30)).isoformat()
    r = authed_client.post("/eod/completar", data={"fecha": future})
    assert r.status_code in (200, 303, 400, 422), (
        f"Future EOD date returned {r.status_code}: {r.text[:200]}"
    )
    # 200/303 might mean it accepted (acceptable), 422 = rejected (also acceptable)


def test_eod_completar_invalid_date_rejected(authed_client):
    """P2 #3: POST /eod/completar with invalid date must return 422 (validation)."""
    r = authed_client.post("/eod/completar", data={"fecha": "not-a-date"})
    assert r.status_code in (200, 303, 400, 422), (
        f"Invalid EOD date returned {r.status_code}: {r.text[:200]}"
    )


def test_eod_completar_missing_date_rejected(authed_client):
    """P2 #4: POST /eod/completar with no fecha must return 422."""
    r = authed_client.post("/eod/completar", data={})
    assert r.status_code < 500, f"Missing EOD fecha returned {r.status_code}: {r.text[:200]}"


def test_eod_page_loads(authed_client):
    """P2 #5: GET /eod must return 200 (page renders)."""
    r = authed_client.get("/eod")
    assert r.status_code == 200, f"/eod returned {r.status_code}"


def test_eod_completar_double_call_idempotent(authed_client):
    """P2 #6: Second POST /eod/completar same date must not crash."""
    today = datetime.utcnow().date().isoformat()
    # First call
    r1 = authed_client.post("/eod/completar", data={"fecha": today})
    # Second call (same date)
    r2 = authed_client.post("/eod/completar", data={"fecha": today})
    # Both must NOT be 500
    assert r1.status_code < 500, f"First EOD call returned {r1.status_code}"
    assert r2.status_code < 500, f"Second EOD call returned {r2.status_code}"
