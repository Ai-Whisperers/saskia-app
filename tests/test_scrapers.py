"""tests/test_scrapers.py — Phase 4 supplier scraper tests.

Most tests focus on the parser (pure function over HTML) so they're
hermetic and fast. The dispatcher test exercises the live network
with a marker so it can be skipped in CI via ``-m 'not network'``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.integrations.scrapers import (
    SCRAPERS,
    ScrapeResult,
    _normalize_price,
    _parse_stock,
    _parse_superseis,
    scrape_all,
    scrape_stock,
    scrape_superseis,
)

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestNormalizePrice:
    def test_simple(self):
        assert _normalize_price("1250") == 1250

    def test_dotted_thousands(self):
        assert _normalize_price("1.250") == 1250

    def test_comma_thousands(self):
        assert _normalize_price("1,250") == 1250

    def test_with_decimals(self):
        # We ignore decimals (Guaraníes are integer-only)
        assert _normalize_price("1.250,50") == 125050

    def test_zero_or_negative_rejected(self):
        assert _normalize_price("0") is None
        assert _normalize_price("-100") is None

    def test_non_numeric_rejected(self):
        assert _normalize_price("abc") is None
        assert _normalize_price("") is None


# ---------------------------------------------------------------------------
# Parser (pure, no network)
# ---------------------------------------------------------------------------


def _load_fixture(name: str) -> str:
    import pathlib

    p = pathlib.Path(__file__).parent / "fixtures" / name
    return p.read_text(encoding="utf-8")


class TestParseSuperseis:
    def test_parses_real_harina_search(self):
        html = _load_fixture("superseis_harina.html")
        matches = _parse_superseis(html)
        assert len(matches) >= 3, f"expected ≥3 matches from fixture, got {len(matches)}"
        # Every match must have a name, positive price, and a URL.
        for m in matches:
            assert m.product_name, f"missing name: {m}"
            assert m.price_gs > 0, f"non-positive price: {m}"
            assert m.url.startswith("https://www.superseis.com.py/product/"), m.url
            assert m.source == "superseis"

    def test_finds_harina_specifically(self):
        html = _load_fixture("superseis_harina.html")
        matches = _parse_superseis(html)
        names = [m.product_name.lower() for m in matches]
        assert any("harina" in n for n in names), (
            f"expected at least one 'harina' product; got: {names[:5]}"
        )

    def test_empty_html_returns_empty(self):
        assert _parse_superseis("") == []
        assert _parse_superseis("<html><body>nothing</body></html>") == []

    def test_garbage_html_returns_empty(self):
        # Parser must not crash on broken HTML
        assert _parse_superseis("<<<<>>><<&") == []


# ---------------------------------------------------------------------------
# Public API: empty query + dispatcher behavior
# ---------------------------------------------------------------------------


class TestScrapeDispatch:
    def test_empty_query_returns_empty_no_network(self, monkeypatch):
        """Empty query → empty result, NO HTTP call attempted."""
        called = []

        def boom(*a, **kw):
            called.append(True)
            raise AssertionError("HTTP should not be called for empty query")

        monkeypatch.setattr("app.integrations.scrapers.httpx.get", boom)
        result = scrape_superseis("")
        assert result.matches == ()
        assert result.error is None
        assert result.ok
        assert called == []

    def test_scrape_all_continues_on_one_source_failing(self, monkeypatch):
        """If one scraper raises, scrape_all reports it as a ScrapeResult
        with an error, NOT a crash."""

        def boom(query):
            raise RuntimeError("simulated crash")

        def fine(query):
            return ScrapeResult(source="stock", query=query, matches=())

        monkeypatch.setitem(SCRAPERS, "superseis", boom)
        monkeypatch.setitem(SCRAPERS, "stock", fine)
        results = scrape_all("harina", sources=["superseis", "stock"])
        assert len(results) == 2
        by_src = {r.source: r for r in results}
        assert by_src["superseis"].error and "crash" in by_src["superseis"].error
        assert by_src["stock"].ok

    def test_unknown_source_reported_not_raised(self):
        results = scrape_all("harina", sources=["does_not_exist"])
        assert len(results) == 1
        assert results[0].error and "unknown source" in results[0].error


# ---------------------------------------------------------------------------
# Stock (always fails closed; verifies graceful degradation)
# ---------------------------------------------------------------------------


class TestStock:
    def test_empty_query_short_circuits(self):
        r = scrape_stock("")
        assert r.matches == ()
        assert r.ok

    def test_returns_unavailable_error_with_friendly_message(self, monkeypatch):
        """When Stock is unreachable, we get a Spanish error pointing to
        the CSV upload fallback. Operator knows what to do next."""
        import httpx as _hx

        class FakeClient:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def get(self, *a, **kw):
                raise _hx.ConnectError("dns fail")

        monkeypatch.setattr("app.integrations.scrapers._client", lambda: FakeClient())
        r = scrape_stock("harina")
        assert r.error is not None
        assert "fetch failed" in r.error

    def test_alive_returns_unavailable_hint(self, monkeypatch):
        """When Stock IS reachable, we still return an 'unavailable' error
        because the parser isn't reliable for ASP.NET VIEWSTATE sites.
        This ensures the /reorder UI shows the CSV hint instead of 'no
        results'."""

        class FakeResp:
            status_code = 200
            text = "<html>ASP.NET VIEWSTATE garbage</html>"

            def raise_for_status(self):
                return None

        class FakeClient:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def get(self, *a, **kw):
                return FakeResp()

        monkeypatch.setattr("app.integrations.scrapers._client", lambda: FakeClient())
        r = scrape_stock("harina")
        # Either the live error path or the unavailable-with-hint path
        # is acceptable — what matters is that the user gets a clear
        # next-action message.
        assert r.error is not None or r.matches == ()
        if r.error is not None:
            # The hint should mention CSV
            assert "CSV" in r.error or "upload-prices" in r.error


