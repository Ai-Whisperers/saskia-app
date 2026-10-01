"""app/rms/streaming_csv.py — streaming CSV response generator.

Phase 14 (mid-tier): the four export.csv endpoints in /auditoria,
/inventario, /recetas, /ventas previously loaded the full result set
into a StringIO and returned ``Response(content=...)``. For a year of
sales that's tens of MB held in memory per request — and concurrent
exports compound. This helper yields rows one at a time so memory stays
constant regardless of result size.

Pattern::

    return StreamingResponse(
        stream_csv_rows(header, row_iter),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={name}"},
    )

``stream_csv_rows`` is a *sync* generator (the caller wraps it via
``StreamingResponse(..., media_type="text/csv")``; FastAPI runs sync
generators in a threadpool, so blocking DB iteration is fine).

The header is written once; UTF-8 BOM is preserved when the caller
opts in via ``bom=True`` (Excel PY needs it for accent rendering).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator, Sequence
from io import StringIO


def _join_row(row: Sequence[object]) -> str:
    """Format one row into a CSV string (no trailing newline)."""
    buf = StringIO()
    csv.writer(buf).writerow(row)
    # csv.writer always appends \r\n; strip it so the caller controls
    # line endings.
    return buf.getvalue().rstrip("\r\n")


def stream_csv_rows(
    header: Sequence[str],
    rows: Iterable[Sequence[object]],
    *,
    bom: bool = False,
) -> Iterator[str]:
    """Yield CSV lines: header first (or BOM + header), then one line per row.

    ``rows`` may be a list, generator, or SQLAlchemy ``.scalars()`` result.
    Iteration is lazy — the consumer controls the pace.
    """
    if bom:
        yield "\ufeff"
    yield _join_row(header) + "\r\n"
    for row in rows:
        # csv.writer escapes commas/quotes/newlines correctly.
        yield _join_row(row) + "\r\n"