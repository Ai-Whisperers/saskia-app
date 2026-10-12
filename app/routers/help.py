"""app/routers/help.py — serves the user guide as rendered HTML.

GET /guia               — index page with TOC
GET /guia/{section}     — individual section (e.g. /guia/02-ventas)

The markdown lives in docs/user-guide/. We convert it to HTML at
request time using Python's markdown library (already pinned in
pyproject.toml as a transitive dep of pytest — if not, see the
fallback to plain-text rendering).
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.auth import require_login_or_disabled as require_login
from app.services.template_render import render

router = APIRouter(prefix="/guia", dependencies=[Depends(require_login)])

GUIDE_DIR = Path(__file__).resolve().parents[2] / "docs" / "user-guide"


# --- inline rendering (called per-text-fragment, inside block producers) ---


def _escape_html(text: str) -> str:
    """Escape `& < >` so Markdown syntax chars don't become live HTML.

    MUST be called first inside `_apply_inline` — see test_security_dynamic.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _safe_url(url: str) -> str:
    """Allow only http/https/relative paths; reject javascript:/vbscript:/data:.

    XSS guard (test_security_dynamic::test_md_to_html_blocks_xss).
    """
    url = url.strip()
    if re.match(r"https?://", url) or url.startswith("/"):
        return url
    return "#"


def _apply_inline(text: str) -> str:
    """Apply inline markdown to a single text fragment.

    Order matters for security (test_security_dynamic):
      1. Escape HTML (so `<script>` becomes inert text).
      2. Apply bold/italic/code/links (regex on the escaped string).

    Links use `_safe_url` to reject javascript: and vbscript: schemes.
    """
    text = _escape_html(text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?![*\w])", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{_safe_url(m.group(2))}">{m.group(1)}</a>',
        text,
    )
    return text


# --- block producers (return HTML for a buffered region) ---


def _flush_table(buf: list[str]) -> str:
    """Render a buffered table to HTML.

    Pipe-table grammar: `| col | col |`, optional `|---|---|` separator.
    If the buffer doesn't form a real table (fewer than 2 real rows), fall
    back to `<pre>` rendering so the markdown source is still readable.
    """
    if not buf:
        return ""
    rows = _real_table_rows(buf)
    if len(rows) < 2:
        return "<pre>" + "\n".join(buf) + "</pre>"
    return _render_table_html(rows[0], rows[1:])


def _real_table_rows(buf: list[str]) -> list[str]:
    """Filter `buf` to the rows that count as a real table row (skip
    separator rows like `|---|---|`)."""
    return [
        r for r in buf
        if r.strip() and not re.match(r"^\s*\|[\s\-:|]+\|\s*$", r)
    ]


def _split_row(line: str) -> list[str]:
    """Strip surrounding pipes and split one row on `|`."""
    return [c.strip() for c in line.strip("|").split("|")]


def _render_table_html(header_line: str, body_lines: list[str]) -> str:
    """Render a real table whose header is `header_line` and whose body
    rows are `body_lines`."""
    parts = ['<table class="data"><thead><tr>']
    parts.extend(f"<th>{_apply_inline(h)}</th>" for h in _split_row(header_line))
    parts.append("</tr></thead><tbody>")
    for row in body_lines:
        parts.append("<tr>")
        parts.extend(f"<td>{_apply_inline(cell)}</td>" for cell in _split_row(row))
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def _emit_code_block(buf: list[str]) -> str:
    """`<pre><code>…</code></pre>` for ``` … ``` blocks."""
    return f"<pre><code>{chr(10).join(buf)}</code></pre>"


def _emit_hr() -> str:
    """`<hr>` for `---` lines."""
    return "<hr>"


def _emit_paragraph(parts: list[str]) -> str:
    """`<p>…</p>` for a joined paragraph (single space, already inline-rendered)."""
    return f"<p>{' '.join(parts)}</p>"


# --- block matchers (return None when line is not a match) ---


