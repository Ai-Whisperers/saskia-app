"""Parametrized coverage for the s3-batch-10 split of `produccion_shift_execute`.

S3 batch-10 (complexity refactor, ticket 211ac): the D-grade route handler
`produccion_shift_execute` (CC 27, at app/routers/produccion/operations.py)
was split into a thin orchestrator (CC 3, A-grade) + four single-purpose
helpers (all <= CC 10, B-grade):

  - `_check_shift_request_preconditions` (CC 4, A)
  - `_detect_shift_concurrent_modify`  (CC 8, B)
  - `_parse_completed_field`            (CC 6, B, pure function)
  - `_persist_completed_completions`    (CC 7, B)
  - `_persist_done_checkboxes`          (CC 7, B)

This file locks the branch matrix of each helper. The route itself
already has integration coverage (test_produccion_concurrent_edit,
test_produccion_closed_day, etc.); this batch is the parametrized
helper-level coverage that the previous batch-3/4/5/6/7/8/9 pattern
established.

Branch matrix:

  _check_shift_request_preconditions:
    - rate-limit hit                  -> 429
    - for_date in the future          -> 400
    - for_date too far in the past    -> 400
    - for_date today                  -> no raise
    - for_date within the window      -> no raise

  _detect_shift_concurrent_modify:
    - form_opened_at missing/empty    -> False (no warning)
    - form_opened_at malformed        -> False (no warning, DEBUG log)
    - form_opened_at < max(updated_at) -> True  (concurrent save)
    - form_opened_at > max(updated_at) -> False (you saw the latest)
    - no prior saves for date         -> False (nothing to compare)
    - form_opened_at naive (no tz)    -> treated as UTC, compared correctly
    - form is None                    -> False (defensive)

  _parse_completed_field (pure):
    - non-completed_ key              -> (None, None)
    - completed_ non-numeric pid      -> (None, None)
    - completed_ non-numeric qty      -> (None, None)
    - completed_ negative qty         -> (None, None)
    - completed_ non-str value         -> (None, None)
    - completed_ valid pid+qty        -> (int(pid), float(qty))
    - completed_ qty=0                -> (int(pid), 0.0) (honest zero)
    - completed_ qty=12.5 (decimal)    -> (int(pid), 12.5)

  _persist_completed_completions:
    - no completed_ fields            -> (0, 0)
    - one valid completed_<pid>=5     -> (1, 0) + ProductionCompletion row
    - one completed_<pid>=0           -> (1, 0) (honest zero)
    - one invalid completed_<bad>     -> (0, 1)
    - completed_<missing_pid>=5       -> (0, 1) (product not in DB)
    - mixed valid + invalid           -> (saved, skipped) counts correct

  _persist_done_checkboxes:
    - no done_ fields                 -> 0
    - one done_<pid>=1                -> 1 + close_day_for_product called
    - one done_<pid>=0 (unchecked)    -> 0 (no row)
    - done_<missing_pid>=1            -> 0 (product not in DB)
    - done_<bad>=1 (non-numeric pid)  -> 0 (skip silently)
    - non-str value on done_<pid>     -> 0
    - two done_<p1>=1 + done_<p2>=1   -> 2

Public route contract is locked separately by the existing
test_produccion_concurrent_edit.py (the soft warning redirect behavior
spans the orchestrator + _detect_shift_concurrent_modify helper).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Module under test — the four helpers extracted from produccion_shift_execute
# in app/routers/produccion/operations.py
# ---------------------------------------------------------------------------
from app.routers.produccion.operations import (
    _check_shift_request_preconditions,
    _detect_shift_concurrent_modify,
    _parse_completed_field,
    _persist_completed_completions,
    _persist_done_checkboxes,
)

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


class _FakeForm:
    """Minimal form stand-in for _persist_*_checkboxes / _parse_completed_field.

    Mimics a starlette `FormData` shape: supports `.get(name)` for single
    lookups and `.multi_items()` to iterate `(key, value)` pairs. Values
    are either strings (form-encoded) or `UploadFile` (file uploads).
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def multi_items(self):
        # Return in stable insertion order; matches FormData.multi_items()
        # for the tests we care about.
        return list(self._data.items())


