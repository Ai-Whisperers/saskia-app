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
    import re
    lines = md_text.split("\n")
    out: list[str] = []
    in_list = False
    in_table = False
    in_code = False
    code_buf: list[str] = []
    table_buf: list[str] = []

    def flush_table():
        if not table_buf:
            return ""
        rows = [r for r in table_buf if r.strip() and not re.match(r"^\s*\|[\s\-:|]+\|\s*$", r)]
        if len(rows) < 2:
            return "<pre>" + "\n".join(table_buf) + "</pre>"
        # First row = headers.
        header = [c.strip() for c in rows[0].strip("|").split("|")]
        body_rows = []
        for r in rows[1:]:
            body_rows.append([c.strip() for c in r.strip("|").split("|")])
        html = ["<table class=\"data\"><thead><tr>"]
        for h in header:
            html.append(f"<th>{_inline(h)}</th>")
        html.append("</tr></thead><tbody>")
        for row in body_rows:
            html.append("<tr>")
            for cell in row:
                html.append(f"<td>{_inline(cell)}</td>")
            html.append("</tr>")
        html.append("</tbody></table>")
        return "".join(html)

    def _inline(text: str) -> str:
        # Escape HTML first.
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # Bold: **text**
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
        # Italic: *text* (but not mid-word)
        text = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?![*\w])", r"<em>\1</em>", text)
        # Inline code: `text`
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        # Links: [text](url)
        text = re.sub(
            r"\[([^\]]+)\]\(([^)]+)\)",
            lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>',
            text,
        )
        return text

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Code block (```...```)
        if stripped.startswith("```"):
            if not in_code:
                in_code = True
                code_buf = []
                i += 1
                continue
            else:
                # End of code block.
                out.append(f"<pre><code>{chr(10).join(code_buf)}</code></pre>")
                in_code = False
                code_buf = []
                i += 1
                continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        # Tables (lines starting with |)
        if stripped.startswith("|") and stripped.endswith("|"):
            table_buf.append(line)
            in_table = True
            i += 1
            continue
        else:
            if in_table:
                out.append(flush_table())
                table_buf = []
                in_table = False

        # Headings
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            if in_list:
                out.append("</ul>")
                in_list = False
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # Horizontal rule
        if stripped == "---":
            out.append("<hr>")
            i += 1
            continue

        # Blockquote
        if stripped.startswith("> "):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<blockquote>{_inline(stripped[2:])}</blockquote>")
            i += 1
            continue

        # Lists (unordered)
        if re.match(r"^\s*[-*]\s+", line):
            content = re.sub(r"^\s*[-*]\s+", "", line)
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"  <li>{_inline(content)}</li>")
            i += 1
            continue

        # Lists (ordered)
        if re.match(r"^\s*\d+\.\s+", line):
            content = re.sub(r"^\s*\d+\.\s+", "", line)
            if not in_list:
                out.append("<ol>")
                in_list = True
            out.append(f"  <li>{_inline(content)}</li>")
            i += 1
            continue

        # Empty line = paragraph break
        if not stripped:
            if in_list:
                out.append("</ul>" if out[-1].startswith("  <li") else "</ol>")
                in_list = False
            out.append("")
            i += 1
            continue

        # Default: paragraph text (accumulate until blank line).
        para: list[str] = [_inline(stripped)]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,6}\s|>|\s*[-*]\s|\s*\d+\.\s)", lines[i]):
            para.append(_inline(lines[i].strip()))
            i += 1
        out.append(f"<p>{' '.join(para)}</p>")

    if in_table:
        out.append(flush_table())
    if in_list:
        out.append("</ul>")
    if in_code:
        out.append(f"<pre><code>{chr(10).join(code_buf)}</code></pre>")

    return "\n".join(out)


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
    return render(request, "guia.html", {
        "title": title,
        "body_html": body_html,
        "section": "README",
    })


@router.get("/{section}", response_class=HTMLResponse)
def guia_section(request: Request, section: str) -> HTMLResponse:
    """Render an individual user-guide section."""
    title, body_html = _read_section(section)
    return render(request, "guia.html", {
        "title": title,
        "body_html": body_html,
        "section": section,
    })


__all__ = ["router"]
