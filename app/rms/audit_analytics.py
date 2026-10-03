"""app/rms/audit_analytics.py — BACKLOG #30: AuditLog analytics.

Aggregates the audit log for an operator dashboard. Pure read-only —
never writes to /audit_log. Designed for a quick /admin/security-audit page
that complements the row-level /auditoria viewer.

Reports:

  - top_ips_by_event_count:  IP most-frequent events in window
  - top_actions_by_count:    count of events by action
  - operator_activity:       per-user event counts + last-seen + distinct actions
  - login_failure_rate:      login.failure / (login.success + login.failure)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.rms.models_legacy import AuditLog


@dataclass(frozen=True)
class IpCount:
    ip: str
    n_events: int
    n_logins_failed: int
    n_logins_success: int


@dataclass(frozen=True)
class ActionCount:
    action: str
    n_events: int


@dataclass(frozen=True)
class OperatorActivity:
    user_id: str
    n_events: int
    distinct_actions: int
    last_seen_at: datetime | None


@dataclass
class AuditAnalyticsReport:
    period_days: int
    n_events: int
    top_ips: list[IpCount] = field(default_factory=list)
    top_actions: list[ActionCount] = field(default_factory=list)
    operator_activity: list[OperatorActivity] = field(default_factory=list)
    login_failure_rate: float | None = None  # 0.0..1.0; None when no login events

    @property
    def n_logins_total(self) -> int:
        return sum(
            1 for ip in self.top_ips for _ in range(1)
        )  # placeholder; computed properly in helpers below

    @property
    def n_login_failures(self) -> int:
        return sum(ip.n_logins_failed for ip in self.top_ips)

    @property
    def n_login_successes(self) -> int:
        return sum(ip.n_logins_success for ip in self.top_ips)


def compute_audit_analytics(
    session: Session,
    days: int = 30,
    top_n_ips: int = 10,
    top_n_actions: int = 15,
    top_n_operators: int = 10,
) -> AuditAnalyticsReport:
    """Aggregate the audit log for the last `days` days."""
    if days < 1 or days > 365:
        raise ValueError(f"days out of range (1..365): {days}")

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    base_q = session.query(AuditLog).filter(AuditLog.occurred_at >= cutoff)

    n_events = base_q.count()

    # Top IPs (by event count, with login.* breakdown).
    ip_rows = (
        session.query(
            AuditLog.ip,
            func.count(AuditLog.id).label("n"),
            func.sum(
                case((AuditLog.action == "login.failure", 1), else_=0)
            ).label("n_fail"),
            func.sum(
                case((AuditLog.action == "login.success", 1), else_=0)
            ).label("n_succ"),
        )
        .filter(AuditLog.occurred_at >= cutoff)
        .filter(AuditLog.ip.isnot(None))
        .group_by(AuditLog.ip)
        .order_by(func.count(AuditLog.id).desc())
        .limit(top_n_ips)
        .all()
    )
    top_ips = [
        IpCount(
            ip=ip,
            n_events=int(n or 0),
            n_logins_failed=int(n_fail or 0),
            n_logins_success=int(n_succ or 0),
        )
        for ip, n, n_fail, n_succ in ip_rows
    ]

    # Top actions.
    act_rows = (
        session.query(
            AuditLog.action,
            func.count(AuditLog.id).label("n"),
        )
        .filter(AuditLog.occurred_at >= cutoff)
        .group_by(AuditLog.action)
        .order_by(func.count(AuditLog.id).desc())
        .limit(top_n_actions)
        .all()
    )
    top_actions = [ActionCount(action=a, n_events=int(n or 0)) for a, n in act_rows]

    # Per-operator activity (only authenticated events).
    op_rows = (
        session.query(
            AuditLog.user_id,
            func.count(AuditLog.id).label("n"),
            func.count(func.distinct(AuditLog.action)).label("distinct_actions"),
            func.max(AuditLog.occurred_at).label("last_seen"),
        )
        .filter(AuditLog.occurred_at >= cutoff)
        .filter(AuditLog.user_id.isnot(None))
        .group_by(AuditLog.user_id)
        .order_by(func.count(AuditLog.id).desc())
        .limit(top_n_operators)
        .all()
    )
    op_activity = [
        OperatorActivity(
            user_id=str(uid or ""),
            n_events=int(n or 0),
            distinct_actions=int(distinct_actions or 0),
            last_seen_at=last_seen,
        )
        for uid, n, distinct_actions, last_seen in op_rows
    ]

    # Login failure rate (over total login attempts in window).
    login_rows = (
        session.query(
            AuditLog.action,
            func.count(AuditLog.id).label("n"),
        )
        .filter(AuditLog.occurred_at >= cutoff)
        .filter(AuditLog.action.in_(["login.success", "login.failure"]))
        .group_by(AuditLog.action)
        .all()
    )
    login_total = sum(int(n or 0) for _, n in login_rows)
    login_fail = sum(
        int(n or 0) for a, n in login_rows if a == "login.failure"
    )
    failure_rate = (
        round(login_fail / login_total, 4) if login_total > 0 else None
    )

    return AuditAnalyticsReport(
        period_days=days,
        n_events=n_events,
        top_ips=top_ips,
        top_actions=top_actions,
        operator_activity=op_activity,
        login_failure_rate=failure_rate,
    )


__all__ = [
    "ActionCount",
    "AuditAnalyticsReport",
    "IpCount",
    "OperatorActivity",
    "compute_audit_analytics",
]
