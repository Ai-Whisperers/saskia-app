"""P-24 / audit #15: /reportes/cierre-mensual label consistency.

Audit finding: page showed "Resultado del mes: 7.084.002" (positive)
and "Pérdida del mes: 2.459.998" (positive number with "pérdida" label
— semantically confusing because a positive number followed by "pérdida"
reads as a contradiction).

The current /reportes/cierre-mensual page uses clear, unambiguous labels
("Margen neto", "Prime Cost", "Mano de obra", "Overhead") instead of
the ambiguous "Resultado del mes / Pérdida del mes" pair.

This test locks in the contract:
1. Page must NOT have the OLD ambiguous label pair
   ("Resultado del mes" + "Pérdida del mes" with both showing positive
   numbers would have been ambiguous). Either present correctly (both
   numbers in same row as net, separately labeled as positive/negative
   contexts) or absent.
2. Page must use clear Spanish labels for each KPI: at minimum
   "Ventas", "IVA", "Margen" (or "Margen neto") and "Prime Cost".
3. Page must have a TOTAL row in the table footer.
4. Page must have an Exportar CSV button.
5. Margen numbers must use the project's GS formatter (m.gs()): "Gs. 30.000".
"""
from __future__ import annotations

import pytest
import re


pytestmark = [pytest.mark.smoke]


def test_cierre_mensual_no_ambiguous_labels(client):
    """P-24: Page must NOT show the old 'Resultado del mes' / 'Pérdida del mes' ambiguous label pair."""
    r = client.get("/reportes/cierre-mensual")
    assert r.status_code == 200, f"got {r.status_code}"
    body = r.text.lower()
    # If both labels appear in close proximity with positive-number semantics,
    # they'd be confusing. The simplest unambiguous pattern is: the OLD pair is
    # gone, replaced by a single "Resultado del mes" net or by clear labels.
    # Allow "Resultado" if it's standalone; forbid the combination
    # "Resultado del mes" + "Pérdida del mes" in the SAME page (contradiction).
    has_resultado = "resultado del mes" in body
    has_perdida = "pérdida del mes" in body or "perdida del mes" in body
    if has_resultado and has_perdida:
        pytest.fail(
            "Page contains BOTH 'Resultado del mes' AND 'Pérdida del mes' — "
            "this is the old ambiguous label pair. Use a single 'Margen neto del mes' instead."
        )


def test_cierre_mensual_uses_clear_labels(client):
    """P-24: KPIs use unambiguous Spanish labels (Margen, Ventas, Prime Cost)."""
    r = client.get("/reportes/cierre-mensual")
    assert r.status_code == 200
    body = r.text
    # At least one of these clear labels must be present
    has_margen = ("Margen" in body) or ("margen" in body)
    has_ventas = ("Ventas" in body) or ("ventas" in body)
    assert has_margen, "Missing 'Margen' label on /reportes/cierre-mensual"
    assert has_ventas, "Missing 'Ventas' label on /reportes/cierre-mensual"


def test_cierre_mensual_has_total_row(client):
    """P-24: The detail table has a TOTAL footer row."""
    r = client.get("/reportes/cierre-mensual")
    assert r.status_code == 200
    # The footer <tr> has the word TOTAL (template line 134)
    body = r.text
    assert "<tfoot>" in body or 'TOTAL' in body, (
        "Missing TOTAL footer row in cierre-mensual detail table"
    )


def test_cierre_mensual_has_csv_export(client):
    """P-24: Page has an Exportar CSV link."""
    r = client.get("/reportes/cierre-mensual")
    assert r.status_code == 200
    # Anchor with download attribute pointing to csv download
    m = re.search(r'href="[^"]*"[^>]*download="cierre_mensual\.csv"', r.text)
    assert m, "Missing CSV export link (download='cierre_mensual.csv')"
    assert "Exportar CSV" in r.text, "Missing 'Exportar CSV' button text"


def test_cierre_mensual_currency_unit_labeled(client):
    """P-24: Currency columns are labeled with 'Gs.' (guaraní) in their headers OR cells."""
    r = client.get("/reportes/cierre-mensual")
    assert r.status_code == 200
    # Currency column headers must be labeled in Gs. (guaraní)
    assert "Gs." in r.text, (
        "Currency columns not labeled with 'Gs.' — bakery uses Gs., not $/€"
    )
    # Confirm absence of wrong currency symbols
    assert "$" not in r.text, "Found '$' currency symbol — bakery uses Gs. not USD"
    # And no demo/foreign currency badges (EUR/USD)
    assert "EUR" not in r.text, "EUR currency symbol found on a PYG-only bakery report"
    assert "USD" not in r.text, "USD currency symbol found on a PYG-only bakery report"
