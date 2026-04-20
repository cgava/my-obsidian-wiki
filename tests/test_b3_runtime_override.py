"""E2E regression test : REV-0006 #2 — b3 gitignored target unblocked.

Before jalon 14, ``apply --dry-run b3-vendor-env-remove`` failed with
``does not exist in index`` because ``vendor/.env`` is gitignored and
``git apply --index`` refuses to touch untracked files.

The runtime.json override at ``patches/runtime.json`` routes b3 through
``patch(1) -p1 -N`` which has no index requirement. This test asserts
the real dry-run now returns exit 0.

Skipped when ``patch(1)`` is not installed on the host.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from patch_system import cli  # noqa: E402


class TestB3RuntimeOverride(unittest.TestCase):
    def setUp(self) -> None:
        if not shutil.which("patch"):
            self.skipTest("patch(1) not installed")
        # Also skip if vendor tree isn't present (fresh clone without
        # submodules).
        vendor = _REPO_ROOT / "vendor" / "obsidian-wiki"
        if not vendor.exists():
            self.skipTest("vendor/obsidian-wiki not checked out")
        env_file = vendor / ".env"
        if not env_file.exists():
            self.skipTest("vendor/.env not present — b3 N/A in this tree")

    def test_b3_dry_run_returns_exit_0_with_runtime_override(self):
        """Run the real CLI against the real repo ; runtime.json drives
        the ``patch(1)`` fallback which bypasses ``--index``.
        """
        argv = [
            "--series", str(_REPO_ROOT / "patches" / "series.json"),
            "--vendor-root", str(_REPO_ROOT / "vendor" / "obsidian-wiki"),
            "apply", "b3-vendor-env-remove", "--dry-run",
        ]
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli.main(argv)
        out = buf.getvalue()
        self.assertEqual(
            rc, 0,
            f"b3 dry-run should now succeed via runtime override. Output:\n{out}",
        )
        self.assertIn("would apply", out)


if __name__ == "__main__":
    unittest.main()
