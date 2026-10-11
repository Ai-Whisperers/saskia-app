def test_customers_delete_soft_deletes(authed_client, session_factory):
    """POST /clientes/{id}/delete -> 303; subsequent GET -> 404 or 'archivado'."""
    from app.rms.models import Customer
    
    s = session_factory()
    c = make_customer(s, name="Delete me")
    s.commit()
    cid = c.id
    s.close()

    r = authed_client.post(f"/clientes/{cid}/delete", follow_redirects=False)
    assert r.status_code == 303

    s = session_factory()
    c2 = s.get(Customer, cid)
    assert c2.deleted_at is not None  # soft-deleted
    s.close()