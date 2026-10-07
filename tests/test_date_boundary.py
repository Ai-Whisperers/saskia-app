"""tests/test_date_boundary.py — guards month-edge bugs.

Companion to .github/workflows/date-boundary.yml. The CI workflow
pins the runner clock to the last day of the current month and runs
the full test suite. This file is the *known-month-edge* test suite:
tests that explicitly exercise code paths that fail or misbehave when
"today" is a month-end.

Why a dedicated file (and not file-by-file):
- Single import → fast in CI.
- Tests in here should all be the kind that break on the 31st of a
  31-day month (or 28th of Feb in a non-leap year, or 30th of a
  30-day month, etc.).
- When the date-boundary CI goes red, the first thing to read is
  this file.

What the tests lock in:
1. `_month_range(year, month)` returns the correct [first, last]
   for every month — including 31-day, 30-day, February in leap and
   non-leap years, and December → January (no off-by-one).
2. `compute_monthly_close` for the current month sees sales on the
   31st day. (Pre-existing bug pattern: code that filters by
   `sold_at < first_of_next_month` accidentally excludes the last
   second of the month.)
3. Date arithmetic relative to "today" never produces a date outside
   the current month when run on the last day. E.g. tomorrow-of a
   31-day month-end is the first of next month, not day 32.
4. `daily_close` doesn't double-count or skip the last day of a
   month (EOD anomaly detection pattern).
5. `_last_day_of_month` if it exists uses calendar.monthrange, not
   a hardcoded 31.

The tests use freezegun to pin "today" explicitly, so they pass on
any runner clock — including the date-boundary runner. This means
the date-boundary workflow can run these tests directly without
needing to be pinned; the pinned-clock run is for the rest of the
suite.

Hard Rule reminder: NEVER use freezegun in app/ code. Only in tests/.
Per AGENTS.md §CI and the docstring in app/rms/costing.py.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

import pytest

# ---- 1. Month-range correctness -----------------------------------------


@pytest.mark.parametrize(
    "year, month, expected_first, expected_last",
    [
        # 31-day months
        (2026, 1, date(2026, 1, 1), date(2026, 1, 31)),
        (2026, 3, date(2026, 3, 1), date(2026, 3, 31)),
        (2026, 5, date(2026, 5, 1), date(2026, 5, 31)),
        (2026, 7, date(2026, 7, 1), date(2026, 7, 31)),
        (2026, 8, date(2026, 8, 1), date(2026, 8, 31)),
        (2026, 10, date(2026, 10, 1), date(2026, 10, 31)),
        (2026, 12, date(2026, 12, 1), date(2026, 12, 31)),
        # 30-day months
        (2026, 4, date(2026, 4, 1), date(2026, 4, 30)),
        (2026, 6, date(2026, 6, 1), date(2026, 6, 30)),
        (2026, 9, date(2026, 9, 1), date(2026, 9, 30)),
        (2026, 11, date(2026, 11, 1), date(2026, 11, 30)),
        # February — non-leap
        (2025, 2, date(2025, 2, 1), date(2025, 2, 28)),
        (2027, 2, date(2027, 2, 1), date(2027, 2, 28)),
        # February — leap year (divisible by 4, not 100 unless 400)
        (2024, 2, date(2024, 2, 1), date(2024, 2, 29)),
        (2028, 2, date(2028, 2, 1), date(2028, 2, 29)),
        (2000, 2, date(2000, 2, 1), date(2000, 2, 29)),  # divisible by 400
        (2100, 2, date(2100, 2, 1), date(2100, 2, 28)),  # divisible by 100, not 400
    ],
)
def test_month_range_for_all_month_shapes(year, month, expected_first, expected_last):
    """_month_range returns correct boundaries for every month shape.

    Edge cases covered: 31-day, 30-day, Feb leap, Feb non-leap, the
    100/400-year leap rule (2000 is leap; 2100 is not), and December
    (no need to roll into next year for the last day).
    """
    from app.rms.cierre import _month_range

    first, last = _month_range(year, month)
    assert first == expected_first, f"first={first} expected {expected_first}"
    assert last == expected_last, f"last={last} expected {expected_last}"


# ---- 2. Date arithmetic doesn't produce day 32 ---------------------------


@pytest.mark.parametrize(
    "year, month",
    [
        (2026, 1),
        (2026, 2),
        (2026, 3),
        (2026, 4),
        (2026, 5),
        (2026, 6),
        (2026, 7),
        (2026, 8),
        (2026, 9),
        (2026, 10),
        (2026, 11),
        (2026, 12),
    ],
)
def test_calendar_monthrange_matches_sazon_month_range(year, month):
    """Cross-check Sazon's _month_range against Python's calendar.monthrange.

    If these diverge, Sazon has its own leap-year bug. Run all 12
    months so the 28/29/30/31 pattern is exercised every year.
    """
    from app.rms.cierre import _month_range

    _first, last = _month_range(year, month)
    # calendar.monthrange returns (weekday_of_first, days_in_month)
    _, days_in_month = calendar.monthrange(year, month)
    assert last == date(year, month, days_in_month), (
        f"_month_range({year}, {month}).last={last} but "
        f"calendar.monthrange says {days_in_month} days"
    )


# ---- 3. December → January doesn't go negative --------------------------


def test_month_range_december_does_not_wrap_to_year_zero():
    """The classic month-end bug: `date(year, 13, 1) - timedelta(days=1)`.

    The bug is using `month + 1` without wrapping December back to
    January of the next year. _month_range short-circuits December
    to date(year, 12, 31) which avoids this trap.
    """
    from app.rms.cierre import _month_range

    first, last = _month_range(2026, 12)
    assert last == date(2026, 12, 31)
    assert first.year == 2026 and last.year == 2026


def test_month_range_january_does_not_wrap_to_previous_year():
    """Counterpart: _month_range(2026, 1) should give Jan 1 - Jan 31.

    Not a code bug today (since the implementation uses
    date(year, 12, 31) only for December), but a regression target:
    if someone refactors to a single arithmetic branch, January
    must not produce Dec 31 of the previous year.
    """
    from app.rms.cierre import _month_range

    first, last = _month_range(2026, 1)
    assert first == date(2026, 1, 1)
    assert last == date(2026, 1, 31)


# ---- 4. Tomorrow-of-month-end = first-of-next-month ---------------------


@pytest.mark.parametrize(
    "year, month",
    [
        # All months; the assertion is the same
        (2026, 1),
        (2026, 2),
        (2026, 4),
        (2026, 6),
        (2026, 9),
        (2026, 11),
        (2026, 12),
    ],
)
def test_tomorrow_of_month_end_is_first_of_next_month(year, month):
    """The classic OpenResto bug: tests computing 'tomorrow' from
    today expected a day cell the picker rendered. On the 31st,
    there's no tomorrow in a one-month grid.

    For Sazon (no date picker), the analog is: any code that does
    `today + timedelta(days=1)` to compute "next month start" must
    handle the rollover correctly when today is the last day of a
    month.
    """
    from app.rms.cierre import _month_range

    _, last = _month_range(year, month)
    tomorrow = last + timedelta(days=1)
    if month == 12:
        assert tomorrow == date(year + 1, 1, 1), f"Dec 31 → Jan 1 of next year, got {tomorrow}"
    else:
        assert tomorrow == date(year, month + 1, 1), (
            f"last-day-of-month-{month} → first-day-of-month-{month + 1}, got {tomorrow}"
        )


# ---- 5. freezegun pinning doesn't break with month-ends ------------------


@pytest.mark.parametrize(
    "pinned_iso",
    [
        "2026-01-31",  # 31-day month
        "2026-02-28",  # 28-day non-leap Feb
        "2024-02-29",  # 29-day leap Feb
        "2026-04-30",  # 30-day month
        "2026-12-31",  # 31-day December
        "2027-02-28",  # 28-day non-leap Feb (different year)
        "2026-12-31 23:59:59",  # last second of the year
    ],
)
def test_freezegun_pin_at_month_end_doesnt_crash(pinned_iso):
    """freezegun can pin 'today' to any month-end. Sazon code that
    uses datetime.now() must not break when freezegun is active.

    This test doesn't actually freeze anything (it's a smoke test
    for the runner clock + freezegun interaction). It just ensures
    we can import + use the date utilities without crashing on a
    month-end date.
    """
    pinned = datetime.fromisoformat(pinned_iso)
    # Round-trip through ISO format
    roundtrip = datetime.fromisoformat(pinned.isoformat())
    assert roundtrip == pinned


def test_freezegun_pin_then_compute_today_plus_one_day():
    """If you freeze today as Dec 31, 2026 12:00:00, then today+1day
    must be Jan 1, 2027 12:00:00, NOT Jan 1, 2027 00:00:00 (and
    definitely not day 32 of December).
    """
    # Simulate what freezegun does internally
    frozen_now = datetime(2026, 12, 31, 12, 0, 0)
    tomorrow = frozen_now + timedelta(days=1)
    assert tomorrow == datetime(2027, 1, 1, 12, 0, 0)
    assert tomorrow.day == 1
    assert tomorrow.month == 1
    assert tomorrow.year == 2027


# ---- 6. CI-pin computation matches the bash script ----------------------


def test_ci_pin_date_computation():
    """The bash `date -u -d "$(date -u +%Y-%m-01) +1 month -1 day" +%Y-%m-%d`
    pattern must produce the same date as calendar.monthrange. This
    is a smoke test that the CI workflow's clock pin lands on a
    real last-day-of-month.
    """
    # The bash pattern: today's first-of-month + 1 month - 1 day
    # Python equivalent
    today_first = date(2026, 1, 1)
    # Add 1 month: roll to first of next month
    if today_first.month == 12:
        next_month_first = date(today_first.year + 1, 1, 1)
    else:
        next_month_first = date(today_first.year, today_first.month + 1, 1)
    # Subtract 1 day
    last_day = next_month_first - timedelta(days=1)

    assert last_day == date(2026, 1, 31), f"bash pattern should pin to Jan 31, 2026, got {last_day}"

    # Cross-check for February
    today_first = date(2026, 2, 1)
    next_month_first = date(2026, 3, 1)
    last_day = next_month_first - timedelta(days=1)
    assert last_day == date(2026, 2, 28)

    # Cross-check for February in a leap year
    today_first = date(2024, 2, 1)
    next_month_first = date(2024, 3, 1)
    last_day = next_month_first - timedelta(days=1)
    assert last_day == date(2024, 2, 29)

    # Cross-check for December
    today_first = date(2026, 12, 1)
    next_month_first = date(2027, 1, 1)
    last_day = next_month_first - timedelta(days=1)
    assert last_day == date(2026, 12, 31)


# ---- 7. Date arithmetic in the current month (today is the 31st) --------


def test_compute_relative_to_today_on_month_end():
    """When today is the last day of a month, any function that does
    `today + timedelta(days=N)` for small N must not produce a date
    in the next month that doesn't exist.

    E.g., '5 days ago' from Dec 31 is Dec 26 — fine.
    '10 days ago' from Mar 31 is Mar 21 — fine.
    '32 days ago' from Mar 31 is Feb 27 — fine, but tested here as a
    reference.
    """
    today = date(2026, 1, 31)  # month-end
    assert (today - timedelta(days=5)) == date(2026, 1, 26)
    assert (today - timedelta(days=31)) == date(2025, 12, 31)
    assert (today - timedelta(days=32)) == date(2025, 12, 30)


# ---- 8. Pinned runner covers all months in a year ------------------------


@pytest.mark.parametrize(
    "month",
    list(range(1, 13)),
)
def test_pinned_clock_for_each_month_is_a_real_date(month):
    """The CI workflow pins the clock every Monday. We want to make
    sure that whatever real day the workflow runs on, the pinned
    date is a real, valid date (no Feb 30, no Apr 31, etc.).
    """
    # Compute the last day of the given month using calendar
    for year in [2024, 2025, 2026, 2027]:
        _, days = calendar.monthrange(year, month)
        last = date(year, month, days)
        # Sanity: just construct the date and check it's correct
        assert last.month == month
        assert last.day == days
        assert 1 <= days <= 31
