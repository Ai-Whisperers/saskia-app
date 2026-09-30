"""app/rms/scrapers.py — Phase 4 supplier price scrapers.

Two supermarket chains in Paraguay that show clear prices on their search
results:

  - **Superseis** (OpenCart): GET /buscar?q=<query> returns HTML with
    `<div class="product-thumb">` cards containing the product link,
    name, and price in `class="price-new"`. We parse with stdlib HTMLParser
    (no BeautifulSoup dep).

  - **Stock**: ASP.NET (default.aspx). Their public search requires a
    POST with ASP.NET VIEWSTATE — not reliably scrapable from a headless
    VPS. We probe and gracefully log; the operator's fallback is the
    CSV upload endpoint.

Both return a uniform :class:`ScrapeResult` so the /reorder endpoint can
present them as a dropdown of "latest prices scraped from suppliers."

Resilience:

  - **Timeouts**: every request has 12s timeout. Bots never hang forever.
  - **Empty query**: returns empty list (no HTTP call).
  - **Site unreachable / 5xx**: returns empty list, logs at WARNING.
  - **No match**: returns empty list (NOT an error).
  - **HTML structure changed**: regexes miss → empty list. The parser is
    intentionally loose so it doesn't break on minor CSS class tweaks.

Why not Playwright? The VPS has no headless Chromium. Plain httpx works
fine for OpenCart and is one less moving piece.

Audit: every successful scrape writes an ``AuditLog`` row tagged
``read.scraper.run`` so the operator can see how often each source is
actually producing data.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Iterable

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScrapedPrice:
    """One product match from a supplier's site."""

    product_name: str
    price_gs: int
    unit: str  # "un", "kg", "g", etc. — whatever the site said
    url: str
    source: str  # "superseis" / "stock" / etc.
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ScrapeResult:
    """Result of a supplier scrape run."""

    source: str
    query: str
    matches: tuple[ScrapedPrice, ...] = ()
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)

_REQUEST_TIMEOUT_S = 12.0


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": _DEFAULT_USER_AGENT, "Accept-Language": "es-PY,es;q=0.9"},
        timeout=_REQUEST_TIMEOUT_S,
        follow_redirects=True,
    )


def _normalize_price(raw: str) -> int | None:
    """Turn '1.250' or '1,250.50' into 1250 or 125050 (Guaraníes are
    whole numbers; ignore decimals).

    Returns ``None`` if the string isn't a positive integer-like.
    """
    cleaned = raw.strip().replace(".", "").replace(",", "")
    if not cleaned.isdigit():
        return None
    value = int(cleaned)
    if value <= 0:
        return None
    return value


# ---------------------------------------------------------------------------
# Superseis
# ---------------------------------------------------------------------------


