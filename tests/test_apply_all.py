"""Tests for ``apply --all`` / ``rollback --all`` (jalon 13).

Covers :

- ``apply --all --dry-run`` on a series of clean records → all would-apply.
- ``apply --all`` without ``--stop-on-fail`` : continues past a failing
  record, exits 1 at the end.
- ``apply --all --stop-on-fail`` : stops at the first failing record.
- ``rollback --all`` pops records in descending ``order`` (§4.1 line 307).
- ``q`` in the interactive menu on record #2 breaks iteration cleanly ;
  record #1 stays applied, #3 is not tried.

The CLI is driven via :func:`patch_system.cli.main` with a handcrafted
``series.json`` in a tempdir so ``--all`` iterates the records we want.
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from patch_system import cli  # noqa: E402


_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_VENDOR_PRISTINE = _FIXTURES / "vendor-mini"
_PATCH_FILES_SRC = _FIXTURES / "patches"


def _fixture_records() -> list[dict]:
    with (_FIXTURES / "series.json").open("r", encoding="utf-8") as f:
        return json.load(f)["records"]


class _AllHarness(unittest.TestCase):
    """Build an isolated tempdir layout :

        tmp/
          vendor/              git repo init from vendor-mini
          patches/
            series.json
            0001-*.patch
            0002-*.patch
            ...
    """

    def setUp(self) -> None:
        if not shutil.which("git"):
            self.skipTest("git not installed")
        self._tmp = Path(tempfile.mkdtemp(prefix="patch-system-all-"))
        self.vendor_root = self._tmp / "vendor"
        shutil.copytree(_VENDOR_PRISTINE, self.vendor_root, symlinks=True)
        subprocess.run(["git", "init", "-q"], cwd=self.vendor_root, check=True, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=self.vendor_root, check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t.invalid", "-c", "user.name=t",
             "commit", "-q", "-m", "init"],
            cwd=self.vendor_root, check=True, capture_output=True,
        )
        self.patches_dir = self._tmp / "patches"
        self.patches_dir.mkdir()
        # Copy patch files over.
        for p in _PATCH_FILES_SRC.iterdir():
            if p.suffix == ".patch":
                shutil.copy2(p, self.patches_dir / p.name)
        self.series_path = self.patches_dir / "series.json"

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_series(self, records: list[dict]) -> None:
        data = {"schema_version": "1", "records": records}
        self.series_path.write_text(json.dumps(data, indent=2))

    def _run_cli(self, argv: list[str]) -> tuple[int, str]:
        full_argv = [
            "--series", str(self.series_path),
            "--vendor-root", str(self.vendor_root),
        ] + argv
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli.main(full_argv)
        return rc, buf.getvalue()


class TestApplyAll(_AllHarness):
    def test_apply_all_dry_run_on_clean_series(self):
        # Two clean records — both would-apply.
        recs = [r for r in _fixture_records() if r["id"] in (
            "t0001-readme-add-section", "t0002-cmd1-fix-typo",
        )]
        self._write_series(recs)
        rc, out = self._run_cli(["apply", "--all", "--dry-run"])
        self.assertEqual(rc, 0, out)
        self.assertIn("would apply", out)
        # Summary line (§4.3 inspired).
        self.assertIn("apply --all:", out)

    def test_apply_all_continues_past_failure_without_stop_flag(self):
        recs = _fixture_records()  # includes 0004 (semantic drift) → fails
        self._write_series(recs)
        rc, out = self._run_cli(["apply", "--all"])
        # At least 2 clean records applied, 0004 failed.
        self.assertEqual(rc, 1, out)
        self.assertIn("t0001-readme-add-section", out)
        self.assertIn("t0002-cmd1-fix-typo", out)
        # Summary says "failed" >= 1.
        self.assertIn("failed", out)

    def test_apply_all_stop_on_fail_halts_after_first_failure(self):
        # Order the failing record (0004) between two cleans by rewiring
        # orders: 0001(order=1), 0004(order=2 with forced clean failure),
        # 0002(order=3).
        recs = _fixture_records()
        r1 = dict(next(r for r in recs if r["id"] == "t0001-readme-add-section"))
        r4 = dict(next(r for r in recs if r["id"] == "t0004-cmd2-semantic-drift"))
        r4["order"] = 2
        r2 = dict(next(r for r in recs if r["id"] == "t0002-cmd1-fix-typo"))
        r2["order"] = 3
        self._write_series([r1, r4, r2])
        rc, out = self._run_cli(["apply", "--all", "--stop-on-fail"])
        self.assertEqual(rc, 1, out)
        # The third record id should NOT appear (run halted).
        self.assertIn("t0004-cmd2-semantic-drift", out)
        self.assertNotIn("t0002-cmd1-fix-typo", out.split("apply --all:")[0])

    def test_quit_in_menu_breaks_iteration(self):
        """``q`` in the interactive menu on record #2 breaks iteration.
        Record #1 stays applied, record #3 is not attempted.
        """
        recs = _fixture_records()
        r1 = dict(next(r for r in recs if r["id"] == "t0001-readme-add-section"))
        r4 = dict(next(r for r in recs if r["id"] == "t0004-cmd2-semantic-drift"))
        r4["order"] = 2
        r2 = dict(next(r for r in recs if r["id"] == "t0002-cmd1-fix-typo"))
        r2["order"] = 3
        self._write_series([r1, r4, r2])

        # Feed 'q' as the first menu choice.
        prompts = iter(["q"])

        def _fake_input(_msg):
            return next(prompts)

        # Patch __builtins__.input used by the UI module (apply.apply_patch
        # passes prompt_fn=None which defaults to input in ui.py).
        with mock.patch("patch_system.ui.input", _fake_input):
            rc, out = self._run_cli(["apply", "--all", "--interactive"])

        # r1 clean applies, r4 prompts → q quits, r2 never tried.
        self.assertIn("t0001-readme-add-section", out)
        self.assertIn("t0004-cmd2-semantic-drift", out)
        self.assertNotIn("t0002-cmd1-fix-typo", out.split("apply --all:")[0])
        self.assertIn("user quit", out)
        self.assertEqual(rc, 0, out)  # q is clean exit per §4.2


class TestRollbackAll(_AllHarness):
    def test_rollback_all_descending_order_after_apply_all(self):
        # Apply two clean records, then roll back --all.
        recs = [r for r in _fixture_records() if r["id"] in (
            "t0001-readme-add-section", "t0002-cmd1-fix-typo",
        )]
        # Make sure orders are 1 and 2.
        r1 = dict(next(r for r in recs if r["id"] == "t0001-readme-add-section"))
        r1["order"] = 1
        r2 = dict(next(r for r in recs if r["id"] == "t0002-cmd1-fix-typo"))
        r2["order"] = 2
        self._write_series([r1, r2])

        rc_apply, _ = self._run_cli(["apply", "--all"])
        self.assertEqual(rc_apply, 0)

        rc_rb, out_rb = self._run_cli(["rollback", "--all"])
        self.assertEqual(rc_rb, 0, out_rb)
        # Descending order : r2 comes before r1 in stdout.
        pos2 = out_rb.find("t0002-cmd1-fix-typo")
        pos1 = out_rb.find("t0001-readme-add-section")
        self.assertGreater(pos2, -1)
        self.assertGreater(pos1, -1)
        self.assertLess(pos2, pos1, f"expected r2 before r1, got:\n{out_rb}")


if __name__ == "__main__":
    unittest.main()