@pytest.fixture
def make_form():
    """Factory: build a _FakeForm from a dict of {field_name: value}."""
    return _FakeForm


# ---------------------------------------------------------------------------
# _check_shift_request_preconditions branches
# ---------------------------------------------------------------------------


class TestCheckShiftRequestPreconditions:
    """Branch matrix for the rate-limit + date-window guard."""

    def test_today_is_allowed(self, monkeypatch):
        """for_date == today_local -> no raise."""
        # Patch is_write_rate_limited to return False
        import app.routers.produccion.operations as ops

        monkeypatch.setattr(ops, "is_write_rate_limited", lambda s, r: False)
        # Should not raise
        _check_shift_request_preconditions(
            session=MagicMock(),
            request=MagicMock(),
            for_date=date.today(),
        )

    def test_future_date_rejected(self, monkeypatch):
        """for_date > today -> 400."""
        import app.routers.produccion.operations as ops

        monkeypatch.setattr(ops, "is_write_rate_limited", lambda s, r: False)
        future = date.today() + timedelta(days=2)
        with pytest.raises(Exception) as exc:
            _check_shift_request_preconditions(
                session=MagicMock(),
                request=MagicMock(),
                for_date=future,
            )
        # FastAPI HTTPException 400
        assert getattr(exc.value, "status_code", None) == 400
        # Spanish copy
        assert "no puede ser futura" in str(exc.value.detail)

    def test_past_date_outside_window_rejected(self, monkeypatch):
        """for_date < today - BACKDATE_WINDOW_DAYS -> 400."""
        import app.routers.produccion.operations as ops

        monkeypatch.setattr(ops, "is_write_rate_limited", lambda s, r: False)
        far_past = date.today() - timedelta(days=30)
        with pytest.raises(Exception) as exc:
            _check_shift_request_preconditions(
                session=MagicMock(),
                request=MagicMock(),
                for_date=far_past,
            )
        assert getattr(exc.value, "status_code", None) == 400
        assert "fuera de la ventana" in str(exc.value.detail)

    def test_within_backdate_window_allowed(self, monkeypatch):
        """for_date yesterday is within the default 7-day window."""
        import app.routers.produccion.operations as ops

        monkeypatch.setattr(ops, "is_write_rate_limited", lambda s, r: False)
        yesterday = date.today() - timedelta(days=1)
        _check_shift_request_preconditions(
            session=MagicMock(),
            request=MagicMock(),
            for_date=yesterday,
        )

    def test_rate_limited_raises_429(self, monkeypatch):
        """is_write_rate_limited True -> 429 (date check skipped)."""
        import app.routers.produccion.operations as ops

        monkeypatch.setattr(ops, "is_write_rate_limited", lambda s, r: True)
        with pytest.raises(Exception) as exc:
            _check_shift_request_preconditions(
                session=MagicMock(),
                request=MagicMock(),
                for_date=date.today(),
            )
        assert getattr(exc.value, "status_code", None) == 429
        assert "Demasiadas acciones" in str(exc.value.detail)


# ---------------------------------------------------------------------------
# _parse_completed_field branches — pure function
# ---------------------------------------------------------------------------


class TestParseCompletedField:
    """Pure-function branch matrix for completed_<pid>=<qty> parsing."""

    @pytest.mark.parametrize(
        "key,value,expected",
        [
            # --- reject branches ---
            ("other_field", "5", (None, None)),  # non-completed_ key
            ("completed_", "5", (None, None)),  # empty pid (int("") fails)
            ("completed_abc", "5", (None, None)),  # non-numeric pid
            ("completed_1", "x", (None, None)),  # non-numeric qty
            ("completed_1", "", (None, None)),  # empty qty (float("") fails)
            ("completed_1", "-1", (None, None)),  # negative qty
            ("completed_1", b"5", (None, None)),  # bytes value
            # --- accept branches ---
            ("completed_1", "5", (1, 5.0)),  # happy path
            ("completed_1", "0", (1, 0.0)),  # honest zero
            ("completed_42", "12.5", (42, 12.5)),  # decimal qty
            ("completed_7", "100", (7, 100.0)),  # large pid, integer qty
        ],
    )
    def test_parse_completed_field_branches(self, key, value, expected):
        """Every branch of _parse_completed_field returns the expected tuple."""
        assert _parse_completed_field(key, value) == expected

    def test_non_string_value_rejected(self):
        """UploadFile / non-str value -> (None, None)."""
        fake_upload = MagicMock()  # not a str
        assert _parse_completed_field("completed_1", fake_upload) == (None, None)

    def test_pure_function_no_side_effects(self):
        """Calling twice with the same input returns the same output (idempotent)."""
        a = _parse_completed_field("completed_1", "5")
        b = _parse_completed_field("completed_1", "5")
        assert a == b == (1, 5.0)