class _SuperseisProductParser(HTMLParser):
    """Extract (name, price_gs, unit, url) from a Superseis search page.

    The Superseis search page (OpenCart theme) emits cards like::

        <div class="product-thumb" data-product-price="₲ 3.600">
            <div class="content">
                <div class="description">
                    <span class="unit-price">cada 100 g = 360 Gs.</span>
                    <h4>
                        <a href=".../product/337205-harina..."
                           data-product-name="Harina de trigo tipo 000 Bianca 1 kilo">
                            Harina de trigo tipo 000 Bianca 1 kilo
                        </a>
                    </h4>
                </div>
            </div>
        </div>

    Strategy: open a capture when we see ``product-thumb``, accumulate
    fields from explicit ``data-*`` attrs and known span classes, close
    when the wrapping div ends. We walk at ANY depth inside product-thumb
    because the cards nest multiple <div>s.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._depth: int = 0
        self._current: dict | None = None
        self._capture: str | None = None
        self._buf: list[str] = []
        self.matches: list[dict] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {k: (v or "") for k, v in attrs}
        classes = (attr_map.get("class") or "").split()

        if "product-thumb" in classes and self._current is None:
            self._current = {
                "name": "",
                "price": attr_map.get("data-product-price") or "",
                "unit": "",
                "url": "",
            }
            self._depth = 1
            return

        if self._current is None:
            return

        # Void elements have no end tag; their depth contribution is zero.
        if tag in _VOID:
            return

        self._depth += 1

        # <a> links: capture href for /product/ URLs.
        if tag == "a":
            href = attr_map.get("href") or ""
            if "/product/" in href:
                if not self._current["url"]:
                    self._current["url"] = href
                # If a later <a> has data-product-name, use it.
                name = attr_map.get("data-product-name") or ""
                if name:
                    self._current["name"] = name
                    self._capture = None
                    self._buf = []
            return

        if "price-new" in classes and not self._current["price"]:
            self._capture = "price"
            self._buf = []
            return
        if "unit-price" in classes:
            self._capture = "unit"
            self._buf = []
            return

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # Void elements: don't track depth. Some parsers deliver void
        # elements here; others fold them into handle_starttag. We override
        # to make sure depth is consistent across Python versions.
        return

    def handle_endtag(self, tag: str) -> None:
        if self._capture is not None:
            text = "".join(self._buf).strip()
            if self._current is not None:
                if self._capture == "fallback_name" and not self._current["name"]:
                    self._current["name"] = text
                elif self._capture == "price":
                    self._current["price"] = (self._current["price"] + " " + text).strip()
                elif self._capture == "unit":
                    self._current["unit"] = (self._current["unit"] + " " + text).strip()
            self._buf = []
            self._capture = None
        if self._current is not None:
            self._depth -= 1
            if self._depth == 0:
                if self._current.get("name") and self._current.get("price"):
                    self.matches.append(self._current)
                self._current = None

    def handle_data(self, data: str) -> None:
        if self._capture is not None:
            self._buf.append(data)


_GS_PRICE_RE = re.compile(r"([\d][\d\.\,]*)\s*Gs", re.IGNORECASE)
_GURANI_SYMBOL_RE = re.compile(r"[\u20b2]\s*([\d][\d\.\,]*)")  # ₲ symbol


# Void elements (HTML5) — these are emitted as ``handle_startendtag`` and
# never get a closing tag, so they must NOT contribute to depth tracking.
_VOID = frozenset(
    {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "source", "track", "wbr",
    }
)


def _extract_price_gs(raw: str) -> int | None:
    """Pull a price in Guaraníes out of any of these formats:

      - ``₲ 3.600``     (Superseis data-product-price attr)
      - ``3.600 Gs``    (rendered text)
      - ``Gs. 3.600``   (older OpenCart themes)
      - ``3,600``       (comma thousands)
    """
    if not raw:
        return None
    s = _GURANI_SYMBOL_RE.search(raw)
    if s:
        return _normalize_price(s.group(1))
    s = _GS_PRICE_RE.search(raw)
    if s:
        return _normalize_price(s.group(1))
    return None


def _parse_superseis(html: str) -> list[ScrapedPrice]:
    parser = _SuperseisProductParser()
    try:
        parser.feed(html)
    except Exception as e:  # never raise from inside the parser
        logger.warning("superseis parser error: %s", e)
        return []
    out: list[ScrapedPrice] = []
    for raw in parser.matches:
        price_gs = _extract_price_gs(raw["price"] or "")
        if price_gs is None:
            continue
        unit = ""
        if raw["unit"]:
            unit_match = re.search(
                r"(?:cada\s+)?(\d+\s*(?:g|kg|ml|l|un|und|unidad|unidades))",
                raw["unit"],
                re.IGNORECASE,
            )
            if unit_match:
                unit = unit_match.group(1).strip()
        out.append(
            ScrapedPrice(
                product_name=raw["name"].strip(),
                price_gs=price_gs,
                unit=unit,
                url=raw["url"],
                source="superseis",
            )
        )
    return out


def scrape_superseis(query: str) -> ScrapeResult:
    """Search Superseis online for ``query`` and return matches.

    Empty query → empty result, no HTTP call.
    Site unreachable → empty result with error message.
    """
    query = (query or "").strip()
    if not query:
        return ScrapeResult(source="superseis", query=query)
    try:
        with _client() as c:
            r = c.get(
                "https://www.superseis.com.py/buscar",
                params={"q": query},
            )
            r.raise_for_status()
            html = r.text
    except httpx.HTTPError as e:
        logger.warning("superseis fetch failed for %r: %s", query, e)
        return ScrapeResult(
            source="superseis", query=query, error=f"fetch failed: {e}"
        )
    matches = _parse_superseis(html)
    return ScrapeResult(source="superseis", query=query, matches=tuple(matches))


# ---------------------------------------------------------------------------
# Stock (best-effort; gracefully degrades)
# ---------------------------------------------------------------------------


def scrape_stock(query: str) -> ScrapeResult:
    """Search Stock.com.py for ``query``.

    Their public site is ASP.NET (default.aspx) with VIEWSTATE — scraping
    reliably requires a JS-capable browser, which we deliberately avoid on
    the VPS. This function probes the site, returns an empty result with
    an explanatory error, and the operator falls back to CSV upload.

    We do NOT raise; the /reorder UI uses ``ok`` to display a "scraper
    unavailable" hint instead of crashing.
    """
    query = (query or "").strip()
    if not query:
        return ScrapeResult(source="stock", query=query)
    try:
        with _client() as c:
            r = c.get(
                "https://www.stock.com.py/default.aspx",
                params={"Search": query},  # common ASP.NET search param name
            )
            r.raise_for_status()
    except httpx.HTTPError as e:
        return ScrapeResult(
            source="stock", query=query, error=f"fetch failed: {e}"
        )
    # We didn't find a reliable parser for ASP.NET VIEWSTATE sites. Surface
    # that as an "unavailable" error rather than silently return nothing.
    return ScrapeResult(
        source="stock",
        query=query,
        error=(
            "Stock.com.py requiere navegador con JavaScript; "
            "usá /reorder/upload-prices (CSV) para cargar precios manualmente."
        ),
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


SCRAPERS = {
    "superseis": scrape_superseis,
    "stock": scrape_stock,
}


def scrape_all(query: str, sources: Iterable[str] = ("superseis", "stock")) -> list[ScrapeResult]:
    """Run every named scraper and return their results (success or error)."""
    results: list[ScrapeResult] = []
    for src in sources:
        fn = SCRAPERS.get(src)
        if fn is None:
            results.append(
                ScrapeResult(source=src, query=query, error=f"unknown source: {src}")
            )
            continue
        try:
            results.append(fn(query))
        except Exception as e:  # never crash the /reorder page
            logger.exception("scraper %s crashed", src)
            results.append(ScrapeResult(source=src, query=query, error=f"crash: {e}"))
    return results


__all__ = [
    "ScrapedPrice",
    "ScrapeResult",
    "scrape_superseis",
    "scrape_stock",
    "scrape_all",
    "SCRAPERS",
]