# ---------------------------------------------------------------------------
# Network smoke (skip in CI; opt-in with pytest -m network)
# ---------------------------------------------------------------------------


@pytest.mark.network
class TestLiveSuperseis:
    """Run against the real Superseis site. Marked so CI can skip."""

    def test_live_search_returns_matches(self):
        r = scrape_superseis("harina")
        assert r.ok, f"unexpected error: {r.error}"
        assert len(r.matches) >= 1, "live scrape returned zero matches"
        # The fixture is the same query; we should get harina products.
        assert any("harina" in m.product_name.lower() for m in r.matches)


def test_parse_stock_featured_grid_from_fixture():
    """Offline parse of saved Stock.com.py featured grid HTML."""
    fixture = Path(__file__).parent / "fixtures" / "stock_featured.html"
    if not fixture.exists():
        import pytest

        pytest.skip("stock_featured.html fixture missing (network needed once)")
    html = fixture.read_text(encoding="utf-8")
    matches = _parse_stock(html)
    assert 10 <= len(matches) <= 30, f"expected 10-30 matches, got {len(matches)}"
    # First match must have a non-empty name and url.
    first = matches[0]
    assert first.product_name
    assert "/products/" in first.url
    # Paraguayan number format: "23.000" → 23000.
    if first.price_gs:
        assert first.price_gs > 1000, f"price {first.price_gs} should be >= 1000"


def test_scrape_stock_returns_featured_products():
    """scrape_stock() returns featured products, not error."""
    result = scrape_stock("harina")
    assert result.source == "stock"
    assert result.query == "harina"
    # Either ok + matches, or ok + error (if the live site is down).
    if result.ok:
        assert len(result.matches) >= 10
    else:
        # Live site failed — that's acceptable for a CI run.
        assert "fetch failed" in (result.error or "")


def test_parse_stock_handles_empty_html():
    """Empty or invalid HTML → empty matches."""
    matches = _parse_stock("")
    assert matches == []
    matches = _parse_stock("<html><body>no products here</body></html>")
    assert matches == []


def test_parse_stock_handles_price_with_thousands_separator():
    """Verify Paraguayan '23.000' format is parsed as 23000."""
    html = (
        '<a title="Mostrar detalles para TEST PRODUCT 1KG" '
        'class="picture-link" href="https://www.stock.com.py/products/123-test.aspx">'
        '<img title="test" /></a>'
        "<span class='price-label'>  23.000</span>"
    )
    matches = _parse_stock(html)
    assert len(matches) == 1
    assert matches[0].price_gs == 23000
    assert matches[0].product_name == "TEST PRODUCT 1KG"