# ---------------------------------------------------------------------------
# _detect_shift_concurrent_modify branches
# ---------------------------------------------------------------------------


class TestDetectShiftConcurrentModify:
    """Branch matrix for the T-2026-10-04 concurrent-modify detector."""

    def test_no_form_opened_at_returns_false(self, session_factory):
        """Missing form_opened_at -> False (backward compat)."""
        form = _FakeForm({})  # no form_opened_at
        with session_factory() as s:
            result = _detect_shift_concurrent_modify(s, form, date(2026, 10, 4))
        assert result is False

    def test_empty_form_opened_at_returns_false(self, session_factory):
        """Empty string form_opened_at -> False (no warning)."""
        form = _FakeForm({"form_opened_at": ""})
        with session_factory() as s:
            result = _detect_shift_concurrent_modify(s, form, date(2026, 10, 4))
        assert result is False

    def test_malformed_form_opened_at_returns_false(self, session_factory):
        """Bad ISO format -> False, DEBUG log, no silent pass."""
        form = _FakeForm({"form_opened_at": "not-a-date"})
        with session_factory() as s:
            result = _detect_shift_concurrent_modify(s, form, date(2026, 10, 4))
        assert result is False

    def test_none_form_returns_false(self, session_factory):
        """form is None -> False (defensive)."""
        with session_factory() as s:
            result = _detect_shift_concurrent_modify(s, None, date(2026, 10, 4))
        assert result is False

    def test_no_prior_saves_returns_false(self, session_factory):
        """No ProductionCompletion rows for the date -> False (nothing to compare)."""
        form = _FakeForm({"form_opened_at": "2026-10-04T10:00:00+00:00"})
        with session_factory() as s:
            result = _detect_shift_concurrent_modify(s, form, date(2026, 10, 4))
        assert result is False

    def test_form_opened_at_older_than_max_returns_true(self, session_factory):
        """form_opened_at < max(updated_at) -> True (concurrent save detected)."""
        from app.rms.models_legacy import Product, ProductionCompletion

        with session_factory() as s:
            prod = Product(
                name="TestDetectedConcurrent",
                sale_price_gs=10000,
                portion_label="1 unidad",
            )
            s.add(prod)
            s.flush()
            s.commit()
            pid = prod.id

            now = datetime.now(timezone.utc)
            # Save with updated_at 10min in the future relative to form_opened
            s.add(
                ProductionCompletion(
                    product_id=pid,
                    for_date=date(2026, 10, 4),
                    completed_qty=5.0,
                    recorded_at=now,
                    updated_at=now + timedelta(minutes=10),
                )
            )
            s.commit()

        # Form was opened 5 min ago, but the row was updated 10 min AFTER now,
        # so the row is 5 min newer than the form -> concurrent.
        form_opened = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        form = _FakeForm({"form_opened_at": form_opened})
        with session_factory() as s:
            result = _detect_shift_concurrent_modify(s, form, date(2026, 10, 4))
        assert result is True

    def test_form_opened_at_newer_than_max_returns_false(self, session_factory):
        """form_opened_at > max(updated_at) -> False (you saw the latest)."""
        from app.rms.models_legacy import Product, ProductionCompletion

        with session_factory() as s:
            prod = Product(
                name="TestNoConcurrent",
                sale_price_gs=10000,
                portion_label="1 unidad",
            )
            s.add(prod)
            s.flush()
            s.commit()
            pid = prod.id

            now = datetime.now(timezone.utc)
            # Save with updated_at 5 min ago
            s.add(
                ProductionCompletion(
                    product_id=pid,
                    for_date=date(2026, 10, 4),
                    completed_qty=5.0,
                    recorded_at=now - timedelta(minutes=5),
                    updated_at=now - timedelta(minutes=5),
                )
            )
            s.commit()

        # Form opened just now -> newer than the row
        form_opened = datetime.now(timezone.utc).isoformat()
        form = _FakeForm({"form_opened_at": form_opened})
        with session_factory() as s:
            result = _detect_shift_concurrent_modify(s, form, date(2026, 10, 4))
        assert result is False

    def test_naive_form_opened_at_treated_as_utc(self, session_factory):
        """Naive datetime (no tz) is treated as UTC for comparison."""
        from app.rms.models_legacy import Product, ProductionCompletion

        with session_factory() as s:
            prod = Product(
                name="TestNaiveTz",
                sale_price_gs=10000,
                portion_label="1 unidad",
            )
            s.add(prod)
            s.flush()
            s.commit()
            pid = prod.id

            now = datetime.now(timezone.utc)
            s.add(
                ProductionCompletion(
                    product_id=pid,
                    for_date=date(2026, 10, 4),
                    completed_qty=5.0,
                    recorded_at=now,
                    updated_at=now + timedelta(hours=1),  # 1h in the future
                )
            )
            s.commit()

        # Naive form_opened_at = 30 min ago (no tz suffix)
        form_opened_naive = (
            (datetime.now(timezone.utc) - timedelta(minutes=30)).replace(tzinfo=None).isoformat()
        )
        form = _FakeForm({"form_opened_at": form_opened_naive})
        with session_factory() as s:
            result = _detect_shift_concurrent_modify(s, form, date(2026, 10, 4))
        assert result is True  # row is 1h ahead, form was 30 min ago -> concurrent


