#!/usr/bin/env python3
"""Migrate inline style="..." patterns to utility classes.

For each pattern with ≥6 occurrences, replace the inline style with the
corresponding class and remove the style="" attribute (when it was the
only one). When the <tag> already has a class attribute, append the new
class.

Run from the repo root.
"""

import os
import re
import sys

# (regex on the inner style value, class to add)
# The regex is matched against the inside of style="<regex>"
MIGRATIONS = [
    # Single declarations
    (r"^font-size:var\(--text-sm\);?$", "text-sm"),
    (r"^font-size:var\(--text-xs\);?$", "text-xs"),
    (r"^font-size:var\(--text-md\);?$", "text-md"),
    (r"^font-size:\s*var\(--text-sm\);?$", "text-sm"),
    (r"^font-size:\s*var\(--text-xs\);?$", "text-xs"),
    (r"^font-size:\s*var\(--text-md\);?$", "text-md"),
    (r"^font-size:\s*12px;?$", "text-xs"),
    (r"^font-size:\s*11px;?$", "text-xs"),
    (r"^font-size:\s*13px;?$", "text-xs"),
    (r"^font-size:\s*14px;?$", "text-sm"),
    # margins (use spaces around "0" carefully — order matters in regex)
    (r"^margin:0;?$", "m-0"),
    (r"^margin:\s*0;?$", "m-0"),
    (r"^margin-top:0;?$", "mt-0"),
    (r"^margin-top:\s*0;?$", "mt-0"),
    (r"^margin-top:4px;?$", "mt-4"),
    (r"^margin-top:\s*4px;?$", "mt-4"),
    (r"^margin-top:var\(--space-1\);?$", "mt-1"),
    (r"^margin-top:\s*var\(--space-1\);?$", "mt-1"),
    (r"^margin-top:var\(--space-2\);?$", "mt-2"),
    (r"^margin-top:\s*var\(--space-2\);?$", "mt-2"),
    (r"^margin-top:var\(--space-3\);?$", "mt-3"),
    (r"^margin-top:\s*var\(--space-3\);?$", "mt-3"),
    (r"^margin-top:2rem;?$", "mt-8"),
    (r"^margin-top:\s*2rem;?$", "mt-8"),
    (r"^margin-bottom:0;?$", "mb-0"),
    (r"^margin-bottom:\s*0;?$", "mb-0"),
    (r"^margin-bottom:var\(--space-2\);?$", "mb-2"),
    (r"^margin-bottom:\s*var\(--space-2\);?$", "mb-2"),
    (r"^margin-bottom:var\(--space-3\);?$", "mb-3"),
    (r"^margin-bottom:\s*var\(--space-3\);?$", "mb-3"),
    (r"^margin-bottom:\s*1rem;?$", "mb-6"),
    (r"^margin-left:var\(--space-2\);?$", "ml-2"),
    (r"^margin-left:\s*var\(--space-2\);?$", "ml-2"),
    # Display
    (r"^display:inline;?$", "d-inline"),
    (r"^display:\s*inline;?$", "d-inline"),
    (r"^display:inline-flex;?$", "d-inline-flex"),
    (r"^display:\s*inline-flex;?$", "d-inline-flex"),
    (r"^display:block;?$", "d-block"),
    (r"^display:\s*block;?$", "d-block"),
    (r"^display:flex;?$", "d-flex"),
    (r"^display:\s*flex;?$", "d-flex"),
    (r"^display:none;?$", "d-none"),
    (r"^display:\s*none;?$", "d-none"),
    (r"^display:grid;?$", "d-grid"),
    # Text alignment
    (r"^text-align:\s*right;?$", "text-right"),
    (r"^text-align:right;?$", "text-right"),
    (r"^text-align:\s*center;?$", "text-center"),
    (r"^text-align:center;?$", "text-center"),
    (r"^text-align:\s*left;?$", "text-left"),
    # Width / height
    (r"^width:100%;?$", "w-100"),
    (r"^width:\s*100%;?$", "w-100"),
    (r"^height:36px;?$", "h-control"),
    (r"^height:\s*36px;?$", "h-control"),
    (r"^flex:1;?$", "flex-1"),
    (r"^flex:\s*1;?$", "flex-1"),
    # Multi-decl (order matters — more specific first)
    (
        r"^font-size:var\(--text-xs\);text-transform:uppercase;letter-spacing:0\.05em;?$",
        "text-label-upper",
    ),
    (
        r"^font-size:\s*var\(--text-xs\);text-transform:\s*uppercase;letter-spacing:\s*0\.05em;?$",
        "text-label-upper",
    ),
    (
        r"^display:\s*flex;\s*justify-content:\s*space-between;\s*margin-bottom:\s*var\(--space-2\);?$",
        "flex-between-mb-2",
    ),
    (
        r"^display:flex;\s*justify-content:space-between;\s*margin-bottom:var\(--space-2\);?$",
        "flex-between-mb-2",
    ),
    (r"^display:\s*flex;\s*gap:\s*var\(--space-2\);\s*flex-wrap:\s*wrap;?$", "flex-gap-2-wrap"),
    (r"^display:flex;\s*gap:var\(--space-2\);\s*flex-wrap:wrap;?$", "flex-gap-2-wrap"),
    (
        r"^display:\s*inline-flex;\s*align-items:\s*center;\s*gap:\s*var\(--space-2\);?$",
        "inline-flex-center-gap-2",
    ),
    (
        r"^display:inline-flex;\s*align-items:center;\s*gap:var\(--space-2\);?$",
        "inline-flex-center-gap-2",
    ),
    (
        r"^display:\s*block;\s*margin-bottom:\s*var\(--space-1\);\s*font-weight:\s*bold;?$",
        "block-bold",
    ),
    (r"^display:block;\s*margin-bottom:var\(--space-1\);\s*font-weight:bold;?$", "block-bold"),
    # "margin: var(--space-1) 0 0 0;" — only top
    (r"^margin:\s*var\(--space-1\)\s*0\s*0\s*0;?$", "mt-1-only"),
    # width:100%; padding: 0.5rem; border-radius: 6px; border: 1px solid var(--border);
    (
        r"^width:100%;\s*padding:\s*0\.5rem;\s*border-radius:\s*6px;\s*border:\s*1px\s+solid\s+var\(--border\);?$",
        "note-callout",
    ),
]