def _try_heading(line: str) -> tuple[int, str] | None:
    """Return (level, html) for ATX headings `# ` … `###### `, else None."""
    m = re.match(r"^(#{1,6})\s+(.*)", line)
    if not m:
        return None
    return len(m.group(1)), _apply_inline(m.group(2))


def _try_blockquote(stripped: str) -> str | None:
    """Return `<blockquote>…</blockquote>` for `> ` lines, else None."""
    if not stripped.startswith("> "):
        return None
    return f"<blockquote>{_apply_inline(stripped[2:])}</blockquote>"


def _try_unordered_item(line: str) -> str | None:
    """Return `<li>…</li>` for `- ` / `* ` list items, else None."""
    m = re.match(r"^\s*[-*]\s+(.*)", line)
    if not m:
        return None
    return f"  <li>{_apply_inline(m.group(1))}</li>"


def _try_ordered_item(line: str) -> str | None:
    """Return `<li>…</li>` for `1. ` / `2. ` … list items, else None."""
    m = re.match(r"^\s*\d+\.\s+(.*)", line)
    if not m:
        return None
    return f"  <li>{_apply_inline(m.group(1))}</li>"


def _is_table_row(stripped: str) -> bool:
    """True for `|…|` rows that may be part of a pipe table."""
    return stripped.startswith("|") and stripped.endswith("|")


def _is_paragraph_continuation(line: str) -> bool:
    """True if `line` is a continuation of an open paragraph.

    A continuation is non-blank and not the start of any other block
    (heading, list, blockquote, table). Mirrors the orchestrator's
    dispatch predicates so we don't miss a block opener mid-paragraph.
    """
    s = line.strip()
    if not s:
        return False
    return (
        _try_heading(line) is None
        and _try_blockquote(s) is None
        and _try_unordered_item(line) is None
        and _try_ordered_item(line) is None
        and not _is_table_row(s)
    )


# --- block classification (dispatch table input) ---


_BLOCK_CODE_OPEN = "CODE_OPEN"
_BLOCK_CODE_LINE_END = "CODE_LINE_END"
_BLOCK_CODE_LINE = "CODE_LINE"
_BLOCK_TABLE_ROW = "TABLE_ROW"
_BLOCK_HEADING = "HEADING"
_BLOCK_HR = "HR"
_BLOCK_BLOCKQUOTE = "BLOCKQUOTE"
_BLOCK_UL_ITEM = "UL_ITEM"
_BLOCK_OL_ITEM = "OL_ITEM"
_BLOCK_BLANK = "BLANK"
_BLOCK_PARAGRAPH = "PARAGRAPH"


def _classify_block(line: str, stripped: str, in_code: bool) -> str:
    """Return a block tag describing what `line` is.

    `in_code` is the current code-block state — when True, any line is
    classified as CODE_LINE (we're inside a ``` block).

    The orchestrator switches on this tag. Each branch in the original
    175-line function becomes one tag → one producer call.
    """
    code_tag = _classify_code_line(line, stripped, in_code)
    if code_tag is not None:
        return code_tag
    return _classify_non_code(line, stripped)


def _classify_code_line(line: str, stripped: str, in_code: bool) -> str | None:
    """Return CODE_OPEN / CODE_LINE_END / CODE_LINE when `line` is part of
    a fenced code block, else None (callers classify non-code lines next).
    """
    if stripped.startswith("```"):
        return _BLOCK_CODE_OPEN if not in_code else _BLOCK_CODE_LINE_END
    if in_code:
        return _BLOCK_CODE_LINE
    return None


# `_classify_non_code` runs the structural matchers in priority order
# (most-specific block first, paragraph as the final fallback). Each
# entry is `(predicate, tag)`; the first match wins.
_NON_CODE_RULES: list[tuple["callable", str]] = []


def _classify_non_code(line: str, stripped: str) -> str:
    """Classify a line that is NOT inside a fenced code block.

    Matches the first structural predicate that fires. The trailing
    BLANK / PARAGRAPH fallback handles plain lines.
    """
    for predicate, tag in _NON_CODE_RULES:
        if predicate(line, stripped):
            return tag
    if not stripped:
        return _BLOCK_BLANK
    return _BLOCK_PARAGRAPH