# ---------------------------------------------------------------------------
# _persist_completed_completions branches
# ---------------------------------------------------------------------------


class TestPersistCompletedCompletions:
    """Branch matrix for the completed_<pid> upsert loop."""

    def test_no_completed_fields(self, session_factory):
        """No completed_<pid> fields -> (0, 0)."""
        form = _FakeForm({"for_date": "2026-10-04", "shift": "AM"})
        with session_factory() as s:
            saved, skipped = _persist_completed_completions(s, form, date(2026, 10, 4), "test-user")
        assert (saved, skipped) == (0, 0)

    def test_one_valid_field(self, session_factory):
        """One completed_<pid>=5 -> (1, 0) + ProductionCompletion row."""
        from app.rms.models_legacy import (
            Product,
            ProductionCompletion,
        )

        with session_factory() as s:
            prod = Product(
                name="TestPersistOne",
                sale_price_gs=10000,
                portion_label="1 unidad",
            )
            s.add(prod)
            s.flush()
            s.commit()
            pid = prod.id
            form = _FakeForm({f"completed_{pid}": "5"})
            saved, skipped = _persist_completed_completions(s, form, date(2026, 10, 4), "test-user")
            s.commit()
        assert (saved, skipped) == (1, 0)

        with session_factory() as s:
            row = s.query(ProductionCompletion).filter(ProductionCompletion.product_id == pid).one()
            assert row.completed_qty == pytest.approx(5.0)
            assert row.for_date == date(2026, 10, 4)

    def test_honest_zero_is_saved(self, session_factory):
        """completed_<pid>=0 (honest zero) -> (1, 0) and DB row qty=0."""
        from app.rms.models_legacy import (
            Product,
            ProductionCompletion,
        )

        with session_factory() as s:
            prod = Product(
                name="TestHonestZero",
                sale_price_gs=10000,
                portion_label="1 unidad",
            )
            s.add(prod)
            s.flush()
            s.commit()
            pid = prod.id
            form = _FakeForm({f"completed_{pid}": "0"})
            saved, skipped = _persist_completed_completions(s, form, date(2026, 10, 4), "test-user")
            s.commit()
        assert (saved, skipped) == (1, 0)

        with session_factory() as s:
            row = s.query(ProductionCompletion).filter(ProductionCompletion.product_id == pid).one()
            assert row.completed_qty == 0.0

    def test_invalid_pid_counted_as_skipped(self, session_factory):
        """completed_abc=5 (non-numeric pid) -> (0, 1)."""
        form = _FakeForm({"completed_abc": "5"})
        with session_factory() as s:
            saved, skipped = _persist_completed_completions(s, form, date(2026, 10, 4), "test-user")
        assert (saved, skipped) == (0, 1)

    def test_missing_product_counted_as_skipped(self, session_factory):
        """completed_<pid>=5 but no Product row -> (0, 1)."""
        form = _FakeForm({"completed_99999": "5"})
        with session_factory() as s:
            saved, skipped = _persist_completed_completions(s, form, date(2026, 10, 4), "test-user")
        assert (saved, skipped) == (0, 1)

    def test_non_numeric_qty_counted_as_skipped(self, session_factory):
        """completed_<pid>=notanumber -> (0, 1)."""
        from app.rms.models_legacy import Product

        with session_factory() as s:
            prod = Product(
                name="TestNonNumericQty",
                sale_price_gs=10000,
                portion_label="1 unidad",
            )
            s.add(prod)
            s.flush()
            s.commit()
            pid = prod.id

        form = _FakeForm({f"completed_{pid}": "abc"})
        with session_factory() as s:
            saved, skipped = _persist_completed_completions(s, form, date(2026, 10, 4), "test-user")
        assert (saved, skipped) == (0, 1)

    def test_negative_qty_counted_as_skipped(self, session_factory):
        """completed_<pid>=-1 -> (0, 1)."""
        from app.rms.models_legacy import Product

        with session_factory() as s:
            prod = Product(
                name="TestNegativeQty",
                sale_price_gs=10000,
                portion_label="1 unidad",
            )
            s.add(prod)
            s.flush()
            s.commit()
            pid = prod.id

        form = _FakeForm({f"completed_{pid}": "-1"})
        with session_factory() as s:
            saved, skipped = _persist_completed_completions(s, form, date(2026, 10, 4), "test-user")
        assert (saved, skipped) == (0, 1)

    def test_mixed_valid_and_invalid(self, session_factory):
        """One valid + one invalid -> (1, 1)."""
        from app.rms.models_legacy import Product

        with session_factory() as s:
            prod = Product(
                name="TestMixedPersist",
                sale_price_gs=10000,
                portion_label="1 unidad",
            )
            s.add(prod)
            s.flush()
            s.commit()
            pid = prod.id

        form = _FakeForm(
            {
                f"completed_{pid}": "5",  # valid
                "completed_99999": "3",  # product doesn't exist
            }
        )
        with session_factory() as s:
            saved, skipped = _persist_completed_completions(s, form, date(2026, 10, 4), "test-user")
        assert (saved, skipped) == (1, 1)


