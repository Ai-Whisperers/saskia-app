"""tests/test_reorder_scrape_endpoint.py — Phase 4 /reorder/scrape endpoint.

The endpoint runs the scrapers over a query and returns matches per
source. Tests focus on the empty-query path (no HTTP), the
graceful-degradation path (mocked scraper fails), and the happy path
against a mocked source.
"""

from __future__ import annotations

from app.integrations.scrapers import ScrapedPrice, ScrapeResult


def test_reorder_scrape_empty_query_returns_empty_no_http(client, monkeypatch):
    """Empty query → 200 with ok=True and zero matches everywhere."""

    def fake_scrape_all(query, sources=None):
        # Confirm scrape_all IS called even for empty query.
        assert query == ""
        return []

    # The endpoint imports inside the function, so patch the source module.
    monkeypatch.setattr("app.integrations.scrapers.scrape_all", fake_scrape_all)
    r = client.post("/reorder/scrape", data={"q": "   "})
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["ok"] is True
    assert payload["query"] == ""
    assert payload["sources"] == []


def test_reorder_scrape_runs_all_sources_and_aggregates(client, monkeypatch):
    """Endpoint must call scrape_all and serialize the results."""

    def fake_scrape_all(query, sources=None):
        return [
            ScrapeResult(
                source="superseis",
                query=query,
                matches=(
                    ScrapedPrice(
                        product_name="Harina Bianca 1kg",
                        price_gs=3600,
                        unit="kg",
                        url="https://www.superseis.com.py/product/337205",
                        source="superseis",
                    ),
                ),
            ),
            ScrapeResult(
                source="stock",
                query=query,
                error="Stock.com.py requiere navegador con JavaScript; usá /reorder/upload-prices",
            ),
        ]

    monkeypatch.setattr("app.integrations.scrapers.scrape_all", fake_scrape_all)
    r = client.post("/reorder/scrape", data={"q": "harina"})
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["query"] == "harina"
    by_src = {s["source"]: s for s in payload["sources"]}
    assert len(by_src["superseis"]["matches"]) == 1
    assert by_src["superseis"]["matches"][0]["price_gs"] == 3600
    assert by_src["superseis"]["matches"][0]["name"] == "Harina Bianca 1kg"
    assert by_src["stock"]["ok"] is False
    assert "CSV" in by_src["stock"]["error"] or "upload-prices" in by_src["stock"]["error"]


def test_reorder_scrape_writes_audit_row(client, monkeypatch, session_factory):
    """Successful scrape writes one audit row with the source list."""
    Session = session_factory

    def fake_scrape_all(query, sources=None):
        return [
            ScrapeResult(
                source="superseis",
                query=query,
                matches=(
                    ScrapedPrice(
                        product_name="x",
                        price_gs=100,
                        unit="",
                        url="u",
                        source="superseis",
                    ),
                ),
            ),
        ]

    monkeypatch.setattr("app.integrations.scrapers.scrape_all", fake_scrape_all)
    r = client.post("/reorder/scrape", data={"q": "leche"})
    assert r.status_code == 200
    assert r.json()["ok"]

    from app.rms.models import AuditLog

    with Session() as s:
        audits = s.query(AuditLog).filter(AuditLog.action == "read.scraper.run").all()
        assert len(audits) == 1
        assert audits[0].detail["query"] == "leche"
        assert audits[0].detail["match_count"] == 1


def test_reorder_scrape_audit_failure_does_not_break_scrape(client, monkeypatch):
    """If the audit write itself blows up, the scrape result is still 200.

    Operator might lose one audit row but the user gets their prices —
    price scraping is more valuable than the audit trace.
    """

    def fake_scrape_all(query, sources=None):
        return [ScrapeResult(source="superseis", query=query, matches=())]

    def boom(*a, **kw):
        raise RuntimeError("audit storage on fire")

    monkeypatch.setattr("app.integrations.scrapers.scrape_all", fake_scrape_all)
    monkeypatch.setattr("app.routers.reorder.audit_record", boom)
    r = client.post("/reorder/scrape", data={"q": "azucar"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