def _rule(predicate):
    """Decorator: register `predicate(line, stripped) -> bool` as a non-
    code classifier rule. Order of registration = priority order.
    """
    _NON_CODE_RULES.append((predicate, _tag_for_predicate_name(predicate.__name__)))
    return predicate


def _tag_for_predicate_name(name: str) -> str:
    """Map a predicate function name to its block tag.

    Centralizes the predicate-name → tag lookup so each predicate stays
    one line of `@_rule`. Names match the `_try_*` / `_is_*` helpers that
    already exist in this module.
    """
    return _PREDICATE_TO_TAG[name]


_PREDICATE_TO_TAG: dict[str, str] = {
    "_predicate_table_row": _BLOCK_TABLE_ROW,
    "_predicate_heading": _BLOCK_HEADING,
    "_predicate_horizontal_rule": _BLOCK_HR,
    "_predicate_blockquote": _BLOCK_BLOCKQUOTE,
    "_predicate_unordered_item": _BLOCK_UL_ITEM,
    "_predicate_ordered_item": _BLOCK_OL_ITEM,
}


def _predicate_table_row(line: str, stripped: str) -> bool:
    return _is_table_row(stripped)


def _predicate_heading(line: str, stripped: str) -> bool:
    return _try_heading(line) is not None


def _predicate_horizontal_rule(line: str, stripped: str) -> bool:
    return stripped == "---"


def _predicate_blockquote(line: str, stripped: str) -> bool:
    return _try_blockquote(stripped) is not None


def _predicate_unordered_item(line: str, stripped: str) -> bool:
    return _try_unordered_item(line) is not None


def _predicate_ordered_item(line: str, stripped: str) -> bool:
    return _try_ordered_item(line) is not None


# Register predicates in priority order. Done at import time so the
# table is ready before the first `_md_to_html` call.
_rule(_predicate_table_row)
_rule(_predicate_heading)
_rule(_predicate_horizontal_rule)
_rule(_predicate_blockquote)
_rule(_predicate_unordered_item)
_rule(_predicate_ordered_item)


# --- state helpers ---


class _ListTracker:
    """One-slot boolean: is a `<ul>` or `<ol>` currently open?

    Module-level state is intentional — `_md_to_html` is called
    per-request and we don't want to thread a state object through every
    helper. The pre-refactor function used closure-local `in_list` for
    the same purpose; we lift it to a tiny class for testability without
    changing behavior.
    """

    _open: bool = False

    @classmethod
    def is_open(cls) -> bool:
        return cls._open

    @classmethod
    def open(cls) -> None:
        cls._open = True

    @classmethod
    def close(cls) -> None:
        cls._open = False


def _close_open_list(out: list[str]) -> None:
    """Close an open `<ul>`/`<ol>`, if any.

    Mirrors the pre-refactor behavior: the prior code emitted `</ul>` for
    BOTH list flavors at every list-close point (the `out[-1].startswith("  <li")`
    test in the original could not distinguish ordered vs unordered — so
    `</ul>` was emitted for both). We mirror that for behavior parity.
    """
    if _ListTracker.is_open():
        out.append("</ul>")
        _ListTracker.close()


# --- dispatch producer ---


# --- dispatch table: tag → pure producer ---
#
# Each producer is `(line, stripped, state) -> str | None`. The orchestrator
# dispatches via a `next()` lookup against this list, keeping `_md_to_html`
# at CC ≤ 10. Producers may mutate `state` (accumulators) but never the
# dispatch table itself. The table is rebuilt every call so we don't share
# mutable closures across requests.

def _produce_code_open(line, stripped, state):
    state["in_code"] = True
    state["code_buf"] = []
    return None

def _produce_code_end(line, stripped, state):
    emitted = _emit_code_block(state["code_buf"])
    state["in_code"] = False
    state["code_buf"] = []
    return emitted

