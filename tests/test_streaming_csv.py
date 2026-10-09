"""Tests for app/rms/streaming_csv.stream_csv_rows."""

from __future__ import annotations

import csv
from io import StringIO

from app.rms.streaming_csv import _join_row, stream_csv_rows


def _materialize(gen):
    """Materialize a generator into a single string (concat all yields)."""
    return "".join(gen)


def test_header_only():
    """When rows is empty, only the header line is yielded (plus BOM if asked)."""
    out = _materialize(stream_csv_rows(["a", "b", "c"], []))
    assert out == "a,b,c\r\n"


def test_bom_present_when_asked():
    out = _materialize(stream_csv_rows(["x"], [], bom=True))
    # First yielded character must be the UTF-8 BOM (U+FEFF)
    assert out.startswith("\ufeff")
    # And then the header
    assert "\ufeffx\r\n" in out


def test_bom_absent_by_default():
    out = _materialize(stream_csv_rows(["x"], [["1", "2"]]))
    assert not out.startswith("\ufeff")


def test_rows_with_special_characters():
    rows = [
        ["plain", "value"],
        ["has,comma", "value"],
        ['has"quote', "value"],
        ["has\nnewline", "value"],
        ["unicode ñ á", "valor"],
    ]
    out = _materialize(stream_csv_rows(["col1", "col2"], rows))
    # Re-parse to verify roundtrip
    parsed = list(csv.reader(StringIO(out)))
    assert parsed[0] == ["col1", "col2"]
    assert parsed[1:] == rows


def test_lazy_iteration():
    """A generator should not be consumed until the caller iterates."""
    consumed = {"flag": False}

    def gen():
        consumed["flag"] = True
        yield ["a", "1"]
        yield ["b", "2"]

    out_iter = stream_csv_rows(["x", "y"], gen())
    assert consumed["flag"] is False, "Generator materialized before iteration"
    out = _materialize(out_iter)
    assert consumed["flag"] is True
    assert "a,1\r\n" in out and "b,2\r\n" in out


def test_join_row_no_trailing_newline():
    s = _join_row(["a", "b"])
    assert s == "a,b"
    assert not s.endswith("\n")
    assert not s.endswith("\r")


def test_large_iterable_does_not_buffer():
    """Streaming is key: a 100k-row iterable must yield incrementally."""
    rows = [[i, str(i)] for i in range(100_000)]

    def it():
        for r in rows:
            yield r

    gen = stream_csv_rows(["id", "val"], it())
    # Pull just the first data line and assert no buffering
    first_data = next(gen)  # skips header automatically? No, header is first yield.
    # First yield is header
    assert first_data == "id,val\r\n"
    second = next(gen)
    assert second == "0,0\r\n"


def test_crlf_line_endings():
    """CSV RFC 4180 calls for CRLF. Excel handles both, but Excel-PY prefers CRLF."""
    out = _materialize(stream_csv_rows(["a"], [["1"]]))
    assert out == "a\r\n1,b\r\n".replace("a\r\n", "a\r\n").replace("1,b", "1")
    # Reconstruct more carefully:
    parts = out.split("\r\n")
    assert parts == ["a", "1", ""]


def test_field_with_comma_is_quoted():
    out = _materialize(stream_csv_rows(["x"], [["a,b"]]))
    assert '"a,b"' in out


def test_field_with_newline_is_quoted():
    out = _materialize(stream_csv_rows(["x"], [["line1\nline2"]]))
    assert '"line1\nline2"' in out
