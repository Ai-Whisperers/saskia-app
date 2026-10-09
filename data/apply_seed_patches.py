"""Patch sazon.py with the new seed pieces (in reverse order, top-down).

Sections to replace (from bottom of file upward to keep offsets stable):
  PRODUCTION_TEMPLATES  (line ~3252-3275)
  WASTE_LOG              (line ~3236-3245)
  BENCHMARKS             (line ~3209-3232)
  PEDIDOS                (line ~3060-3198)
  CUSTOMERS              (KEEP — only demo data)
  PRODUCTS               (line ~2179-2792)
  RECIPE_LINES           (line ~1979-2175)
  RECIPES                (line ~1686-1976)
  INGREDIENTS            (line ~476-1682)  ← biggest replacement

Within seed_sazon(), two embedded values to change:
  - production_completion's hardcoded product-name list (~line 4102-4109)
"""
import os
import subprocess
import sys
from typing import Optional

WT = "/opt/data/profiles/ivan/cache/scratch/saskia-workbook-reconcile"
os.chdir(WT)

PATH = "app/rms/seed/sazon.py"
with open(PATH) as f:
    src = f.read()
lines: list[str] = src.split("\n")


def get_piece(name: str) -> str:
    """Read a generated piece file (skips the leading # comment lines)."""
    with open(f"data/seed_pieces/{name}.py") as f:
        content = f.read()
    # The first lines are `# AUTO-GENERATED ...` then the assignment
    # Drop the leading `#` lines but keep the assignment starting
    # from `NAME = [`. The first non-# line is the assignment.
    out_lines: list[str] = []
    for line in content.split("\n"):
        if line.startswith("#") or line == "":
            out_lines.append(line)
        elif not out_lines or " = [" not in out_lines[-1]:
            out_lines.append(line)
        else:
            out_lines.append(line)
    # Find the assignment start (the first line containing " = [")
    body_lines = [line for line in content.split("\n")]
    # Skip the leading comments, find the assignment start
    start = 0
    for i, line in enumerate(body_lines):
        if " = [" in line and not line.strip().startswith("#"):
            start = i
            break
    return "\n".join(body_lines[start:])


# Define section boundaries (1-indexed line numbers of the assignment line)
# through the matching closing ] line.
def section_bounds(name: str) -> tuple[int, int]:
    """Find line range (1-indexed inclusive) for `name: list[...] = [ ... ]`.

    Strategy: walk forward from the opener and track bracket balance only
    *after* the opener line — the opener itself contains `list[tuple]` which
    has a nested `[]` for the type parameter, so starting depth at 0 from
    the opener line finds a phantom match.
    """
    pattern = name + ":"
    start_idx: Optional[int] = None
    for i, line in enumerate(lines):
        if line.strip().startswith(pattern) and "=" in line and "[" in line:
            start_idx = i
            break
    if start_idx is None:
        raise RuntimeError(f"section not found: {name}")

    # Skip the opener line entirely (its [] is just a type annotation).
    body_start = start_idx + 1
    depth = 1  # we're already "inside" the list opener
    for i in range(body_start, len(lines)):
        for ch in lines[i]:
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return (start_idx + 1, i + 1)  # 1-indexed
    raise RuntimeError(f"section bounds not closed for {name}")


SECTIONS = {
    "INGREDIENTS":          section_bounds("INGREDIENTS"),
    "RECIPES":              section_bounds("RECIPES"),
    "RECIPE_LINES":         section_bounds("RECIPE_LINES"),
    "PRODUCTS":             section_bounds("PRODUCTS"),
    "PEDIDOS":              section_bounds("PEDIDOS"),
    "BENCHMARKS":           section_bounds("BENCHMARKS"),
    "WASTE_LOG":            section_bounds("WASTE_LOG"),
    "PRODUCTION_TEMPLATES": section_bounds("PRODUCTION_TEMPLATES"),
}

for name, (s, e) in SECTIONS.items():
    print(f"{name:25s} lines {s}-{e} ({e-s+1} lines)")


