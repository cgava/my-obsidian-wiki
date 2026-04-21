"""Tests for patch_system.rollback — `git apply --reverse --index` (jalon 7).

Each test sets up a throwaway git repo cloning vendor-mini-patched/,
applies patch 0001 via git first (so the tree is in the expected
"patched" state), then asserts rollback_patch restores the baseline.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from patch_system import apply as apply_mod  # noqa: E402
from patch_system import rollback as rb_mod  # noqa: E402
from patch_system import registry  # noqa: E402


_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_VENDOR_PATCHED = _FIXTURES / "vendor-mini-patched"
_VENDOR_PRISTINE = _FIXTURES / "vendor-mini"
_PATCHES_DIR = _FIXTURES / "patches"


def _fixture_record(rid: str) -> dict:
    with (_FIXTURES / "series.json").open("r", encoding="utf-8") as f:
        for r in json.load(f)["records"]:
            if r["id"] == rid:
                return r
    raise AssertionError(f"fixture record not found: {rid}")


class RollbackTestBase(unittest.TestCase):
    def setUp(self) -> None:
        if not shutil.which("git"):
            self.skipTest("git not installed — rollback tests skipped")

        # Start from PRISTINE, then apply 0001 forward so the resulting
        # tree is in the "patched" state with a clean git index. This
        # mirrors the realistic sequence (apply -> rollback).
        self._tmp = Path(tempfile.mkdtemp(prefix="patch-system-rollback-"))
        self.vendor_root = self._tmp / "vendor"
        shutil.copytree(_VENDOR_PRISTINE, self.vendor_root, symlinks=True)

        subprocess.run(
            ["git", "init", "-q"], cwd=self.vendor_root, check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "add", "-A"], cwd=self.vendor_root, check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git", "-c", "user.email=t@t.invalid",
                "-c", "user.name=t", "commit", "-q", "-m", "init",
            ],
            cwd=self.vendor_root, check=True, capture_output=True,
        )
        # Apply 0001 so the tree is in the patched state.
        apply_mod.apply_patch(
            _fixture_record("t0001-readme-add-section"),
            self.vendor_root, _PATCHES_DIR,
            dry_run=False, yes=False,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestRollbackHappyPath(RollbackTestBase):
    def test_rollback_from_patched_succeeds_state_becomes_clean(self):
        r = dict(_fixture_record("t0001-readme-add-section"))
        # rollback requires last_result=patched — simulate that.
        r["last_result"] = "patched"
        result = rb_mod.rollback_patch(
            r, self.vendor_root, _PATCHES_DIR,
            dry_run=False, yes=False,
        )
        self.assertTrue(result["success"], result["message"])
        self.assertEqual(result["from_state"], "patched")
        self.assertEqual(result["to_state"], "clean")
        # README.md must no longer contain "Local notes".
        readme = (self.vendor_root / "README.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("Local notes", readme)


class TestRollbackSafety(RollbackTestBase):
    def test_rollback_refuses_if_last_result_not_patched(self):
        r = dict(_fixture_record("t0001-readme-add-section"))
        # Simulate "never applied" — no last_result key.
        r.pop("last_result", None)
        result = rb_mod.rollback_patch(
            r, self.vendor_root, _PATCHES_DIR,
            dry_run=False, yes=False,
        )
        self.assertFalse(result["success"], result["message"])
        self.assertIn("refuse to rollback", result["message"])
        self.assertIn("last_result", result["message"])

    def test_rollback_idempotent_refuse_from_clean(self):
        # Tree is actually patched at this point; but we set last_result
        # to 'clean' to simulate a registry that says "already rolled back".
        r = dict(_fixture_record("t0001-readme-add-section"))
        r["last_result"] = "clean"
        result = rb_mod.rollback_patch(
            r, self.vendor_root, _PATCHES_DIR,
            dry_run=False, yes=False,
        )
        self.assertFalse(result["success"], result["message"])
        self.assertIn("refuse", result["message"])


class TestRollbackDryRun(RollbackTestBase):
    def test_rollback_dry_run_no_writes(self):
        r = dict(_fixture_record("t0001-readme-add-section"))
        r["last_result"] = "patched"
        readme_before = (self.vendor_root / "README.md").read_text(
            encoding="utf-8"
        )
        result = rb_mod.rollback_patch(
            r, self.vendor_root, _PATCHES_DIR,
            dry_run=True, yes=False,
        )
        self.assertTrue(result["success"], result["message"])
        self.assertTrue(result.get("dry_run"))
        self.assertIn("would rollback", result["message"])
        readme_after = (self.vendor_root / "README.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(readme_before, readme_after)


class TestRollbackRegistryUpdate(RollbackTestBase):
    def test_rollback_updates_registry(self):
        r = dict(_fixture_record("t0001-readme-add-section"))
        r["last_result"] = "patched"
        registry_path = self._tmp / "series.json"
        payload = {"schema_version": "1", "records": [dict(r)]}
        result = rb_mod.rollback_patch(
            r, self.vendor_root, _PATCHES_DIR,
            dry_run=False, yes=False,
            registry_path=registry_path, all_records=payload,
        )
        self.assertTrue(result["success"], result["message"])
        self.assertTrue(registry_path.exists())
        saved = registry.load(registry_path)
        saved_rec = saved["records"][0]
        self.assertEqual(saved_rec.get("last_result"), "clean")
        self.assertTrue(
            saved_rec.get("last_applied", "").endswith("Z"),
            saved_rec.get("last_applied"),
        )


if __name__ == "__main__":
    unittest.main()