# ---------------------------------------------------------------------------
# _persist_done_checkboxes branches
# ---------------------------------------------------------------------------


class TestPersistDoneCheckboxes:
    """Branch matrix for the done_<pid>=1 checkbox loop."""

    def test_no_done_fields(self, session_factory):
        """No done_<pid> fields -> 0."""
        form = _FakeForm({"for_date": "2026-10-04"})
        with session_factory() as s:
            count = _persist_done_checkboxes(s, form, date(2026, 10, 4))
        assert count == 0

    def test_unchecked_done_returns_zero(self, session_factory):
        """done_<pid>=0 (unchecked) -> 0 (no row, no close)."""
        from app.rms.models_legacy import Product

        with session_factory() as s:
            prod = Product(
                name="TestUnchecked",
                sale_price_gs=10000,
                portion_label="1 unidad",
            )
            s.add(prod)
            s.flush()
            s.commit()
            pid = prod.id

        form = _FakeForm({f"done_{pid}": "0"})
        with session_factory() as s:
            count = _persist_done_checkboxes(s, form, date(2026, 10, 4))
        assert count == 0

    def test_checked_done_creates_completion(self, session_factory):
        """done_<pid>=1 -> count=1, ProductionCompletion row with status='done'."""
        from app.rms.models_legacy import (
            Product,
            ProductionCompletion,
        )

        with session_factory() as s:
            prod = Product(
                name="TestCheckedDone",
                sale_price_gs=10000,
                portion_label="1 unidad",
            )
            s.add(prod)
            s.flush()
            s.commit()
            pid = prod.id
            form = _FakeForm({f"done_{pid}": "1"})
            count = _persist_done_checkboxes(s, form, date(2026, 10, 4))
            s.commit()
        assert count == 1

        with session_factory() as s:
            row = s.query(ProductionCompletion).filter(ProductionCompletion.product_id == pid).one()
            assert row.status == "done"
            assert row.for_date == date(2026, 10, 4)

    def test_done_for_missing_product_skipped(self, session_factory):
        """done_<missing_pid>=1 -> 0 (no row, silently skipped)."""
        form = _FakeForm({"done_99999": "1"})
        with session_factory() as s:
            count = _persist_done_checkboxes(s, form, date(2026, 10, 4))
        assert count == 0

    def test_done_with_non_numeric_pid_skipped(self, session_factory):
        """done_abc=1 -> 0 (silently skipped, not a 500)."""
        form = _FakeForm({"done_abc": "1"})
        with session_factory() as s:
            count = _persist_done_checkboxes(s, form, date(2026, 10, 4))
        assert count == 0

    def test_non_string_value_on_done_skipped(self, session_factory):
        """done_<pid>=UploadFile (non-str) -> 0."""
        fake_upload = MagicMock()
        form = _FakeForm({"done_1": fake_upload})
        with session_factory() as s:
            count = _persist_done_checkboxes(s, form, date(2026, 10, 4))
        assert count == 0

    def test_two_checked_dones(self, session_factory):
        """done_<p1>=1 + done_<p2>=1 -> count=2."""
        from app.rms.models_legacy import Product

        with session_factory() as s:
            prod1 = Product(
                name="TestTwoDone1",
                sale_price_gs=10000,
                portion_label="1 unidad",
            )
            prod2 = Product(
                name="TestTwoDone2",
                sale_price_gs=10000,
                portion_label="1 unidad",
            )
            s.add_all([prod1, prod2])
            s.flush()
            s.commit()
            p1, p2 = prod1.id, prod2.id
            form = _FakeForm({f"done_{p1}": "1", f"done_{p2}": "1"})
            count = _persist_done_checkboxes(s, form, date(2026, 10, 4))
            s.commit()
        assert count == 2