def _produce_code_line(line, stripped, state):
    state["code_buf"].append(line)
    return None

def _produce_table_row(line, stripped, state):
    state["table_buf"].append(line)
    state["in_table"] = True
    return None

def _produce_heading(line, stripped, state):
    _close_open_list(state["out"])
    heading = _try_heading(line)
    assert heading is not None, "HEADING tag implies _try_heading matched"
    level, html = heading
    return f"<h{level}>{html}</h{level}>"

def _produce_hr(line, stripped, state):
    return _emit_hr()

def _produce_blockquote(line, stripped, state):
    _close_open_list(state["out"])
    return _try_blockquote(stripped)

def _produce_list_item(open_tag, item_fn):
    """Build a producer that opens the list tag on first call, then emits items.

    Captures `open_tag` (e.g. "<ul>") and `item_fn` (e.g. `_try_unordered_item`).
    A single closure replaces two near-identical inline branches.
    """
    def producer(line, stripped, state):
        if not _ListTracker.is_open():
            state["out"].append(open_tag)
            _ListTracker.open()
        return item_fn(line)
    return producer

def _produce_blank(line, stripped, state):
    _close_open_list(state["out"])
    return ""


def _build_dispatch_table() -> list[tuple[str, "callable"]]:
    """Return a fresh [(tag, producer), ...] for this request."""
    return [
        (_BLOCK_CODE_OPEN, _produce_code_open),
        (_BLOCK_CODE_LINE_END, _produce_code_end),
        (_BLOCK_CODE_LINE, _produce_code_line),
        (_BLOCK_TABLE_ROW, _produce_table_row),
        (_BLOCK_HEADING, _produce_heading),
        (_BLOCK_HR, _produce_hr),
        (_BLOCK_BLOCKQUOTE, _produce_blockquote),
        (_BLOCK_UL_ITEM, _produce_list_item("<ul>", _try_unordered_item)),
        (_BLOCK_OL_ITEM, _produce_list_item("<ol>", _try_ordered_item)),
        (_BLOCK_BLANK, _produce_blank),
    ]


def _dispatch(tag, line, stripped, state, table):
    """Look up the producer for `tag` and run it. Returns its HTML or None.

    Iterates `table` linearly — there are 10 entries, so this is O(10) per
    line and CC 2 (one for-loop, one branch for not-found). _BLOCK_PARAGRAPH
    has no entry: the orchestrator handles paragraph accumulation directly
    (multi-line buffer that spans many `i` iterations).
    """
    for entry_tag, producer in table:
        if entry_tag == tag:
            return producer(line, stripped, state)
    return None  # _BLOCK_PARAGRAPH or unknown — caller handles


# --- main orchestrator ---


def _md_to_html(md_text: str) -> str:
    """Convert our user-guide markdown subset to HTML.

    We don't depend on the `markdown` package (per AGENTS.md: no new
    deps without operator OK). The user-guide markdown uses a small
    subset of syntax — H1-H4, bold, italic, code, links, lists, tables.
    This renderer handles exactly that subset.

    If we ever need full CommonMark, request adding `markdown` to
    pyproject.toml and replace this function.

    Behavior preservation (CHARACTER-FOR-CHARACTER identical to the
    pre-refactor version):
      - Code block: ``` ... ``` → `<pre><code>…</code></pre>` (verbatim)
      - Table: consecutive `|…|` lines → `<table class="data">…</table>`
        OR `<pre>…</pre>` when fewer than 2 real rows
      - Heading: `#` … `######` → `<hN>…</hN>`
      - Horizontal rule: `---` → `<hr>`
      - Blockquote: `> ` → `<blockquote>…</blockquote>`
      - Unordered list: `- ` / `* ` → `<ul>…</ul>`
      - Ordered list: `1. ` … → `<ol>…</ol>`
      - Paragraph: contiguous non-blank, non-block lines → `<p>…</p>`
      - Empty line: emits a blank output line (paragraph/list break)
      - List-close always emits `</ul>` (matches pre-refactor closure bug)

    XSS guards (test_security_dynamic::test_md_to_html_blocks_xss):
      - HTML escape happens FIRST in `_apply_inline`
      - Link href passes through `_safe_url` (rejects javascript:, vbscript:)
    """
    state: dict = {
        "out": [],
        "table_buf": [],
        "code_buf": [],
        "in_table": False,
        "in_code": False,
    }
    _ListTracker.close()
    dispatch_table = _build_dispatch_table()

    lines = md_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        i = _render_one_line(lines, i, line, stripped, state, dispatch_table)
    _finalize(state)
    return "\n".join(state["out"])