# ────────────────────────────────────────────────────────────────────
# Replace sections IN REVERSE ORDER (bottom-up) to keep offsets stable.
# ────────────────────────────────────────────────────────────────────
def replace_section(name: str, new_body: list[str]) -> tuple[int, int]:
    """Replace the section for `name` with new_body lines.

    new_body: list of strings (each line WITHOUT trailing newline).
    """
    global lines
    s, e = SECTIONS[name]
    # Convert to 0-indexed
    s_idx, e_idx = s - 1, e - 1
    # Preserve indent from the section's opening line
    lines[s_idx].lstrip("\n")[: len(lines[s_idx]) - len(lines[s_idx].lstrip())]
    # Detect indent from first non-blank line
    first_indent = ""
    for ch in lines[s_idx]:
        if ch in (" ", "\t"):
            first_indent += ch
        else:
            break
    # Apply indent to body if needed
    new_lines = [line if line.startswith(first_indent) or not line.strip() else first_indent + line
                 for line in new_body]
    # Re-build lines
    new_lines_all = lines[:s_idx] + new_lines + lines[e_idx + 1:]
    lines = new_lines_all
    return len(new_body), e - s + 1


# Define new bodies
INDIENTS_PIECE = get_piece("ingredients")
RECIPES_PIECE = get_piece("recipes")
RECIPE_LINES_PIECE = get_piece("recipe_lines")
PRODUCTS_PIECE = get_piece("products")
PEDIDOS_PIECE = get_piece("pedidos")
BENCHMARKS_PIECE = get_piece("benchmarks")
WASTE_LOG_PIECE = get_piece("waste_log")
PROD_TEMPLATES_PIECE = get_piece("production_templates")
PROD_COMPLETION_PIECE = open("data/seed_pieces/prod_completion_products.py").read()


def split_body(content: str) -> list[str]:
    """Return list of lines from a generated piece body (no leading comments)."""
    body = content.split("\n")
    out: list[str] = []
    started = False
    for line in body:
        if not started:
            if " = [" in line and not line.strip().startswith("#"):
                started = True
                # skip — we add the section's own opener later if needed
                out.append(line)
            elif line.strip().startswith("#"):
                # comment — skip; the next iteration starts content
                continue
            else:
                out.append(line)
        else:
            out.append(line)
    return out


# Each piece starts with a `NAME = [...` line. We want to keep the existing
# opener `NAME: list[tuple] = [` line. Strategy: strip the leading
# `NAME = [` from each piece's body and replace the section with the rest.
def strip_opener(body: list[str]) -> list[str]:
    """Strip leading opener line `NAME = [` from body, keeping the rest."""
    out: list[str] = []
    skipped = False
    for line in body:
        if not skipped and "= [" in line and not line.strip().startswith("#"):
            skipped = True
            # Keep the LHS but transform it
            # If it has no type annotation, add one when replacing an existing one
            continue
        out.append(line)
    return out


new_ingredients_lines = strip_opener(INDIENTS_PIECE.split("\n"))
new_recipes_lines = strip_opener(RECIPES_PIECE.split("\n"))
new_recipe_lines_lines = strip_opener(RECIPE_LINES_PIECE.split("\n"))
new_products_lines = strip_opener(PRODUCTS_PIECE.split("\n"))
new_pedidos_lines = strip_opener(PEDIDOS_PIECE.split("\n"))
new_benchmarks_lines = strip_opener(BENCHMARKS_PIECE.split("\n"))
new_waste_log_lines = strip_opener(WASTE_LOG_PIECE.split("\n"))
new_prod_templates_lines = strip_opener(PROD_TEMPLATES_PIECE.split("\n"))


# Patch sections in REVERSE order (bottom-up) so line offsets stay stable.
# But we must capture the line range in the ORIGINAL file. Section bounds
# from the `lines` variable above are BEFORE the replacement.
# For reverse-bottom-up patching, the bounds are already correct since
# we process bottom sections first and they don't change upper lines.

# Plan: apply replacement in REVERSE order using ORIGINAL bounds. We need
# a clean lines list for each operation — track changes carefully.

# Strategy v2: build a single line list with empty markers for each
# section, then fill in each marker. Cleaner.

# Build markered content
output_lines = list(lines)  # copy

# Apply in reverse
PATCHES = [
    ("PRODUCTION_TEMPLATES", new_prod_templates_lines),
    ("WASTE_LOG",            new_waste_log_lines),
    ("BENCHMARKS",           new_benchmarks_lines),
    ("PEDIDOS",              new_pedidos_lines),
    ("PRODUCTS",             new_products_lines),
    ("RECIPE_LINES",         new_recipe_lines_lines),
    ("RECIPES",              new_recipes_lines),
    ("INGREDIENTS",          new_ingredients_lines),
]