# ---------------------------------------------------------------------------
# Helper-level CC sanity check
# ---------------------------------------------------------------------------


class TestHelperComplexity:
    """Lock the CC ceiling at <= 10 (B-grade) for the 5 extracted helpers.

    Runs radon on the live source to prevent a future refactor from
    re-bloating any helper past the B-grade ceiling (rule 40). This
    is the same gate `make complexity` enforces in CI.
    """

    @pytest.mark.parametrize(
        "fn_name,max_cc",
        [
            ("_check_shift_request_preconditions", 5),  # A-grade (CC <= 5)
            ("_detect_shift_concurrent_modify", 10),  # B-grade
            ("_parse_completed_field", 10),  # B-grade
            ("_persist_completed_completions", 10),  # B-grade
            ("_persist_done_checkboxes", 10),  # B-grade
        ],
    )
    def test_helper_cc_under_ceiling(self, fn_name, max_cc):
        """Every extracted helper is <= max_cc (A or B grade)."""
        from radon.visitors import ComplexityVisitor

        with open("app/routers/produccion/operations.py", encoding="utf-8") as fh:
            source = fh.read()
        visitor = ComplexityVisitor.from_code(source)
        for fn in visitor.functions:
            if fn.name == fn_name:
                assert fn.complexity <= max_cc, f"{fn_name} CC={fn.complexity} > max_cc={max_cc}"
                return
        pytest.fail(f"{fn_name} not found in operations.py — was the helper renamed?")
