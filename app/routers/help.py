"""app/routers/help.py — serves the user guide as rendered HTML.

GET /guia               — index page with TOC
GET /guia/{section}     — individual section (e.g. /guia/02-ventas)

The markdown lives in docs/user-guide/. We convert it to HTML at
request time using Python's markdown library (already pinned in
pyproject.toml as a transitive dep of pytest — if not, see the
fallback to plain-text rendering).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.auth import require_login_or_disabled as require_login
from app.services.template_render import render

router = APIRouter(prefix="/guia", dependencies=[Depends(require_login)])

GUIDE_DIR = Path(__file__).resolve().parents[2] / "docs" / "user-guide"


def _md_to_html(md_text: str) -> str:
    """Convert our user-guide markdown subset to HTML.

    We don't depend on the `markdown` package (per AGENTS.md: no new
    deps without operator OK). The user-guide markdown uses a small
    subset of syntax — H1-H4, bold, italic, code, links, lists, tables.
    This renderer handles exactly that subset.

    If we ever need full CommonMark, request adding `markdown` to
    pyproject.toml and replace this function.
    """
    lines = md_text.split("\n")
    ctx = _MdContext()

    i = 0
    while i < len(lines):
        i = _process_md_line(lines, i, ctx)

    # Flush any remaining state.
    _flush_table(ctx)
    if ctx.in_list:
        ctx.out.append("</ul>" if ctx.list_type == "ul" else "</ol>")
        ctx.in_list = False
    if ctx.in_code:
        ctx.out.append(f"<pre><code>{chr(10).join(ctx.code_buf)}</code></pre>")
        ctx.in_code = False

    return "\n".join(ctx.out)


class _MdContext:
    """Mutable state carried through a markdown-to-html pass.

    Holds the output buffer, current mode (code block, list, table),
    and any buffered content awaiting a flush.
    """
    out: list[str]
    in_list: bool
    in_table: bool
    in_code: bool
    list_type: str
    code_buf: list[str]
    table_buf: list[str]

    def __init__(self):
        self.out = []
        self.in_list = False
        self.in_table = False
        self.in_code = False
        self.list_type = "ul"
        self.code_buf = []
        self.table_buf = []


def _process_md_line(lines: list[str], i: int, ctx) -> int:
    """Process a single markdown line and return the next index to process.

    Extracted from _md_to_html to reduce complexity.
    """
    import re

    line = lines[i]
    stripped = line.strip()

    if ctx.in_code:
        return _process_code_line(line, i, ctx, stripped)

    if stripped.startswith("```"):
        return _toggle_code_block(i, ctx)

    if stripped.startswith("|") and stripped.endswith("|"):
        ctx.table_buf.append(line)
        ctx.in_table = True
        return i + 1

    if ctx.in_table:
        _flush_table(ctx)
        ctx.in_table = False

    return _process_block_element(line, stripped, i, ctx)


def _process_code_line(line: str, i: int, ctx, stripped: str) -> int:
    """Process a line while inside a code block.

    Extracted from _process_md_line to reduce complexity.
    """
    if stripped.startswith("```"):
        ctx.out.append(f"<pre><code>{chr(10).join(ctx.code_buf)}</code></pre>")
        ctx.in_code = False
        ctx.code_buf = []
    else:
        ctx.code_buf.append(line)
    return i + 1


def _toggle_code_block(i: int, ctx) -> int:
    """Toggle the code-block state (enter or exit).

    Extracted from _process_md_line to reduce complexity.
    """
    if ctx.in_code:
        ctx.out.append(f"<pre><code>{chr(10).join(ctx.code_buf)}</code></pre>")
        ctx.in_code = False
        ctx.code_buf = []
    else:
        ctx.in_code = True
        ctx.code_buf = []
    return i + 1


def _process_block_element(line: str, stripped: str, i: int, ctx) -> int:
    """Process a block-level element (heading, list, blockquote, paragraph).

    Extracted from _process_md_line to reduce complexity.
    """
    import re

    # Headings
    m = re.match(r"^(#{1,6})\s+(.*)", line)
    if m:
        return _emit_heading(m, i, ctx)

    # Horizontal rule
    if stripped == "---":
        ctx.out.append("<hr>")
        return i + 1

    # Blockquote
    if stripped.startswith("> "):
        return _emit_blockquote(stripped, i, ctx)

    # Lists (unordered)
    if re.match(r"^\s*[-*]\s+", line):
        return _emit_list_item(line, "ul", i, ctx)

    # Lists (ordered)
    if re.match(r"^\s*\d+\.\s+", line):
        return _emit_list_item(line, "ol", i, ctx)

    # Empty line = paragraph break
    if not stripped:
        return _handle_blank_line(ctx, i)

    # Default paragraph
    ctx.out.append(f"<p>{_inline(stripped)}</p>")
    return i + 1


def _emit_heading(m, i: int, ctx) -> int:
    """Emit a heading element, closing any open list first.

    Extracted from _process_block_element to reduce complexity.
    """
    if ctx.in_list:
        ctx.out.append("</ul>" if ctx.list_type == "ul" else "</ol>")
        ctx.in_list = False
    level = len(m.group(1))
    ctx.out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
    return i + 1


def _emit_blockquote(stripped: str, i: int, ctx) -> int:
    """Emit a blockquote element, closing any open list first.

    Extracted from _process_block_element to reduce complexity.
    """
    if ctx.in_list:
        ctx.out.append("</ul>" if ctx.list_type == "ul" else "</ol>")
        ctx.in_list = False
    ctx.out.append(f"<blockquote>{_inline(stripped[2:])}</blockquote>")
    return i + 1


def _emit_list_item(line: str, list_type: str, i: int, ctx) -> int:
    """Emit a list item, opening the list if not already.

    Extracted from _process_block_element to reduce complexity.
    """
    import re

    content = re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", line)
    if not ctx.in_list or ctx.list_type != list_type:
        if ctx.in_list:
            ctx.out.append("</ul>" if ctx.list_type == "ul" else "</ol>")
        ctx.out.append(f"<{list_type}>")
        ctx.in_list = True
        ctx.list_type = list_type
    ctx.out.append(f"  <li>{_inline(content)}</li>")
    return i + 1


def _handle_blank_line(ctx, i: int) -> int:
    """Handle a blank line, closing any open list.

    Extracted from _process_block_element to reduce complexity.
    """
    if ctx.in_list:
        ctx.out.append("</ul>" if ctx.list_type == "ul" else "</ol>")
        ctx.in_list = False
    return i + 1


def _flush_table(ctx) -> str:
    """Flush the buffered table content as HTML, if any.

    Extracted from _md_to_html to reduce complexity.
    """
    if not ctx.table_buf:
        return ""
    rows = _filter_table_rows(ctx.table_buf)
    if len(rows) < 2:
        return "<pre>" + "\n".join(ctx.table_buf) + "</pre>"
    html = _render_table_html(rows)
    ctx.table_buf = []
    return html


def _filter_table_rows(buf: list[str]) -> list[str]:
    """Filter out empty lines and the markdown separator row (|---|---|).

    Extracted from _flush_table to reduce complexity.
    """
    import re
    return [
        r for r in buf
        if r.strip() and not re.match(r"^\s*\|[\s\-:|]+\|\s*$", r)
    ]


def _render_table_html(rows: list[str]) -> str:
    """Build the HTML string for a markdown table given its rows.

    Extracted from _flush_table to reduce complexity.
    """
    header = [c.strip() for c in rows[0].strip("|").split("|")]
    body_rows = [[c.strip() for c in r.strip("|").split("|")] for r in rows[1:]]
    parts = ['<table class="data"><thead><tr>']
    parts.extend(f"<th>{_inline(h)}</th>" for h in header)
    parts.append("</tr></thead><tbody>")
    for row in body_rows:
        parts.append("<tr>")
        parts.extend(f"<td>{_inline(cell)}</td>" for cell in row)
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def _inline(text: str) -> str:
    """Apply inline markdown transformations: bold, italic, code, links.

    Extracted from _md_to_html to reduce complexity.
    """
    import re

    # Escape HTML first so markdown syntax chars are inert.
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Bold: **text**
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    # Italic: *text* (but not mid-word)
    text = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?![*\w])", r"<em>\1</em>", text)
    # Inline code: `text`
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # Links: [text](url) — href sanitized to safe schemes only.
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{_safe_url(m.group(2))}">{m.group(1)}</a>',
        text,
    )
    return text


def _safe_url(url: str) -> str:
    """Allow only http/https/relative paths; block javascript: and data:.

    Extracted from _md_to_html to reduce complexity.
    """
    import re

    url = url.strip()
    if re.match(r"https?://", url) or url.startswith("/"):
        return url
    return "#"


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