# Build offset-aware patch. For each patch, compute line count delta and
# adjust later bounds.
def apply_patch(name: str, new_body_lines: list[str]) -> int:
    """Replace a section while preserving the opener line `NAME: list[tuple] = [`.

    Strategy:
      1. The opener at lines[s_idx] is preserved (kept verbatim from the existing file).
      2. The body before the closing `]` is replaced with new_body_lines.
      3. The closing `]` at lines[e_idx] is preserved.
    new_body_lines should NOT contain its own opener or closing bracket.
    """
    global lines
    s, e = SECTIONS[name]
    s_idx, e_idx = s - 1, e - 1

    opener = lines[s_idx]   # "INGREDIENTS: list[tuple] = ["
    closer = lines[e_idx]   # "]"

    out_body = list(new_body_lines)
    # Strip trailing blanks
    while out_body and out_body[-1] == "":
        out_body.pop()
    # Strip trailing "]" if body has one (generator includes it)
    while out_body and out_body[-1].strip() == "]":
        out_body.pop()
        # Also strip preceding blanks
        while out_body and out_body[-1] == "":
            out_body.pop()

    # Build replacement: opener + body + trailing colon + closer + post-blank line
    replacement = [opener, *out_body, closer, ""]

    new_lines = lines[:s_idx] + replacement + lines[e_idx + 1 :]
    delta = len(replacement) - (e_idx - s_idx + 1) - 1  # existing range minus pre-existing post-blank
    lines = new_lines
    return delta


# Reverse-iterate
for name, body in PATCHES:
    delta = apply_patch(name, body)
    print(f"  Patched {name:25s} delta = {delta:+d}")

# Now: production_completion block — the hardcoded list of product names.
# This block lives around line ~4102. We need to swap the literal list.

PROD_COMP_NAMES = PROD_COMPLETION_PIECE.replace("PROD_COMPLETION_PRODUCTS = ", "").strip()
# Format like ['Muffin de chocolate (20x20 cm)', 'Cheesecake (30x50)', ...]

# Replace the 6-item product list inside seed_sazon's production_completion block.
# Original layout (around line 4103):
#   "Muffin de vainilla",
#   "Muffin de chocolate",
#   "Pan lactal",
#   "Facturas (docena)",
#   "Medialunas (docena)",
#   "Tostado JyQ",
# Layout in seeded file (around line 4102):
#   "        for prod_name in ["
#   "            \"Muffin de vainilla\","      <-- target_start
#   "            ... 5 more product names ..."
#   "        ]:"                                  <-- target_end
# We replace ONLY the 6 product-name lines (skip opener + closer, keep them).
target_start: Optional[int] = None
target_end: Optional[int] = None
for i, line in enumerate(lines):
    if '"Muffin de vainilla",' in line:
        target_start = i
        # walk forward to the closing "]:"
        for j in range(i + 1, min(i + 12, len(lines))):
            if lines[j].strip() == "]:":
                target_end = j  # exclusive
                break
        break

if target_start is None or target_end is None:
    print("WARNING: production_completion block not found", file=sys.stderr)

if target_start is not None:
    new_lines_block: list[str] = [
        f"            {name!r}," for name in eval(PROD_COMP_NAMES)  # noqa: S307
    ]
    lines = lines[:target_start] + new_lines_block + lines[target_end:]
    print(f"Patched production_completion product list ({len(eval(PROD_COMP_NAMES))} products)")  # noqa: S307


# Write patched file
out_path = PATH + ".patched"
with open(out_path, "w") as f:
    f.write("\n".join(lines))

print(f"\nWrote {out_path}")
print(f"Original lines: {len(src.split(chr(10)))}  Patched lines: {len(lines)}")
print()

# Sanity check: import the patched file
r = subprocess.run(  # noqa: S603 - operator-supplied path, runs parser only
    [".venv/bin/python", "-c", f"import ast; ast.parse(open('{out_path}').read()); print('SYNTAX OK')"],
    capture_output=True, text=True,
)
print(f"Syntax check: rc={r.returncode}")
if r.stdout:
    print(r.stdout)
if r.stderr:
    print('STDERR:', r.stderr[:2000])
