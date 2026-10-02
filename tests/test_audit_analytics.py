"""tests/test_audit_analytics.py — BACKLOG #30 unit tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.rms.audit_analytics import compute_audit_analytics
from app.rms.db import make_engine
from app.rms.models_legacy import AuditLog


@pytest.fixture
def audit_session():
    eng = make_engine("sqlite:///:memory:")
    from app.rms.db import init_db
    init_db(eng)
    from sqlalchemy.orm import sessionmaker
    return sessionmaker(bind=eng)()


def _add(session, **kw):
    row = AuditLog(occurred_at=datetime.now(timezone.utc), **kw)
    session.add(row)
    return row


def test_empty_db_returns_zero_report(audit_session):
    report = compute_audit_analytics(audit_session, days=30)
    assert report.n_events == 0
    assert report.top_ips == []
    assert report.top_actions == []
    assert report.operator_activity == []
    assert report.login_failure_rate is None


def test_top_ips_aggregates_correctly(audit_session):
    now = datetime.now(timezone.utc)
    for _ in range(5):
        _add(audit_session, action="login.success", ip="1.2.3.4", user_id="u1")
    for _ in range(3):
        _add(audit_session, action="login.failure", ip="1.2.3.4", user_id=None)
    for _ in range(2):
        _add(audit_session, action="sale.create", ip="5.6.7.8", user_id="u2")
    audit_session.commit()
    report = compute_audit_analytics(audit_session, days=30)
    assert report.n_events == 10
    # 1.2.3.4 is the top IP (8 events), 5.6.7.8 second (2 events)
    assert report.top_ips[0].ip == "1.2.3.4"
    assert report.top_ips[0].n_events == 8
    assert report.top_ips[0].n_logins_success == 5
    assert report.top_ips[0].n_logins_failed == 3
    assert report.top_ips[1].ip == "5.6.7.8"
    assert report.top_ips[1].n_events == 2


def test_top_actions_aggregated(audit_session):
    for _ in range(4):
        _add(audit_session, action="sale.create", ip="1.1.1.1", user_id="u1")
    for _ in range(2):
        _add(audit_session, action="sale.void", ip="1.1.1.1", user_id="u1")
    _add(audit_session, action="login.success", ip="1.1.1.1", user_id="u1")
    audit_session.commit()
    report = compute_audit_analytics(audit_session, days=30)
    # Top action is sale.create with 4
    assert report.top_actions[0].action == "sale.create"
    assert report.top_actions[0].n_events == 4
    # sale.void is next with 2
    assert any(a.action == "sale.void" and a.n_events == 2 for a in report.top_actions)


def test_operator_activity(audit_session):
    # u1: 5 events (sale.create + sale.void + login.success), u2: 2 events
    for _ in range(3):
        _add(audit_session, action="sale.create", user_id="u1")
    _add(audit_session, action="sale.void", user_id="u1")
    _add(audit_session, action="login.success", user_id="u1")
    for _ in range(2):
        _add(audit_session, action="sale.create", user_id="u2")
    audit_session.commit()
    report = compute_audit_analytics(audit_session, days=30)
    assert len(report.operator_activity) == 2
    top = report.operator_activity[0]
    assert top.user_id == "u1"
    assert top.n_events == 5
    assert top.distinct_actions == 3  # sale.create + sale.void + login.success
    assert top.last_seen_at is not None


def test_login_failure_rate_computed(audit_session):
    for _ in range(8):
        _add(audit_session, action="login.success", ip="1.1.1.1")
    for _ in range(2):
        _add(audit_session, action="login.failure", ip="1.1.1.1")
    audit_session.commit()
    report = compute_audit_analytics(audit_session, days=30)
    assert report.login_failure_rate == 0.2


def test_login_failure_rate_zero_no_events(audit_session):
    """When there are no login events, rate is None (not 0.0)."""
    _add(audit_session, action="sale.create", ip="1.1.1.1")
    audit_session.commit()
    report = compute_audit_analytics(audit_session, days=30)
    assert report.login_failure_rate is None


def test_period_filter_excludes_old_events(audit_session):
    """Events older than the window are excluded."""
    old = datetime.now(timezone.utc) - timedelta(days=60)
    # Need to insert with explicit old timestamp
    audit_session.add(AuditLog(
        occurred_at=old, action="login.success", ip="1.1.1.1", user_id="u1",
    ))
    for _ in range(3):
        _add(audit_session, action="sale.create", user_id="u1")
    audit_session.commit()
    report = compute_audit_analytics(audit_session, days=30)
    # Only the 3 new sale.create events counted
    assert report.n_events == 3


def test_invalid_days_raises(audit_session):
    with pytest.raises(ValueError):
        compute_audit_analytics(audit_session, days=0)
    with pytest.raises(ValueError):
        compute_audit_analytics(audit_session, days=400)


def test_top_n_limits(audit_session):
    """Top-N options truncate the lists."""
    # Just ensure top_n_ips limits the list
    for i in range(15):
        _add(audit_session, action="sale.create", ip=f"192.168.0.{i}")
    audit_session.commit()
    report = compute_audit_analytics(audit_session, days=30, top_n_ips=3)
    assert len(report.top_ips) == 3