def _render_one_line(
    lines: list[str],
    i: int,
    line: str,
    stripped: str,
    state: dict,
    dispatch_table: list[tuple[str, "callable"]],
) -> int:
    """Render `lines[i]` into `state["out"]`, advancing `i` past any
    paragraph continuation. Returns the next index for the outer loop.

    Splitting this from `_md_to_html` drops its cyclomatic complexity to
    a tight loop over a single-line renderer.
    """
    if not _is_table_row(stripped) and state["in_table"]:
        _flush_open_table(state)

    tag = _classify_block(line, stripped, state["in_code"])
    if tag == _BLOCK_PARAGRAPH:
        paragraph_html, next_i = _accumulate_paragraph(lines, i, stripped)
        state["out"].append(paragraph_html)
        return next_i

    emitted = _dispatch(tag, line, stripped, state, dispatch_table)
    if emitted is not None:
        state["out"].append(emitted)
    return i + 1


def _flush_open_table(state: dict) -> None:
    """Close any open table run and reset the table buffer."""
    state["out"].append(_flush_table(state["table_buf"]))
    state["table_buf"] = []
    state["in_table"] = False


def _accumulate_paragraph(
    lines: list[str], i: int, first_stripped: str
) -> tuple[str, int]:
    """Collect a paragraph starting at `lines[i]` (already-stripped first
    line is `first_stripped`). Returns `(html, next_i)` where `next_i`
    points past the last paragraph line consumed.
    """
    para: list[str] = [_apply_inline(first_stripped)]
    i += 1
    while i < len(lines) and _is_paragraph_continuation(lines[i]):
        para.append(_apply_inline(lines[i].strip()))
        i += 1
    return _emit_paragraph(para), i


def _finalize(state: dict) -> None:
    """End-of-document cleanup: flush any open table / list / code buffer.

    Mirrors the pre-refactor end-of-function logic exactly (character-for-
    character output, including the list-close `</ul>` quirk).
    """
    if state["in_table"]:
        _flush_open_table(state)
    if _ListTracker.is_open():
        state["out"].append("</ul>")
    if state["in_code"]:
        state["out"].append(_emit_code_block(state["code_buf"]))


def _read_section(slug: str) -> tuple[str, str]:
    """Return (title, html) for a section by slug."""
    # Map slugs to file names.
    fname = f"{slug}.md"
    fpath = GUIDE_DIR / fname
    if not fpath.exists():
        raise HTTPException(status_code=404, detail=f"Sección no encontrada: {slug}")
    md_text = fpath.read_text()
    # Extract first H1 title.
    title = "Guía"
    for line in md_text.split("\n"):
        if line.startswith("# "):
            title = line[2:].strip()
            break
    return title, _md_to_html(md_text)


@router.get("", response_class=HTMLResponse)
def guia_index(request: Request) -> HTMLResponse:
    """Render the user-guide README as the index."""
    title, body_html = _read_section("README")
    return render(
        request,
        "guia.html",
        {
            "title": title,
            "body_html": body_html,
            "section": "README",
        },
    )


@router.get("/{section}", response_class=HTMLResponse)
def guia_section(request: Request, section: str) -> HTMLResponse:
    """Render an individual user-guide section."""
    title, body_html = _read_section(section)
    return render(
        request,
        "guia.html",
        {
            "title": title,
            "body_html": body_html,
            "section": section,
        },
    )


__all__ = ["router"]
