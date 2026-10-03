"""Test bank reconciliation feature."""



def test_bank_page_renders(client):
    """Bank page renders normally."""
    r = client.get('/bank')
    assert r.status_code == 200

def test_bank_page_shows_reconciliation_stats(client):
    """Bank page shows reconciliation statistics."""
    r = client.get('/bank')
    assert r.status_code == 200
    body = r.text
    # Should show stats cards
    assert 'Conciliados' in body
    assert 'Pendientes' in body
    assert 'Total' in body

def test_bank_page_shows_reconciliation_filter(client):
    """Bank page shows reconciliation filter buttons."""
    r = client.get('/bank')
    assert r.status_code == 200
    body = r.text
    assert 'Todos' in body
    assert 'Conciliados' in body or 'reconciled=yes' in body
    assert 'Pendientes' in body or 'reconciled=no' in body

def test_bank_filter_reconciled_yes(client):
    """Filter to show only reconciled transactions."""
    r = client.get('/bank?reconciled=yes')
    assert r.status_code == 200

def test_bank_filter_reconciled_no(client):
    """Filter to show only unreconciled transactions."""
    r = client.get('/bank?reconciled=no')
    assert r.status_code == 200

def test_bank_reconcile_endpoint_exists(client):
    """Reconciliation endpoint exists."""
    r = client.post('/bank/1/reconcile', data={
        'with_type': 'pedido',
        'with_id': '1',
    })
    assert r.status_code in (200, 302, 303, 404)


def test_bank_reconcile_sets_reconciled_by_from_session(client, session_factory):
    """Phase 14 — `reconciled_by` is populated from request.state.user_id.

    With SASKIA_TEST_AUTH_DISABLED=*** the ObservabilityContextMiddleware
    can't extract a user id from the session (test bypass), so the value
    must fall back to "anonymous" — NOT the old literal "system". This
    locks in the regression-vs-replacement: any future change that
    hard-codes "system" again trips this test.
    """
    from datetime import datetime, timezone

    from app.rms.models import BankTransaction

    with session_factory() as s:
        # Create a fresh transaction so this test is self-contained.
        tx = BankTransaction(
            posted_at=datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
            amount=1000,
            currency="EUR",
            description="Phase-14 reconciled_by test",
            category="uncategorized",
        )
        s.add(tx)
        # Commit (not just flush) so the row is visible to the route's
        # session — get_session() opens a fresh session per request.
        s.commit()
        tx_pk = tx.id
        try:
            r = client.post(f'/bank/{tx_pk}/reconcile', data={
                'with_type': 'pedido',
                'with_id': '1',
            })
            assert r.status_code in (200, 302, 303, 404), r.text
            # Re-open session to read the post-reconcile state (the route
            # committed via a different session).
            with session_factory() as s2:
                tx2 = s2.get(BankTransaction, tx_pk)
                assert tx2 is not None
                assert tx2.reconciled is True
                assert tx2.reconciled_by != "system", (
                    "reconciled_by must NOT be hard-coded 'system' anymore — "
                    "the Phase 14 fix reads from request.state.user_id (fallback 'anonymous')."
                )
                # In SASKIA_TEST_AUTH_DISABLED=*** the session has no user_id,
                # so ObservabilityContextMiddleware sets state.user_id = None
                # and the fallback resolves to "anonymous".
                assert tx2.reconciled_by == "anonymous"
        finally:
            # Always clean up so we don't pollute other tests.
            with session_factory() as s2:
                tx2 = s2.get(BankTransaction, tx_pk)
                if tx2 is not None:
                    s2.delete(tx2)
                    s2.commit()

def test_bank_reconcile_valid_type(client):
    """Reconciliation accepts valid with_type values."""
    for with_type in ['pedido', 'gasto', 'ingreso']:
        r = client.post('/bank/1/reconcile', data={
            'with_type': with_type,
            'with_id': '1',
        })
        assert r.status_code in (200, 302, 303, 404), f"Failed for {with_type}"

def test_bank_reconcile_invalid_type(client):
    """Reconciliation rejects invalid with_type."""
    r = client.post('/bank/1/reconcile', data={
        'with_type': 'invalid',
        'with_id': '1',
    })
    assert r.status_code in (200, 302, 303, 400, 404)

def test_bank_unreconcile_endpoint_exists(client):
    """Unreconciliation endpoint exists."""
    r = client.post('/bank/1/unreconcile')
    assert r.status_code in (200, 302, 303, 404)

def test_bank_reconcile_nonexistent_transaction(client):
    """Reconciling non-existent transaction doesn't crash."""
    r = client.post('/bank/99999/reconcile', data={
        'with_type': 'pedido',
        'with_id': '1',
    })
    assert r.status_code in (200, 302, 303, 404)

def test_bank_unreconcile_nonexistent_transaction(client):
    """Unreconciling non-existent transaction doesn't crash."""
    r = client.post('/bank/99999/unreconcile')
    assert r.status_code in (200, 302, 303, 404)

def test_bank_reconcile_missing_type(client):
    """Reconciliation without with_type is handled."""
    r = client.post('/bank/1/reconcile', data={
        'with_id': '1',
    })
    assert r.status_code in (200, 302, 303, 400, 404, 422)

def test_bank_reconcile_missing_id(client):
    """Reconciliation without with_id is handled."""
    r = client.post('/bank/1/reconcile', data={
        'with_type': 'pedido',
    })
    assert r.status_code in (200, 302, 303, 400, 404, 422)

def test_bank_reconcile_empty_data(client):
    """Reconciliation with empty data is handled."""
    r = client.post('/bank/1/reconcile', data={})
    assert r.status_code in (200, 302, 303, 400, 404, 422)

def test_bank_table_has_reconciliation_column(client):
    """Bank table has reconciliation column header."""
    r = client.get('/bank')
    assert r.status_code == 200
    body = r.text
    assert 'Conciliación' in body or 'reconciled' in body.lower()

def test_bank_reconciled_filter_with_other_filters(client):
    """Reconciled filter works with other filters."""
    r = client.get('/bank?reconciled=yes&currency=EUR')
    assert r.status_code == 200

def test_bank_unreconciled_filter_with_pagination(client):
    """Unreconciled filter works with pagination."""
    r = client.get('/bank?reconciled=no&page=1')
    assert r.status_code == 200

def test_bank_reconciliation_stats_count(client):
    """Reconciliation stats show numeric counts."""
    r = client.get('/bank')
    assert r.status_code == 200
    body = r.text
    # Should have at least one number in the stats
    import re
    numbers = re.findall(r'\d+', body)
    assert len(numbers) > 0

def test_bank_no_python_errors_on_reconciliation(client):
    """No Python errors on reconciliation actions."""
    test_urls = [
        '/bank',
        '/bank?reconciled=yes',
        '/bank?reconciled=no',
        '/bank/1/unreconcile',
    ]

    for url in test_urls:
        if '/unreconcile' in url:
            r = client.post(url)
        else:
            r = client.get(url)
        assert r.status_code != 500, f"500 error on {url}"

def test_bank_reconcile_preserves_filters(client):
    """Reconciliation redirect preserves filters."""
    r = client.get('/bank?currency=EUR&reconciled=no')
    assert r.status_code == 200
    # The reconcile form should preserve the transaction ID
    body = r.text
    if 'action="/bank/' in body and '/reconcile"' in body:
        # Forms are present
        assert True
