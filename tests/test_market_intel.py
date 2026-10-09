"""tests/test_market_intel.py — market-intel: evidencia de competencia retail.

Cubre: modelo CompetitorPriceObservation, stats por familia, seed
idempotente, rutas /vs-mercado (columna mercado real), /vs-mercado/evidencia,
evidencia.csv y el importador con confirmación.
"""
# allow-hardcoded-dates: fixed instants for deterministic assertions

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.rms.models import CompetitorPriceObservation
from app.rms.seed.competitor_prices import (
    COMPETITOR_SEED,
    COMPETITOR_SEED_SHOPPINGS,
    seed_competitor_prices,
)


def _mk(
    session,
    comp="Karu",
    item="Cheesecake porción",
    fam="tortas",
    price=32000,
    as_of="2026-09-30",
    unit="unidad",
    source="https://karu.com.py",
):
    session.add(
        CompetitorPriceObservation(
            competitor_name=comp,
            competitor_type="cafetería",
            city="Asunción",
            product_name=item,
            family=fam,
            unit=unit,
            price_gs=price,
            as_of=date.fromisoformat(as_of),
            source=source,
        )
    )
    session.commit()


def test_migration_creates_table(app_engine):
    from sqlalchemy import inspect as sa_inspect

    insp = sa_inspect(app_engine)
    assert "competitor_price_observation" in insp.get_table_names()


def test_family_stats_percentiles(session_factory):
    s = session_factory()
    # tortas: 5 precios conocidos
    for i, p in enumerate([8000, 12000, 16000, 22000, 32000]):
        _mk(s, comp=f"L{i}", item=f"Torta {i}", fam="tortas", price=p)
    from app.rms.market_intel import stats_by_family

    st = stats_by_family(s).get("tortas")
    assert st is not None
    assert st.n == 5
    assert st.min_gs == 8000
    assert st.max_gs == 32000
    assert st.median_gs == 16000
    assert 8000 <= st.p25_gs <= 12000
    assert 22000 <= st.p75_gs <= 32000


def test_family_of_heuristics(session_factory):
    from app.rms.market_intel import family_of

    assert family_of("Cheesecake de frutos rojos (porción)") == "tortas"
    assert family_of("Medialuna de manteca rellena") == "facturas"
    assert family_of("Stroopwafel artesanal") == "stroopwafels"
    assert family_of("Café Latte (Caliente)") == "cafes"
    assert family_of("Té en hebras") == "tes"
    # combos NO son evidencia de precio unitario
    assert family_of("Desayuno Del Sur (cocido con leche, chipitas)") is None
    assert family_of("Promo 12 medialunas") is None


def test_seed_competitor_prices_idempotent(session_factory):
    s = session_factory()
    added1, _skip1 = seed_competitor_prices(s)
    total_seed = len(COMPETITOR_SEED) + len(COMPETITOR_SEED_SHOPPINGS)
    assert added1 == total_seed > 0
    added2, skip2 = seed_competitor_prices(s)
    assert added2 == 0
    assert skip2 == total_seed
    n = s.query(CompetitorPriceObservation).count()
    assert n == total_seed


def test_vs_mercado_shows_intel_columns(client, session_factory):
    s = session_factory()
    _mk(
        s,
        comp="El Café de Acá",
        item="Cheesecake de frutos rojos (porción)",
        fam="tortas",
        price=29000,
    )
    _mk(s, comp="Karu", item="Cheesecake", fam="tortas", price=32000)
    r = client.get("/vs-mercado")
    assert r.status_code == 200
    assert "Mercado real" in r.text
    assert "Evidencia de mercado" in r.text


def test_evidencia_view_and_csv(client, session_factory):
    s = session_factory()
    _mk(s)
    r = client.get("/vs-mercado/evidencia")
    assert r.status_code == 200
    assert "Karu" in r.text
    rcsv = client.get("/vs-mercado/evidencia.csv")
    assert rcsv.status_code == 200
    assert "competidor" in rcsv.text
    assert "Karu" in rcsv.text
    assert "32000" in rcsv.text


def test_import_requires_confirmation(client):
    r = client.post(
        "/vs-mercado/evidencia/importar",
        data={"confirmar": "no"},
        files={"csv": ("x.csv", b"a,b\n1,2", "text/csv")},
    )
    assert r.status_code in (400, 422)


def test_import_csv_happy_and_rejects(client, session_factory):
    s = session_factory()
    base = s.query(CompetitorPriceObservation).count()  # seed lifespan = 86
    assert base > 0
    csv_body = (
        "competidor,tipo,ciudad,producto,familia,unidad,precio_gs,as_of,fuente\n"
        "La Vienesa,confitería,Asunción,Medialuna ddl,facturas,unidad,9000,2026-10-01,https://lavienesa.com.py\n"
        "SinFuente,café,Asunción,Latte,cafes,unidad,20000,2026-10-01,\n"
        "Barato,café,Asunción,Espresso,cafes,unidad,50,2026-10-01,https://x.com\n"
        "La Vienesa,confitería,Asunción,Medialuna ddl,facturas,unidad,9000,2026-10-01,https://lavienesa.com.py\n"
    ).encode()
    r = client.post(
        "/vs-mercado/evidencia/importar",
        data={"confirmar": "si"},
        files={"csv": ("evidencia.csv", csv_body, "text/csv")},
        follow_redirects=False,
    )
    assert r.status_code == 303
    rows = s.execute(select(CompetitorPriceObservation)).scalars().all()
    # solo 1 fila nueva: sin-fuente y precio-50 rechazadas, la 4ta es duplicado
    assert len(rows) == base + 1
    vie = [x for x in rows if x.product_name == "Medialuna ddl"]
    assert len(vie) == 1
    assert vie[0].price_gs == 9000
    assert vie[0].family == "facturas"
    assert vie[0].source.startswith("https://")
    assert not any(x.competitor_name in ("SinFuente", "Barato") for x in rows)
