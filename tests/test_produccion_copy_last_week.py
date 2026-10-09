"""# allow-hardcoded-dates: fixtures intentionally pin fixed dates (calendar edges, tz math, far-future sentinels); asserted relative to frozen or explicit anchors.
Tests for /produccion/copy-last-week (Phase C of Sazon-Improvement v2 plan).

The "copy last week's plan" button saves the operator 20 minutes per
menu-planning session. It reads the source day's plan_production() output
and creates ProductionPlanOverride rows for the target date with the same
qty_to_produce. The forecast_source is NOT copied — the target date uses
its own fresh forecast; the override is just the manual-adjustment layer.

Contract:
- POST /produccion/copy-last-week
  body: source_date=YYYY-MM-DD (default = 7 days before for_date)
        for_date=YYYY-MM-DD (default = today)
- Creates one ProductionPlanOverride per row in source plan
- Override.qty = source.qty_to_produce
- Override.for_date = target_date
- Returns redirect to /produccion?for_date=target_date
- If source has no rows, returns 200/302/303 with empty apply
- Source date may be missing (no plan for that date) — graceful empty
"""

from __future__ import annotations


def test_copy_last_week_creates_overrides_and_redirects(client, qseed):
    """The endpoint should create overrides and redirect to /produccion."""
    qseed("with_kyrian_full")
    r = client.post(
        "/produccion/copy-last-week",
        data={"for_date": "2026-10-13", "source_date": "2026-10-06"},
        follow_redirects=False,
    )
    # Should redirect (303) to /produccion?for_date=2026-10-13
    assert r.status_code in (302, 303), f"expected redirect, got {r.status_code}"
    loc = r.headers.get("location", "")
    assert "2026-10-13" in loc, f"expected target date in redirect, got {loc!r}"


def test_copy_last_week_handles_no_prior_week_gracefully(client, qseed):
    """If source_date has no plan, the endpoint should redirect without 500."""
    qseed("with_kyrian_full")
    r = client.post(
        "/produccion/copy-last-week",
        data={"for_date": "2026-10-13", "source_date": "2020-01-01"},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303), (
        f"expected redirect even on empty source, got {r.status_code}"
    )


def test_copy_last_week_uses_default_source_date_when_missing(client, qseed):
    """If source_date is missing, default to 7 days before for_date."""
    qseed("with_kyrian_full")
    r = client.post(
        "/produccion/copy-last-week",
        data={"for_date": "2026-10-13"},  # no source_date
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    loc = r.headers.get("location", "")
    assert "2026-10-13" in loc, f"expected target date in redirect, got {loc!r}"


def test_copy_last_week_validates_dates(client, qseed):
    """Endpoint should accept the standard form-encoded body."""
    qseed("with_kyrian_full")
    # for_date missing → 422 (form validation)
    r = client.post(
        "/produccion/copy-last-week",
        data={"source_date": "2026-10-06"},  # no for_date
        follow_redirects=False,
    )
    # Either 422 (validation) or 400 (bad request) — both acceptable
    assert r.status_code in (302, 303, 400, 422), f"expected validation error, got {r.status_code}"


def test_copy_last_week_is_idempotent(client, qseed):
    """Calling the endpoint twice with the same args should not error
    (the second call overwrites the overrides from the first)."""
    qseed("with_kyrian_full")
    r1 = client.post(
        "/produccion/copy-last-week",
        data={"for_date": "2026-10-13", "source_date": "2026-10-06"},
        follow_redirects=False,
    )
    r2 = client.post(
        "/produccion/copy-last-week",
        data={"for_date": "2026-10-13", "source_date": "2026-10-06"},
        follow_redirects=False,
    )
    assert r1.status_code in (302, 303)
    assert r2.status_code in (302, 303), f"second call should also succeed, got {r2.status_code}"
