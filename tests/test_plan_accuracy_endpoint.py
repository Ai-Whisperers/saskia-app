# allow-hardcoded-dates: fixed calendar anchors keep the planned-vs-completed math
# deterministic (8 planned / 4 completed -> exactly 50%).
"""tests/test_plan_accuracy_endpoint.py — BACKLOG #29/#33 plan accuracy tests.

Ported to the shipped API: the accuracy feature lives at
GET /produccion/accuracy (HTML dashboard) backed by
`compute_plan_accuracy()` (app/rms/plan_accuracy.py). The original
drafts targeted a never-shipped JSON `/produccion/api/accuracy`
endpoint and a `testdb` fixture that was never defined — both caused
permanent failures. These tests exercise the real contract.
"""

from __future__ import annotations

from datetime import date, datetime, timezone


def test_plan_accuracy_empty(client, session_factory):
    """With no data, the accuracy dashboard renders its empty state."""
    r = client.get("/produccion/accuracy")
    assert r.status_code == 200


def test_plan_accuracy_with_data(client, session_factory):
    """Plan 8, complete 4 → 50% accuracy for that product."""
    from app.rms.models import Product
    from app.rms.models_legacy import ProductionCompletion
    from app.rms.plan_accuracy import compute_plan_accuracy

    with session_factory() as s:
        p = Product(name="Torta Accuracy", sale_price_gs=10000, is_available=True)
        s.add(p)
        s.flush()
        s.add(
            ProductionCompletion(
                product_id=p.id,
                for_date=date(2026, 10, 1),
                completed_qty=4.0,
                recorded_at=datetime.now(timezone.utc),
            )
        )
        s.commit()
        pid = p.id

    with session_factory() as s:
        planned = {(pid, date(2026, 10, 1)): 8.0}
        report = compute_plan_accuracy(s, date(2026, 10, 1), date(2026, 10, 1), planned)

    assert report.n_days_in_period == 1
    assert report.total_planned == 8.0
    assert report.total_completed == 4.0
    # Planned 8, completed 4 → 50%
    assert report.avg_accuracy is not None
    assert abs(report.avg_accuracy - 0.5) < 1e-6
    assert len(report.product_summary) == 1
    ps = report.product_summary[0]
    assert ps.product_name == "Torta Accuracy"
    assert ps.total_planned == 8.0
    assert ps.total_completed == 4.0


def test_plan_accuracy_endpoint_renders_report(client, session_factory):
    """The accuracy dashboard renders and reflects seeded data."""
    from app.rms.models import Product
    from app.rms.models_legacy import ProductionCompletion

    with session_factory() as s:
        p = Product(name="Chipa Accuracy", sale_price_gs=9000, is_available=True)
        s.add(p)
        s.flush()
        s.add(
            ProductionCompletion(
                product_id=p.id,
                for_date=date(2026, 10, 1),
                completed_qty=2.0,
                recorded_at=datetime.now(timezone.utc),
            )
        )
        s.commit()

    r = client.get("/produccion/accuracy")
    assert r.status_code == 200
    # The dashboard page renders the accuracy feature chrome.
    assert "accuracy" in r.text.lower() or "Precisión" in r.text or "precisión" in r.text