def migrate_file(path):
    with open(path) as f:
        content = f.read()

    changed = False

    def replace_style(m):
        nonlocal changed
        style_value = m.group(1).strip()
        # Try each migration pattern
        for pattern, cls in MIGRATIONS:
            if re.match(pattern, style_value):
                # Found a match. We need to:
                # 1. Find the enclosing <tag ...> element
                # 2. Add `cls` to its class attribute (creating one if absent)
                # 3. Remove the entire `style="..."` attribute
                _tag_match = re.search(
                    r'<([a-zA-Z][a-zA-Z0-9-]*)\s+([^>]*)style="'
                    + re.escape(m.group(1))
                    + r'"([^>]*)>',
                    m.string[max(0, m.start() - 500) : m.end() + 500],
                )
                # ... this is getting complex. Just do simple substitution:
                # Replace the entire `style="..."` with `class="<cls>"`.
                # If there's already a class, append.
                # Find the opening tag that this style is inside.
                # Easier: do this by finding the <TAG ... style="..." ATTRS> span.
                before = m.string[: m.start()]
                # Find the last '<' before m.start()
                last_lt = before.rfind("<")
                if last_lt < 0:
                    return m.group(0)
                # Find the next '>' after m.end()
                next_gt = m.string.find(">", m.end())
                if next_gt < 0:
                    return m.group(0)
                _tag_full = m.string[last_lt : next_gt + 1]
                tag_inner = m.string[last_lt + 1 : next_gt]
                # Split tag into name + attrs
                tag_match2 = re.match(
                    r'([a-zA-Z][a-zA-Z0-9-]*)((?:\s+[^=>\s]+(?:=("[^"]*"|\'[^\']*\'|[^\s"\']*))?)*)\s*/?>',
                    tag_inner,
                )
                if not tag_match2:
                    return m.group(0)
                tag_name = tag_match2.group(1)
                attrs_str = tag_match2.group(2) or ""
                # Parse attrs
                # Remove the style attribute
                attrs_str = re.sub(r"\s+style=" + re.escape('"' + m.group(1) + '"'), "", attrs_str)
                # Check for existing class attribute
                cls_match = re.search(r'class=("[^"]*"|\'[^\']*\')', attrs_str)
                if cls_match:
                    # Append cls
                    existing = cls_match.group(1).strip('"').strip("'")
                    new_cls_val = (existing + " " + cls).strip()
                    attrs_str = re.sub(r'class="[^"]*"', f'class="{new_cls_val}"', attrs_str)
                    if not re.search(r'class="[^"]*"', attrs_str):
                        attrs_str = re.sub(r"class='[^']*'", f'class="{new_cls_val}"', attrs_str)
                else:
                    # Add class attribute
                    attrs_str = ' class="' + cls + '"' + attrs_str
                # Reassemble
                new_tag = "<" + tag_name + attrs_str + ">"
                changed = True
                return new_tag
        return m.group(0)

    # Actually the replace_style approach above doesn't work because re.sub
    # works on strings, not on matched position context. Let me redo this
    # using a simpler 2-pass approach.
    return content, changed


