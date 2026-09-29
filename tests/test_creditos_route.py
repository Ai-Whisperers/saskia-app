"""tests/test_creditos_route.py — /creditos photo-credits page (CC-BY attribution)."""


import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path/'cred.sqlite'}")
    monkeypatch.setenv("SASKIA_TEST_AUTH_DISABLED", "1")
    from app.rms import db as dbmod
    from app.rms.main import app

    dbmod.engine = dbmod.create_engine(f"sqlite:///{tmp_path/'cred.sqlite'}")
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_creditos_renders_attribution(client):
    r = client.get("/creditos")
    assert r.status_code == 200
    assert "Créditos de imágenes" in r.text
    # The bundled credits.json ships real CC-BY entries (33 photos)
    assert "CC-BY" in r.text or "CC BY" in r.text or "Openverse" in r.text


def test_creditos_lists_entries(client):
    r = client.get("/creditos")
    assert r.status_code == 200
    # each entry renders a source link
    assert r.text.count("ver original") >= 30
