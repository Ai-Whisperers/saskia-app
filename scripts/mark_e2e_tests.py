"""Add `pytest.mark.e2e` to every tests/e2e/*.py test module that
doesn't have it yet. Preserves existing markers (crud, security, etc.).
"""

from pathlib import Path

e2e_dir = Path("tests/e2e")
for path in sorted(e2e_dir.glob("test_*.py")):
    text = path.read_text()
    if "pytest.mark.e2e" in text:
        continue
    if "pytestmark" in text:
        # Has pytestmark — replace single marker with a list that includes e2e
        # + the existing marker.
        import re

        # Match: pytestmark = pytest.mark.foo OR pytestmark = [pytest.mark.foo]
        new = re.sub(
            r"^pytestmark = (pytest\.mark\.\w+)$",
            r"pytestmark = [pytest.mark.e2e, \1]",
            text,
            flags=re.MULTILINE,
        )
        new = re.sub(
            r"^pytestmark = \[(.*)\]$",
            lambda m: (
                f"pytestmark = [pytest.mark.e2e, {m.group(1)}]"
                if "pytest.mark.e2e" not in m.group(1)
                else m.group(0)
            ),
            new,
            flags=re.MULTILINE,
        )
    else:
        # No pytestmark at all — add one after imports
        lines = text.splitlines()
        last_import = -1
        for i, line in enumerate(lines):
            if line.startswith(("import ", "from ")):
                last_import = i
        new = (
            "\n".join(lines[: last_import + 1])
            + "\n\npytestmark = pytest.mark.e2e\n"
            + "\n".join(lines[last_import + 1 :])
        )
    if new != text:
        path.write_text(new)
        print(f"  marked: {path.name}")
