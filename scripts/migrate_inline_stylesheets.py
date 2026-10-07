#!/usr/bin/env python3
"""Move all inline <style> blocks from templates to app-improvements.css.

For each template with one or more <style> blocks:
1. Extract the CSS body
2. Append it to app-improvements.css with a header naming the template
3. Remove the <style> block from the template

Run from repo root.
"""
import os
import re

CONSOLIDATOR = 'app/static/app-improvements.css'
HEADER_TPL = '\n\n/* ─── {slug} (extracted from {rel_path}) ─── */\n'


def migrate():
    moved_total = 0
    files_touched = 0
    files = [
        os.path.join(root, f)
        for root, _, fs in os.walk('app/templates')
        for f in fs
        if f.endswith('.html')
    ]

    with open(CONSOLIDATOR) as f:
        existing = f.read()

    for path in files:
        with open(path) as f:
            content = f.read()
        # Find all <style> blocks (preserve order)
        matches = list(re.finditer(r'<style[^>]*>(.*?)</style>', content, re.DOTALL))
        if not matches:
            continue
        # Build the CSS to append
        rel = os.path.relpath(path, 'app/templates')
        slug = rel.replace('/', '_').replace('.html', '')
        body_parts = [m.group(1).strip() for m in matches]
        appended_css = HEADER_TPL.format(slug=slug, rel_path=rel) + '\n'.join(body_parts) + '\n'
        # Remove the inline blocks (process in reverse to preserve offsets)
        new_content = content
        for m in reversed(matches):
            new_content = new_content[:m.start()] + new_content[m.end():]
        # Clean up excess blank lines
        new_content = re.sub(r'\n{3,}', '\n\n', new_content)
        # Check for duplication: only append if header doesn't already exist
        _header_marker = HEADER_TPL.split('\n')[2].strip()  # e.g. '─── ... ───'
        # Use a unique identifier: the slug
        if f'─── {slug} ' not in existing and f'─── {slug} (' not in existing:
            with open(CONSOLIDATOR, 'a') as f:
                f.write(appended_css)
            existing += appended_css
            with open(path, 'w') as f:
                f.write(new_content)
            moved_total += sum(len(p) for p in body_parts) + len(HEADER_TPL.format(slug=slug, rel_path=rel))
            files_touched += 1
            print(f'  {path}: {sum(len(p) for p in body_parts)} bytes')
    print(f'\n{files_touched} files, {moved_total} bytes migrated')


if __name__ == '__main__':
    migrate()
