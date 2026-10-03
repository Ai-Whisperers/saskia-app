"""P3 dietary batch: customer restrictions + preference ordering.

- Migration 070: customer.dietary_restrictions / dietary_preferences /
  dietary_confirm_always.
- /clientes/{id}/editar saves the profile (restrictions canonical-only,
  preferences JSON ordered, confirm-always flag).
- /clientes/{id} renders the alert card.
- /customers/api/search carries dietary payload for pickers.
- /clientes/{id} 500 regression (naive vs aware datetime, ref
  9da40358ea00) — see test_cliente_detalle_tz.py.
"""

from __future__ import annotations

from app.rms.customer_dietary import (
    DietaryPreference,
    format_preferences,
    format_restrictions,
    load_profile,
    parse_preferences,
    parse_restrictions,
)
from tests.factories import make_customer, make_product

# ── Parsing helpers ──────────────────────────────────────────────────────

def test_parse_restrictions_dedupes_and_strips():
    assert parse_restrictions("sin lactosa, sin gluten ,sin lactosa") == [
        "sin lactosa",
        "sin gluten",
    ]
    assert parse_restrictions(None) == []
    assert parse_restrictions("") == []


def test_parse_preferences_orders_by_rank():
    raw = '[{"tag": "leche de coco", "rank": 2, "note": ""}, {"tag": "leche de almendra", "rank": 1, "note": "marca X"}]'
    prefs = parse_preferences(raw)
    assert [p.tag for p in prefs] == ["leche de almendra", "leche de coco"]
    assert prefs[0].note == "marca X"


def test_parse_preferences_survives_garbage():
    assert parse_preferences("not json") == []
    assert parse_preferences('{"tag": "x"}') == []  # dict, not list
    assert parse_preferences(None) == []


def test_roundtrip_format_parse():
    prefs = [DietaryPreference(tag="sin lactosa", rank=1, note="almendra")]
    assert parse_preferences(format_preferences(prefs))[0].tag == "sin lactosa"
    assert parse_restrictions(format_restrictions(["vegano"])) == ["vegano"]


def test_load_profile_full():
    profile = load_profile("sin lactosa,vegano", '[{"tag": "coco", "rank": 1, "note": ""}]', 1)
    assert profile.restrictions == ["sin lactosa", "vegano"]
    assert profile.preferences[0].tag == "coco"
    assert profile.confirm_always is True
    assert profile.has_alerts


# ── Save via the edit form ───────────────────────────────────────────────

def test_cliente_editar_saves_dietary_profile(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="DietSave UX")
        s.commit()
        cid = c.id
    r = client.post(
        f"/clientes/{cid}/editar",
        data={
            "name": "DietSave UX",
            "phone": "0983112233",
            "notes": "",
            "dietary_restriction": ["sin lactosa", "sin gluten", "fake-tag"],
            "dietary_prefs_payload": '[{"tag": "leche de almendra", "rank": 1, "note": "marca X"}]',
            "dietary_confirm_always": "1",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    from app.rms.models import Customer
    with session_factory() as s:
        c = s.get(Customer, cid)
        assert "sin lactosa" in (c.dietary_restrictions or "")
        assert "sin gluten" in (c.dietary_restrictions or "")
        assert "fake-tag" not in (c.dietary_restrictions or "")  # canonical-only
        prefs = parse_preferences(c.dietary_preferences)
        assert prefs and prefs[0].tag == "leche de almendra"
        assert c.dietary_confirm_always is True


def test_cliente_editar_clears_profile(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="DietClear UX")
        c.dietary_restrictions = "vegano"
        s.commit()
        cid = c.id
    client.post(
        f"/clientes/{cid}/editar",
        data={"name": "DietClear UX", "phone": "", "notes": "",
              "dietary_restriction": [], "dietary_prefs_payload": ""},
        follow_redirects=False,
    )
    from app.rms.models import Customer
    with session_factory() as s:
        c = s.get(Customer, cid)
        assert c.dietary_restrictions is None
        assert c.dietary_confirm_always is False


# ── Display surfaces ─────────────────────────────────────────────────────

def test_cliente_detalle_shows_dietary_alert(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="DietShow UX")
        c.dietary_restrictions = "sin lactosa"
        c.dietary_preferences = '[{"tag": "leche de almendra", "rank": 1, "note": "marca X"}]'
        c.dietary_confirm_always = True
        s.commit()
        cid = c.id
    r = client.get(f"/clientes/{cid}")
    assert r.status_code == 200
    body = r.text
    assert "Perfil dietético" in body
    assert "sin lactosa" in body
    assert "leche de almendra" in body
    assert "Preguntar siempre" in body


def test_cliente_detalle_no_alert_when_clean(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="DietClean UX")
        s.commit()
        cid = c.id
    r = client.get(f"/clientes/{cid}")
    assert r.status_code == 200
    assert "Perfil dietético" not in r.text


def test_customer_search_api_carries_dietary(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="DietApi Uniqueover UX")
        c.dietary_restrictions = "sin gluten,sin lactosa"
        c.dietary_confirm_always = True
        s.commit()
    r = client.get("/clientes/api/search?q=DietApi+Uniqueover")
    assert r.status_code == 200
    results = r.json()["results"]
    assert results, "customer must be found"
    top = results[0]
    assert "sin gluten" in top["dietary_restrictions"]
    assert top["dietary_confirm_always"] is True


def test_cliente_editar_form_renders_profile_ui(client, session_factory):
    with session_factory() as s:
        c = make_customer(s, name="DietForm UX")
        c.dietary_restrictions = "vegano"
        s.commit()
        cid = c.id
    r = client.get(f"/clientes/{cid}/editar")
    assert r.status_code == 200
    body = r.text
    assert "Perfil dietético" in body
    assert 'name="dietary_restriction"' in body
    assert "dietary-pref-add" in body
    assert "dietary_confirm_always" in body
    # the saved restriction is pre-checked
    assert 'value="vegano" checked' in body or ('checked' in body and 'vegano' in body)


# ── Pedidos form: dietary alert markup present ───────────────────────────

def test_pedidos_nuevo_has_dietary_alert_element(client, session_factory):
    with session_factory() as s:
        make_product(s, name="DietPedProd UX")
        s.commit()
    r = client.get("/pedidos/nuevo")
    assert r.status_code == 200
    assert 'id="dietary-alert"' in r.text


def test_ventas_customer_card_has_dietary_chip(client):
    r = client.get("/ventas")
    assert r.status_code == 200
    assert "customer-card-dietary-chip" in r.text
