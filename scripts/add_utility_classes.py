#!/usr/bin/env python3
"""Add utility classes alongside existing inline styles where the style
starts with a recognized pattern.

Unlike migrate_inline_styles.py (which REPLACES the style), this one
ADDS the utility class while leaving the rest of the inline style in
place. This is the safe way to migrate compound styles like
'display:flex; gap:8px; align-items:center;' — we get the .d-flex class
plus the rest stays.

Run from repo root.
"""
import re
import os
import sys


# (regex to match at START of style value, class to add)
ADD_UTILITIES = [
    (r'^margin:0(?=$|;)', 'm-0'),
    (r'^margin-top:0(?=$|;)', 'mt-0'),
    (r'^margin-top:4px(?=$|;)', 'mt-4'),
    (r'^margin-top:var\(--space-1\)(?=$|;)', 'mt-1'),
    (r'^margin-top:var\(--space-2\)(?=$|;)', 'mt-2'),
    (r'^margin-top:var\(--space-3\)(?=$|;)', 'mt-3'),
    (r'^margin-top:2rem(?=$|;)', 'mt-8'),
    (r'^margin-bottom:0(?=$|;)', 'mb-0'),
    (r'^margin-bottom:var\(--space-2\)(?=$|;)', 'mb-2'),
    (r'^margin-bottom:var\(--space-3\)(?=$|;)', 'mb-3'),
    (r'^margin-bottom:1rem(?=$|;)', 'mb-6'),
    (r'^margin-left:var\(--space-2\)(?=$|;)', 'ml-2'),
    (r'^display:inline(?=$|;)', 'd-inline'),
    (r'^display:inline-flex(?=$|;)', 'd-inline-flex'),
    (r'^display:block(?=$|;)', 'd-block'),
    (r'^display:flex(?=$|;)', 'd-flex'),
    (r'^display:none(?=$|;)', 'd-none'),
    (r'^display:grid(?=$|;)', 'd-grid'),
    (r'^text-align:right(?=$|;)', 'text-right'),
    (r'^text-align:center(?=$|;)', 'text-center'),
    (r'^text-align:left(?=$|;)', 'text-left'),
    (r'^width:100%(?=$|;)', 'w-100'),
    (r'^height:36px(?=$|;)', 'h-control'),
    (r'^flex:1(?=$|;)', 'flex-1'),
]


def migrate_file(path):
    with open(path) as f:
        content = f.read()
    new_content = content
    total = 0

    matches = list(re.finditer(r'style="([^"]+)"', content))
    # Process in reverse
    additions = []
    for m in matches:
        value = m.group(1).strip()
        added_classes = []
        for pattern, cls in ADD_UTILITIES:
            if re.match(pattern, value):
                if cls not in added_classes:
                    added_classes.append(cls)
        if not added_classes:
            continue
        # Find enclosing tag
        before = new_content[:m.start()]
        last_lt = before.rfind('<')
        if last_lt < 0 or new_content[last_lt + 1] == '/':
            continue
        next_gt = new_content.find('>', m.end())
        if next_gt < 0:
            continue
        tag_str = new_content[last_lt:next_gt + 1]
        # Skip script/style/link/meta/img/input
        if re.match(r'<(script|style|link|meta|br|hr|input|img|!--)', tag_str, re.I):
            continue
        m_tag = re.match(r'<([a-zA-Z][a-zA-Z0-9-]*)', tag_str)
        if not m_tag:
            continue
        tag_name = m_tag.group(1)
        # Skip if tag already has all the new classes
        class_match = re.search(r'class=("[^"]*"|\'[^\']*\')', tag_str)
        existing_classes = []
        if class_match:
            existing_classes = class_match.group(1).strip('"').strip("'").split()
        needed = [c for c in added_classes if c not in existing_classes]
        if not needed:
            continue
        new_classes = ' '.join(existing_classes + needed)
        if class_match:
            new_tag = re.sub(r'class=("[^"]*"|\'[^\']*\')', f'class="{new_classes}"', tag_str, count=1)
        else:
            new_tag = re.sub(r'<' + tag_name, '<' + tag_name + f' class="{new_classes}"', tag_str, count=1)
        new_content = new_content[:last_lt] + new_tag + new_content[next_gt + 1:]
        total += len(needed)

    return new_content, total


def main():
    templates_dir = 'app/templates'
    if not os.path.isdir(templates_dir):
        print(f'No {templates_dir}; run from repo root')
        sys.exit(1)
    total_files = 0
    total_adds = 0
    for root, _, files in os.walk(templates_dir):
        for f in files:
            if not f.endswith('.html'):
                continue
            path = os.path.join(root, f)
            new_content, n = migrate_file(path)
            if n > 0:
                with open(path, 'w') as fh:
                    fh.write(new_content)
                total_files += 1
                total_adds += n
                print(f'  {path}: +{n} utility classes')
    print(f'\n{total_files} files, {total_adds} classes added')


if __name__ == '__main__':
    main()