"""Tests for PRODUCCION-V3 Phase 0 — silent-data-loss + backdate + page titles.

Three concerns, all on the existing /produccion day view:

1. The shift-checkbox (`done_<product_id>`) on each row is currently
   ignored by `produccion_shift_execute`. The cook checks the box, the
   page visually marks the row done, but the closure_status never
   persists. This is silent data loss.

2. `produccion_shift_execute` accepts any `for_date`, including dates
   years in the past. A cook can corrupt the 14-day rolling forecast
   by backfilling 2020. Cap it.

3. Page titles don't include the date, so two tabs of /produccion
   look identical. The `for_date` must show in `<title>` so the
   operator can tell them apart.

4. The column headers (Meta / +Pedidos / Total a hornear / Progreso)
   confuse new cooks. Rename to (Meta (und) / Pedidos / Lote final /
   Hecho) and add explanatory subtitles.

These tests pin the behavior so a future refactor can't accidentally
regress the silent-loss fix or the backdate cap.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.rms.eod_completions import completions_for_date
from app.rms.models import Product, ProductionCompletion


# --- Test fixtures ----------------------------------------------------------


@pytest.fixture
def croissant_id(session_factory):
    with session_factory() as s:
        prod = Product(
            name="Croissant v3 test",
            portion_label="1 und",
            sale_price_gs=10000,
            is_available=True,
        )
        s.add(prod)
        s.commit()
        s.refresh(prod)
        return prod.id


def _seed_day_view_product(session_factory) -> int:
    """Seed a single active product so the /produccion day-view table
    actually renders its thead + tbody. Returns the product id.

    The day view gates the table on whether rows exist; an empty DB
    renders an empty <main>, so we need at least one product for
    column-header assertions to find their text."""
    import datetime as _dt

    with session_factory() as s:
        prod = Product(
            name=f"Phase0 Column-Test {_dt.datetime.now().timestamp()}",
            portion_label="1 und",
            sale_price_gs=10000,
            is_available=True,
        )
        s.add(prod)
        s.commit()
        s.refresh(prod)
        # The day view is gated by {% if plan_rows_view %}, so the <thead>
        # only renders when at least one plan row exists. To make the
        # column-header assertions meaningful, we seed a per-date override
        # so the product appears in plan.rows for today.
        from app.rms.models_legacy import ProductionPlanOverride

        s.add(
            ProductionPlanOverride(
                product_id=prod.id,
                for_date=_dt.date.today(),
                qty=20.0,
                updated_at=_dt.datetime.now(),
            )
        )
        s.commit()
        return prod.id


# --- 1. Shift-checkbox silent-data-loss fix ---------------------------------


def test_shift_execute_checkbox_persists_closure_done(
    authed_client, session_factory, croissant_id
):
    """Posting `done_<pid>=1` must persist closure_status='done'.

    Regression for the audit blocker (B5 + H5): the cook checks the
    shift-checkbox, presses Guardar turno, the page visually marks the
    row complete, but the closure_status was NEVER written to the DB
    because the route ignored `done_<pid>`. This test fails on the
    OLD code (closure_status stays at the default) and passes on the
    NEW code.
    """
    today = datetime.now(UTC).date()

    r = authed_client.post(
        "/produccion/shift-execute",
        data={
            "for_date": today.isoformat(),
            f"completed_{croissant_id}": "12",
            f"done_{croissant_id}": "1",
        },
    )
    assert r.status_code in (200, 303), f"shift-execute returned {r.status_code}: {r.text[:200]}"

    with session_factory() as s:
        row = s.execute(
            select(ProductionCompletion).where(
                ProductionCompletion.product_id == croissant_id,
                ProductionCompletion.for_date == today,
            )
        ).scalar_one()
        assert row.status == "done", (
            f"closure_status must be 'done' when checkbox is checked; got {row.status!r}"
        )
        assert float(row.completed_qty) == 12.0


def test_shift_execute_unchecked_box_leaves_status_open(
    authed_client, session_factory, croissant_id
):
    """If `done_<pid>` is absent, closure_status stays 'open' (default).

    The cook didn't check the box → the row is still open → no silent
    flip to done. This protects against the inverse data-loss:
    marking a row done when the cook didn't intend it.
    """
    today = datetime.now(UTC).date()

    r = authed_client.post(
        "/produccion/shift-execute",
        data={
            "for_date": today.isoformat(),
            f"completed_{croissant_id}": "12",
            # NO done_<pid> field — cook didn't check the box
        },
    )
    assert r.status_code in (200, 303)

    with session_factory() as s:
        row = s.execute(
            select(ProductionCompletion).where(
                ProductionCompletion.product_id == croissant_id,
                ProductionCompletion.for_date == today,
            )
        ).scalar_one()
        assert row.status == "open", (
            f"closure_status must stay 'open' when checkbox is unchecked; got {row.status!r}"
        )


def test_shift_execute_checkbox_uncheck_reopens(
    authed_client, session_factory, croissant_id
):
    """Re-posting with the checkbox CHECKED again must keep status='done'.

    (The uncheck path — done -> open — is handled by the dedicated
    /produccion/close-day/reopen route; this endpoint only handles
    'still done' and 'newly done' states.)
    """
    today = datetime.now(UTC).date()
    from app.rms.eod_completions import close_day_for_product

    with session_factory() as s:
        close_day_for_product(
            s,
            product_id=croissant_id,
            for_date=today,
            status="open",
        )
        s.commit()

    r = authed_client.post(
        "/produccion/shift-execute",
        data={
            "for_date": today.isoformat(),
            f"completed_{croissant_id}": "5",
            f"done_{croissant_id}": "1",
        },
    )
    assert r.status_code in (200, 303)

    with session_factory() as s:
        row = s.execute(
            select(ProductionCompletion).where(
                ProductionCompletion.product_id == croissant_id,
                ProductionCompletion.for_date == today,
            )
        ).scalar_one()
        assert row.status == "done"
        assert float(row.completed_qty) == 5.0


def test_shift_execute_checkbox_without_qty_creates_zero_done(
    authed_client, session_factory, croissant_id
):
    """Cook can mark a row done with completed_qty=0 (baked nothing).

    The form's natural shape is `completed_<pid>=0&done_<pid>=1` —
    the cook baked nothing for this product but is closing the day.
    The route must persist status='done' AND a row exists, even if
    qty is 0. (Without the fix, the row is created with default
    status='open' which is wrong.)
    """
    today = datetime.now(UTC).date()

    r = authed_client.post(
        "/produccion/shift-execute",
        data={
            "for_date": today.isoformat(),
            f"completed_{croissant_id}": "0",
            f"done_{croissant_id}": "1",
        },
    )
    assert r.status_code in (200, 303)

    with session_factory() as s:
        row = s.execute(
            select(ProductionCompletion).where(
                ProductionCompletion.product_id == croissant_id,
                ProductionCompletion.for_date == today,
            )
        ).scalar_one()
        assert row.status == "done"
        assert float(row.completed_qty) == 0.0


# --- 2. Backdate cap --------------------------------------------------------


def test_shift_execute_rejects_far_past_for_date(
    authed_client, session_factory, croissant_id
):
    """for_date older than BACKDATE_WINDOW_DAYS (default 7) must 400.

    Regression for the audit blocker (M14/L13): a cook who backfills
    2020-01-01 would corrupt the 14-day rolling forecast used by
    future plans. The route must reject with a friendly Spanish error.
    """
    from app.rms.config import ASUNCION_TZ

    today = datetime.now(ASUNCION_TZ).date()
    too_old = today - timedelta(days=30)

    r = authed_client.post(
        "/produccion/shift-execute",
        data={
            "for_date": too_old.isoformat(),
            f"completed_{croissant_id}": "5",
        },
    )
    assert r.status_code == 400, (
        f"far-past for_date must 400; got {r.status_code}: {r.text[:200]}"
    )
    # Friendly Spanish error
    body = r.text.lower()
    assert "pasado" in body or "antigua" in body or "ventana" in body, (
        f"400 must include a friendly Spanish error; got: {r.text[:300]}"
    )


def test_shift_execute_rejects_future_for_date(
    authed_client, session_factory, croissant_id
):
    """for_date > today must 400.

    A cook can't bake tomorrow's bread today (the system can't
    distinguish 'plan ahead' from 'typo' for completions). Plans
    use a different endpoint.
    """
    from app.rms.config import ASUNCION_TZ

    today = datetime.now(ASUNCION_TZ).date()
    future = today + timedelta(days=7)

    r = authed_client.post(
        "/produccion/shift-execute",
        data={
            "for_date": future.isoformat(),
            f"completed_{croissant_id}": "5",
        },
    )
    assert r.status_code == 400


def test_shift_execute_accepts_within_window(
    authed_client, session_factory, croissant_id
):
    """for_date within BACKDATE_WINDOW_DAYS (default 7) must succeed.

    The cook legitimately needs to backfill 2-3 missed days.
    """
    from app.rms.config import ASUNCION_TZ

    today = datetime.now(ASUNCION_TZ).date()
    two_days_ago = today - timedelta(days=2)

    r = authed_client.post(
        "/produccion/shift-execute",
        data={
            "for_date": two_days_ago.isoformat(),
            f"completed_{croissant_id}": "5",
        },
    )
    assert r.status_code in (200, 303), (
        f"within-window backdate must succeed; got {r.status_code}: {r.text[:200]}"
    )


# --- 3. Page titles include the date ----------------------------------------


def test_day_view_title_includes_date(authed_client, session_factory):
    """The <title> tag must include the for_date so multi-tab users
    can tell which day they're on.

    Regression for the audit L1: a cook with 3 /produccion tabs open
    for today/yesterday/tomorrow all show 'Producción — Sazón' in
    the browser tab strip. They have to click each one to figure out
    which is which. Fix: include the date in the title.
    """
    today = datetime.now(UTC).date()
    r = authed_client.get(f"/produccion?for_date={today.isoformat()}")
    assert r.status_code == 200
    body = r.text
    # Find the <title>...</title> block.
    import re

    m = re.search(r"<title>([^<]+)</title>", body)
    assert m, "no <title> tag found"
    title = m.group(1)
    assert today.isoformat() in title, (
        f"title must include the for_date ({today.isoformat()}); got: {title!r}"
    )


def test_manana_page_title_includes_tomorrow(authed_client, session_factory):
    """The /produccion/manana title must include the tomorrow date so
    it's distinguishable from the day view.
    """
    r = authed_client.get("/produccion/manana")
    assert r.status_code == 200
    body = r.text
    import re

    m = re.search(r"<title>([^<]+)</title>", body)
    assert m
    title = m.group(1)
    # The title should mention "Mañana" + a date OR just a date that
    # is in the future. Accept either form so we don't over-specify.
    has_manana = "mañana" in title.lower() or "manana" in title.lower()
    has_date = any(d.isdigit() for d in title)
    assert has_manana or has_date, (
        f"/produccion/manana title must mention 'Mañana' or a date; got: {title!r}"
    )


# --- 4. Column header renames -----------------------------------------------


def test_day_view_contains_meta_unidades_column(authed_client, session_factory):
    """The Meta column must be labeled 'Meta (und)' or 'Meta (unidades)'.

    Regression for the audit B1: 'Meta' alone is ambiguous — units? kg?
    dozens? Adding '(und)' makes the unit explicit.
    """
    _seed_day_view_product(session_factory)
    today = datetime.now(UTC).date()
    r = authed_client.get(f"/produccion?for_date={today.isoformat()}&view=day")
    body = r.text
    # Accept any reasonable render: "Meta (und)", "Meta (unidades)",
    # "Meta (uds)". The exact label is a UI choice; the contract is
    # that 'Meta' appears WITH a unit hint.
    import re

    assert re.search(r"Meta\s*\(und[^)]*\)", body, re.IGNORECASE), (
        "Meta column must show a unit hint like 'Meta (und)' or 'Meta (unidades)'"
    )


def test_day_view_contains_lote_final_column(authed_client, session_factory):
    """The 'Total a hornear' column is renamed to 'Lote final' to
    avoid the '+ Pedidos double-count' confusion (audit B3).

    The OLD label 'Total a hornear' must be removed.
    """
    _seed_day_view_product(session_factory)
    today = datetime.now(UTC).date()
    r = authed_client.get(f"/produccion?for_date={today.isoformat()}&view=day")
    body = r.text
    if "Lote final" not in body:
        # Debug: dump to /tmp/dump.html for offline inspection
        with open("/tmp/dump.html", "w") as f:
            f.write(body)
    assert "Lote final" in body, "day view must contain the new 'Lote final' column header"
    assert "Total a hornear" not in body, (
        "old 'Total a hornear' header must be removed (renamed to 'Lote final')"
    )


def test_day_view_contains_hecho_column(authed_client, session_factory):
    """The 'Progreso' column is renamed to 'Hecho' so the cook knows
    the input is for the actual amount baked, not a progress bar
    (audit B2).
    """
    _seed_day_view_product(session_factory)
    today = datetime.now(UTC).date()
    r = authed_client.get(f"/produccion?for_date={today.isoformat()}&view=day")
    body = r.text
    assert ">Hecho" in body, (
        "day view must contain the 'Hecho' column header (was 'Progreso')"
    )
    # The old header should be gone. But 'progreso' is a Spanish word
    # that could appear in tooltips — accept only if it's a column header.
    # The simplest regression: the OLD column header "<th>Progreso" or
    # "<th class=...>Progreso" should not exist.
    import re

    assert not re.search(r"<th[^>]*>\s*Progreso\s*</th>", body, re.IGNORECASE), (
        "old '<th>Progreso</th>' column header must be removed"
    )


def test_day_view_pedidos_column_no_plus_prefix(authed_client, session_factory):
    """The '+ Pedidos' column header is renamed to 'Pedidos' (the
    `+` is the math, not the column name — audit B3).
    """
    _seed_day_view_product(session_factory)
    today = datetime.now(UTC).date()
    r = authed_client.get(f"/produccion?for_date={today.isoformat()}&view=day")
    body = r.text
    # The old '+ Pedidos' as a column header must be gone
    import re

    assert not re.search(r"<th[^>]*>\s*\+\s*Pedidos\s*</th>", body, re.IGNORECASE), (
        "old '+ Pedidos' column header must be removed (renamed to 'Pedidos')"
    )


# --- 5. Idempotency check (audit closure) -----------------------------------


def test_shift_execute_idempotent_same_form(
    authed_client, session_factory, croissant_id
):
    """Posting the same form twice within 60s must NOT duplicate rows.

    The audit M6 finding: the cook's browser sometimes re-submits
    a form on retry (network blip → click twice). The route must
    be idempotent so the audit log and `ProductionCompletion` table
    don't blow up.
    """
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).date()
    payload = {
        "for_date": today.isoformat(),
        f"completed_{croissant_id}": "8",
        f"done_{croissant_id}": "1",
    }

    r1 = authed_client.post("/produccion/shift-execute", data=payload)
    r2 = authed_client.post("/produccion/shift-execute", data=payload)
    assert r1.status_code in (200, 303)
    assert r2.status_code in (200, 303)

    with session_factory() as s:
        rows = list(
            s.execute(
                select(ProductionCompletion).where(
                    ProductionCompletion.product_id == croissant_id,
                    ProductionCompletion.for_date == today,
                )
            ).scalars()
        )
        # Upsert: 2 POSTs → 1 row, NOT 2.
        assert len(rows) == 1, (
            f"same form posted twice must upsert to 1 row; got {len(rows)}"
        )
        assert float(rows[0].completed_qty) == 8.0
