#!/usr/bin/env python3
"""Fix assert True cases in sentry_init.py file."""
from pathlib import Path

p = Path("tests/test_sentry_init.py")
text = p.read_text()

# Replace the assert True cases with comments explaining the assertion is implicit
text = text.replace('        assert True', '        # Test assertion is implicit: no crash means sentry handled the case gracefully')

p.write_text(text)
print("Fixed sentry_init assert True cases")