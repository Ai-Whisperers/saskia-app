"""tests/test_clock_discipline.py — Sprint 1.3 verification.

Sprint 1.3 of the 2026-10-02 backend overhaul: clock/timezone discipline.

Locks the invariants that protect against the silent disasters the
audit found:

1. **No bare ``datetime.utcnow()`` or ``datetime.now()`` callsites**
   outside the ``app/rms/clock.py`` module itself. Every "now" call
   must go through ``app.rms.clock``.

2. **The clock module exposes the three canonical helpers** — ``now``
   (UTC-aware), ``today_local`` (Asuncion-aware), and ``to_utc`` /
   ``to_asuncion`` for coercion.

3. **Every helper returns a timezone-aware datetime** — never naive.
   This is what protects against the Python 3.12 deprecation of
   ``datetime.utcnow()`` and against subtle "compare naive vs aware"
   bugs at the SQLite/Postgres boundary.

Ref: plans/2026-10-02-backend-overhaul-master-plan.md, Sprint 1.3.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_clock_module_exposes_required_helpers():
    """``app.rms.clock`` provides now / today_local / to_utc / to_asuncion."""
    from app.rms import clock

    for name in ("now", "today_local", "to_utc", "to_asuncion", "utcnow"):
        assert hasattr(clock, name), f"clock module missing helper: {name}"
        assert callable(getattr(clock, name)), f"clock.{name} is not callable"


def test_now_returns_tz_aware_utc():
    """``now()`` returns a timezone-aware datetime in UTC."""
    from app.rms.clock import now

    result = now()
    assert isinstance(result, _dt.datetime)
    assert result.tzinfo is not None, "now() returned a naive datetime"
    assert result.utcoffset() == _dt.timedelta(0), (
        f"now() returned a non-UTC offset: {result.utcoffset()}"
    )


def test_today_local_returns_tz_aware_asuncion():
    """``today_local()`` returns a timezone-aware datetime in Asuncion.

    Paraguay's offset has historically been -4 (winter, no DST) or -3
    (summer DST). The IANA ``America/Asuncion`` zoneinfo returns whatever
    is current; the test only requires that the result is timezone-aware
    and matches ``ASUNCION_TZ`` for the current moment.
    """
    from app.rms.clock import ASUNCION_TZ, today_local

    result = today_local()
    assert isinstance(result, _dt.datetime)
    assert result.tzinfo is not None, "today_local() returned naive datetime"
    # Match Asuncion's actual current offset — varies between -3 (DST) and -4 (no DST)
    # but always equals what ASUNCION_TZ says for this date.
    expected_offset = (
        _dt.datetime.now(ASUNCION_TZ).astimezone(_dt.timezone(_dt.timedelta(0))).astimezone(ASUNCION_TZ).utcoffset()
    )
    assert result.utcoffset() == expected_offset, (
        f"today_local() offset is {result.utcoffset()}; expected {expected_offset}"
    )
    # Same moment in time as now() (within 1 second)
    from app.rms.clock import now
    delta = abs((now() - result).total_seconds())
    assert delta < 1.0, f"now() and today_local() differ by {delta}s"


def test_to_utc_handles_naive_and_aware():
    """``to_utc`` assumes naive datetimes are already UTC; aware ones are converted."""
    from app.rms.clock import to_utc

    # Naive: stays at the same instant, gets UTC tzinfo
    naive = _dt.datetime(2026, 10, 1, 12, 0, 0)
    aware_utc = to_utc(naive)
    assert aware_utc.tzinfo is _dt.timezone.utc
    assert aware_utc.replace(tzinfo=None) == naive

    # Aware in non-UTC: converted to UTC
    asuncion_tz = _dt.timezone(_dt.timedelta(hours=-4))
    aware_asu = _dt.datetime(2026, 10, 1, 8, 0, 0, tzinfo=asuncion_tz)  # = 12:00 UTC
    aware_utc2 = to_utc(aware_asu)
    assert aware_utc2.tzinfo is _dt.timezone.utc
    assert aware_utc2 == _dt.datetime(2026, 10, 1, 12, 0, 0, tzinfo=_dt.timezone.utc)


def test_to_asuncion_handles_naive_and_aware():
    """``to_asuncion`` assumes naive datetimes are UTC; aware ones are converted."""
    from app.rms.clock import ASUNCION_TZ, to_asuncion

    # Naive: stays at the same instant, gets Asuncion tzinfo
    naive = _dt.datetime(2026, 10, 1, 12, 0, 0)
    aware_asu = to_asuncion(naive)
    assert aware_asu.tzinfo is not None
    # Paraguay's offset is whatever America/Asuncion says (varies with DST)
    expected_offset = ASUNCION_TZ.utcoffset(aware_asu.replace(tzinfo=None))
    assert aware_asu.utcoffset() == expected_offset, (
        f"utcoffset is {aware_asu.utcoffset()}, expected {expected_offset}"
    )


def test_utcnow_alias_matches_now():
    """``utcnow`` is a backwards-compatible alias for ``now``."""
    from app.rms import clock

    a = clock.utcnow()
    b = clock.now()
    assert abs((a - b).total_seconds()) < 0.01


def test_no_bare_datetime_now_in_app_source():
    """No `.py` file in app/ uses ``datetime.utcnow()`` or bare ``datetime.now()``.

    Exceptions:
    - ``app/rms/clock.py`` itself (defines the helpers)
    - Docstrings + comments are tolerated (they may mention the old names
      historically; the regex below only matches *calls*, not mentions).
    """
    import re

    _call_patterns = [
        re.compile(r"\bdatetime\.utcnow\s*\("),
        # Bare `datetime.now()` only — `datetime.now(ASUNCION_TZ)` is fine.
        re.compile(r"(?<![\w.])datetime\.now\s*\(\s*\)"),
    ]

    offenders: list[tuple[str, str]] = []
    for py in (REPO_ROOT / "app").rglob("*.py"):
        # Skip the clock module itself
        if py.name == "clock.py":
            continue
        # Generated seed files mirror the seed/sazon.py naive-UTC contract
        # (same rationale as the pyproject per-file DTZ ignore) — they are
        # regenerated from scripts/, so fix the GENERATOR, not the output.
        if py.name in ("packs.py",) and "GENERATED FILE" in py.read_text(
            encoding="utf-8"
        )[:400]:
            continue
        # Strip docstrings (triple-quoted at module/class level) and comments
        text = py.read_text(encoding="utf-8")
        # Use Python's tokenize to find actual call expressions
        import ast as _ast
        try:
            tree = _ast.parse(text)
        except SyntaxError:
            continue
        for node in _ast.walk(tree):
            if not isinstance(node, _ast.Call):
                continue
            func = node.func
            # Match `datetime.utcnow(...)` or `datetime.now(...)` calls
            is_utcnow = (
                isinstance(func, _ast.Attribute)
                and func.attr == "utcnow"
                and isinstance(func.value, _ast.Name)
                and func.value.id == "datetime"
            )
            is_now = (
                isinstance(func, _ast.Attribute)
                and func.attr == "now"
                and isinstance(func.value, _ast.Name)
                and func.value.id == "datetime"
                # Only flag bare datetime.now() — datetime.now(ASUNCION_TZ) is fine
                and not node.args
                and not node.keywords
            )
            if is_utcnow or is_now:
                offenders.append((str(py.relative_to(REPO_ROOT)), f"line {node.lineno}"))

    assert not offenders, (
        "Bare datetime.utcnow() / datetime.now() still in source (use app.rms.clock):\n"
        + "\n".join(f"  {p}: {line_no}" for p, line_no in offenders)
    )


def test_eod_closed_uses_clock_helper():
    """``eod_closed._today_local`` must use ``clock.today_local()``, not ``datetime.utcnow().date()``."""
    from app.rms import eod_closed

    src = Path(eod_closed.__file__).read_text(encoding="utf-8")
    # The audit-flagged fallback path
    assert "datetime.utcnow().date" not in src, (
        "eod_closed._today_local still has the audit-flagged fallback "
        "`datetime.utcnow().date()` — must use clock.today_local()."
    )
    assert "today_local" in src, (
        "eod_closed._today_local should reference clock.today_local()"
    )


def test_pedidos_router_uses_clock_helpers():
    """``routers/pedidos.py`` uses ``clock.now`` / ``clock.today_local``."""
    src = (REPO_ROOT / "app" / "routers" / "pedidos.py").read_text(encoding="utf-8")
    assert "from app.rms.clock import" in src, (
        "routers/pedidos.py should import from app.rms.clock"
    )
    # The audit-flagged call sites must be gone
    assert "datetime.utcnow()" not in src
    assert "datetime.now().strftime" not in src  # filename timestamp used today_local


def test_settings_runtime_uses_clock_helper():
    """``routers/settings_runtime.py`` uses ``clock.now`` for ``SettingsKV.updated_at``."""
    src = (REPO_ROOT / "app" / "routers" / "settings_runtime.py").read_text(encoding="utf-8")
    assert "from app.rms.clock import" in src
    assert "datetime.utcnow()" not in src
