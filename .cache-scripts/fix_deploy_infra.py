#!/usr/bin/env python3
"""Fix the test_release_off_main_refuses test in tests/test_deploy_infra.py."""
from pathlib import Path

p = Path("tests/test_deploy_infra.py")
text = p.read_text()

old = '''    def test_release_off_main_refuses(self):
        r = subprocess.run(
            ["bash", str(SCRIPTS_DIR / "release.sh"), "--dry-run"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=REPO_ROOT,
        )
        # We're on feat/three-env-deploy, so release.sh should refuse
        # with a clear "must run from main" message.
        self.assertNotEqual(r.returncode, 0)
        out = r.stdout + r.stderr
        self.assertIn("main", out.lower())'''

new = '''    def test_release_off_main_refuses(self):
        # Test is meaningful only on a non-main branch (was originally
        # written for feat/three-env-deploy). Skip on main.
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        if branch == "main":
            self.skipTest("Test is only meaningful on a non-main branch")

        r = subprocess.run(
            ["bash", str(SCRIPTS_DIR / "release.sh"), "--dry-run"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=REPO_ROOT,
        )
        # We're on a non-main branch, so release.sh should refuse
        # with a clear "must run from main" message.
        self.assertNotEqual(r.returncode, 0)
        out = r.stdout + r.stderr
        self.assertIn("main", out.lower())'''

if old in text:
    text = text.replace(old, new)
    p.write_text(text)
    print("OK - replaced")
else:
    print("Old text not found, file starts with:")
    print(text[text.find("test_release_off_main_refuses")-50:text.find("test_release_off_main_refuses")+500])
