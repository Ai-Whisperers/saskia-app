"""P-42: /reportes/ventas-hora should put the heatmap first.

Currently the page renders the by-hour table (line 21) BEFORE the
day-of-week × hour heatmap (line 81). The heatmap is the more
informative view; table should be secondary.

Acceptance:
  - GET /reportes/ventas-hora returns 200.
  - In the body, the heatmap element (.heatmap-grid) appears BEFORE
    the by-hour table.
  - A day-of-week filter exists (a <select> or set of links).
"""

from __future__ import annotations

import re


def test_reportes_ventas_hora_heatmap_first(client):
    """P-42: heatmap renders before the by-hour table."""
    r = client.get("/reportes/ventas-hora")
    assert r.status_code == 200
    body = r.text

    heatmap_idx = body.find('class="heatmap-grid"')
    assert heatmap_idx >= 0, "no .heatmap-grid in body"

    # The by-hour table is marked with class "table is-hoverable sortable".
    # We look for the FIRST occurrence of this class.
    table_match = re.search(r'<table[^>]*class="[^"]*table is-hoverable', body)
    assert table_match, "no by-hour table found"

    # Heatmap should be BEFORE the table.
    assert heatmap_idx < table_match.start(), (
        f"heatmap (idx={heatmap_idx}) should appear before the table (idx={table_match.start()})"
    )