# Simpler implementation: find each style="...", determine its migration class,
# then patch the surrounding tag separately.
def migrate_file_v2(path):
    with open(path) as f:
        content = f.read()
    new_content = content
    total_replacements = 0

    # Find all style="..." attrs
    style_re = re.compile(r'style="([^"]*)"')
    matches = list(style_re.finditer(content))
    if not matches:
        return content, 0

    # Process in reverse to preserve offsets
    replacements = []
    for m in matches:
        style_value = m.group(1).strip()
        for pattern, cls in MIGRATIONS:
            if re.match(pattern, style_value):
                replacements.append((m, cls))
                break

    # Apply replacements in reverse
    for m, cls in reversed(replacements):
        # Find enclosing <tag>
        before = new_content[: m.start()]
        last_lt = before.rfind("<")
        if last_lt < 0:
            continue
        # Skip if this isn't a tag opener (could be inside a string/comment)
        # Find matching >
        next_gt = new_content.find(">", m.end())
        if next_gt < 0:
            continue
        # The tag is from last_lt to next_gt (inclusive of '<')
        # But we need to handle multiline tags too
        end_lt = next_gt + 1

        tag_str = new_content[last_lt:end_lt]
        # Get the inner (without the < and >)
        # Check if it's a closing tag
        if tag_str.lstrip("<").startswith("/"):
            continue
        # Check for self-closing
        # Skip script/style/link/meta
        if re.match(r"<(script|style|link|meta|br|hr|input|img|!--)", tag_str, re.I):
            continue

        # Get tag name
        m_tag = re.match(r"<([a-zA-Z][a-zA-Z0-9-]*)", tag_str)
        if not m_tag:
            continue
        tag_name = m_tag.group(1)
        # Remove the style attribute (the matched span)
        new_tag = tag_str[: m.start() - last_lt] + tag_str[m.end() - last_lt :]
        # Now insert the class. If class= exists, append. Otherwise add.
        class_match = re.search(r'class=("[^"]*"|\'[^\']*\')', new_tag)
        if class_match:
            existing = class_match.group(1).strip('"').strip("'")
            new_cls_val = (existing + " " + cls).strip()
            new_tag = re.sub(r'class=("[^"]*"|\'[^\']*\')', f'class="{new_cls_val}"', new_tag)
        else:
            # Insert class= immediately after tag name
            new_tag = re.sub(
                r"(<" + tag_name + r")",
                r'\1 class="' + cls + '"',
                new_tag,
                count=1,
            )
        new_content = new_content[:last_lt] + new_tag + new_content[end_lt:]
        total_replacements += 1

    return new_content, total_replacements


def main():
    templates_dir = "app/templates"
    if not os.path.isdir(templates_dir):
        print(f"No {templates_dir} directory; run from repo root")
        sys.exit(1)
    total_files = 0
    total_replacements = 0
    for root, _, files in os.walk(templates_dir):
        for f in files:
            if not f.endswith(".html"):
                continue
            path = os.path.join(root, f)
            new_content, n = migrate_file_v2(path)
            if n > 0:
                with open(path, "w") as fh:
                    fh.write(new_content)
                total_files += 1
                total_replacements += n
                print(f"  {path}: {n} migrations")
    print(f"\n{total_files} files, {total_replacements} total migrations")


if __name__ == "__main__":
    main()
