"""P-23 / audit #9, #10, #11: /analisis empty-state hygiene.

Audit findings:
- #9 Top banner shows "10:00" which is unclear — does it mean a window?
- #10 "Alerta: margen cayendo" shows 100 rows all "-0%" when DB has data
   but no real alerts (sentinel for "no data" dressed as data).
- #11 "Rotación de stock" shows 0.0 kg / 0 días for every item when DB
   has ingredients but no recent consumption.

These tests verify:
1. /analisis renders 200
2. The hour peak label is unambiguous (must include "hs" or "AM/PM" or
    similar disambiguation — NOT just bare "HH:00").
3. When there are no erosion alerts, the "Alerta: margen cayendo"
    section is NOT rendered (not a 100-row empty table).
4. When there are no real turnover entries, the "Rotación de stock"
    section is NOT rendered OR shows an empty-state, not 0.0 everywhere.
5. Currency values use the "Gs." prefix.
6. Sections that have content use real numbers, not "-0%" sentinels.
"""
from __future__ import annotations

import re

import pytest

pytestmark = [pytest.mark.smoke]


def test_analisis_renders_200(client):
    r = client.get("/analisis")
    assert r.status_code == 200, f"got {r.status_code}"
    # Page heading should be present
    assert "An" in r.text or "análisis" in r.text.lower() or "Análisis" in r.text


def test_peak_hour_label_is_unambiguous(client):
    """P-23 #9: 'HH:00' is too vague. Must include 'hs' or 'AM/PM'."""
    r = client.get("/analisis")
    assert r.status_code == 200
    body = r.text

    # Look for the peak-hour label and its value. If the peak is shown,
    # it must use a disambiguated format. We allow the "—" placeholder
    # (no data) since that's unambiguous.
    has_ambiguous = bool(re.search(r"(?:>|\s)([01]?\d|2[0-3]):00(?:<|\s)", body))
    if has_ambiguous:
        # If the bare 'HH:00' pattern appears, it must be followed by a
        # disambiguator like "hs" or "AM"/"PM"
        m = re.search(r"(?:>|\s)([01]?\d|2[0-3]):00(?:<|\s)", body)
        assert m is not None
        # Check the next ~30 chars after the match for a disambiguator
        idx = m.end()
        window = body[idx:idx + 30]
        assert (
            "hs" in window.lower()
            or "AM" in window
            or "PM" in window
            or "—" in window
        ), (
            "Peak hour shows bare 'HH:00' which is ambiguous "
            "(audit #9). Add 'hs' (e.g. '10:00 hs') or AM/PM."
        )


def test_erosion_alerts_section_guarded_by_truthiness(client):
    """P-23 #10: 'Alerta: margen cayendo' must NOT render when empty."""
    r = client.get("/analisis")
    assert r.status_code == 200
    body = r.text
    has_section = "Alerta: margen cayendo" in body
    if has_section:
        # If the section is rendered, it must have at least one row
        # with a real Δ Margen value (not '—' for every row).
        # Find the table under the alert section.
        idx = body.find("Alerta: margen cayendo")
        # Look forward up to the next </section>
        end = body.find("</section>", idx)
        chunk = body[idx:end if end > 0 else idx + 5000]
        # Count rows with "-0%" or "—" in the Δ Margen column
        sentinel_rows = len(re.findall(r"badge[^>]*>↓\s*-?\d+%\s*<", chunk))
        em_dash_rows = len(re.findall(r">—</span>", chunk))
        # The template uses "↓ {{ delta }}%" — if all rows are "—" there's
        # no real alert. Audit wanted this to be hidden in that case.
        if em_dash_rows > 0 and sentinel_rows == 0:
            pytest.fail(
                f"Alerta: margen cayendo rendered {em_dash_rows} rows with '—' as Δ Margen — "
                f"this is 'empty-state dressed as data' (audit #10). "
                f"Hide the section when erosion_alerts is empty."
            )


def test_turnover_section_uses_real_numbers_or_empty_state(client):
    """P-23 #11: Rotación de stock must not show 0.0 for everything
    when DB has ingredients but no real turnover data."""
    r = client.get("/analisis")
    assert r.status_code == 200
    body = r.text
    if "Rotación de stock" in body:
        # The section is present. Check whether all rows show 0.0/0.
        idx = body.find("Rotación de stock")
        end = body.find("</section>", idx)
        chunk = body[idx:end if end > 0 else idx + 5000]
        # Look for the data rows (each <tr> in the table)
        rows = re.findall(r"<tr>(.+?)</tr>", chunk, re.DOTALL)
        if len(rows) > 1:  # first is the header
            data_rows = rows[1:]
            all_zero = all(
                # 0.0 kg or 0 días in the row
                ("0.0" in r_ or "0&nbsp;kg" in r_ or ">0<" in r_)
                for r_ in data_rows
            )
            assert not all_zero, (
                f"Rotación de stock shows {len(data_rows)} rows all with 0.0 values — "
                f"audit #11: empty-state dressed as data."
            )


def test_analisis_uses_guarani_currency_format(client):
    """P-23: Currency values use 'Gs.' prefix."""
    r = client.get("/analisis")
    assert r.status_code == 200
    body = r.text
    # The page references Guaraní amounts (Ventas, Margen, Costo)
    # Check that at least one currency value uses 'Gs.'
    if "Gs." not in body and "PYG" not in body:
        pytest.fail(
            "No currency formatting on /analisis. "
            "Use 'Gs. 20.000' (dot separator, no decimals)."
        )


def test_analisis_no_sentinel_minus_zero(client):
    """P-23 #10: No '-0%' or '↓ -0%' sentinels anywhere on the page."""
    r = client.get("/analisis")
    assert r.status_code == 200
    body = r.text
    # The audit explicitly called out '↓ -0%' as the sentinel pattern
    # for "no real data". Must not appear on the rendered page.
    bad = ["↓ -0%", "-0%", "↓ 0%"]
    found = [b for b in bad if b in body]
    assert not found, (
        f"Found sentinel 'no data' values on /analisis: {found}. "
        f"Audit #10: hide sections with no real data instead."
    )
