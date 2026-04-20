"""Tests for patch_system.apply — git apply --index engine (jalon 6).

Each test sets up a throwaway git repo under a tempdir, stages the
vendor-mini fixture content, commits it, then invokes `apply_patch`
against `tests/fixtures/patches/0001-readme-add-section.patch` (or 0002).

The real vendor tree (vendor/obsidian-wiki) is never touched.
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
from patch_system import detect, registry  # noqa: E402


_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_VENDOR_PRISTINE = _FIXTURES / "vendor-mini"
_VENDOR_PATCHED = _FIXTURES / "vendor-mini-patched"
_PATCHES_DIR = _FIXTURES / "patches"


def _load_fixture_records() -> list[dict]:
    with (_FIXTURES / "series.json").open("r", encoding="utf-8") as f:
        return json.load(f)["records"]


def _fixture_record(rid: str) -> dict:
    for r in _load_fixture_records():
        if r["id"] == rid:
            return r
    raise AssertionError(f"fixture record not found: {rid}")


class ApplyTestBase(unittest.TestCase):
    """Common setUp: build a fresh git repo cloning the pristine fixture.

    Also skip the whole class if git is not available.
    """

    def setUp(self) -> None:
        if not shutil.which("git"):
            self.skipTest("git not installed — apply tests skipped")

        self._tmp = Path(tempfile.mkdtemp(prefix="patch-system-apply-"))
        self.vendor_root = self._tmp / "vendor"
        shutil.copytree(_VENDOR_PRISTINE, self.vendor_root, symlinks=True)
        # Initialise git repo so `git apply --index` has something to
        # diff against.
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
                "git", "-c", "user.email=test@t.invalid",
                "-c", "user.name=test", "commit", "-q", "-m", "init",
            ],
            cwd=self.vendor_root, check=True, capture_output=True,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestApplyCleanPath(ApplyTestBase):
    def test_apply_from_clean_succeeds(self):
        r = _fixture_record("t0001-readme-add-section")
        result = apply_mod.apply_patch(
            r, self.vendor_root, _PATCHES_DIR, dry_run=False, yes=False,
        )
        self.assertTrue(result["success"], result["message"])
        self.assertEqual(result["from_state"], "clean")
        self.assertEqual(result["to_state"], "patched")
        # Working tree has been mutated — README.md now has the section.
        readme = (self.vendor_root / "README.md").read_text(encoding="utf-8")
        self.assertIn("Local notes", readme)

    def test_apply_idempotent_from_patched_no_op(self):
        r = _fixture_record("t0001-readme-add-section")
        # Point vendor_root at the pre-patched tree.
        patched_root = self._tmp / "vendor-patched"
        shutil.copytree(_VENDOR_PATCHED, patched_root, symlinks=True)
        subprocess.run(
            ["git", "init", "-q"], cwd=patched_root, check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "add", "-A"], cwd=patched_root, check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git", "-c", "user.email=test@t.invalid",
                "-c", "user.name=test", "commit", "-q", "-m", "init",
            ],
            cwd=patched_root, check=True, capture_output=True,
        )
        result = apply_mod.apply_patch(
            r, patched_root, _PATCHES_DIR, dry_run=False, yes=False,
        )
        self.assertTrue(result["success"], result["message"])
        self.assertEqual(result["from_state"], "patched")
        self.assertEqual(result["to_state"], "patched")
        self.assertTrue(result.get("noop"))
        self.assertIn("skip", result["message"])


class TestApplyNonCleanPaths(ApplyTestBase):
    def test_apply_from_dirty_without_yes_fails(self):
        # Patch 0004 is semantic drift → partial on vendor-mini.
        r = _fixture_record("t0004-cmd2-semantic-drift")
        result = apply_mod.apply_patch(
            r, self.vendor_root, _PATCHES_DIR, dry_run=False, yes=False,
        )
        self.assertFalse(result["success"], result["message"])
        self.assertIn(result["from_state"], ("partial", "dirty"))
        self.assertEqual(result["to_state"], result["from_state"])
        self.assertIn("--interactive", result["message"])

    def test_apply_from_dirty_with_yes_still_fails_explicitly(self):
        # --yes alone must not force-apply (§4.3 — rerun with --interactive
        # or --force). The failure message is explicit about it.
        r = _fixture_record("t0004-cmd2-semantic-drift")
        result = apply_mod.apply_patch(
            r, self.vendor_root, _PATCHES_DIR, dry_run=False, yes=True,
        )
        self.assertFalse(result["success"], result["message"])
        self.assertIn("--yes mode forbids interactive arbitration",
                      result["message"])

    def test_apply_from_absent_fails(self):
        # Synthesise a record that targets a non-existent file.
        r = {
            "id": "synthetic-absent",
            "order": 999,
            "status": "active",
            "severity": "INFO",
            "title": "absent target",
            "patch_file": "0001-readme-add-section.patch",  # any real patch
            "patch_sha256": "a" * 64,
            "targets": [
                {
                    "path": "vendor/obsidian-wiki/does/not/exist.md",
                    "baseline_sha256": "a" * 64,
                    "patched_sha256": "b" * 64,
                }
            ],
        }
        result = apply_mod.apply_patch(
            r, self.vendor_root, _PATCHES_DIR, dry_run=False, yes=False,
        )
        self.assertFalse(result["success"], result["message"])
        self.assertEqual(result["from_state"], "absent")
        self.assertIn("absent", result["message"])


class TestApplyDryRun(ApplyTestBase):
    def test_apply_dry_run_no_writes(self):
        r = _fixture_record("t0001-readme-add-section")
        # Pre-read README content to assert it is unchanged afterwards.
        readme_before = (self.vendor_root / "README.md").read_text(
            encoding="utf-8"
        )
        result = apply_mod.apply_patch(
            r, self.vendor_root, _PATCHES_DIR, dry_run=True, yes=False,
        )
        self.assertTrue(result["success"], result["message"])
        self.assertTrue(result.get("dry_run"))
        self.assertIn("would apply", result["message"])
        self.assertIn("[dry-run]", result["message"])
        readme_after = (self.vendor_root / "README.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(readme_before, readme_after)


class TestApplyRegistryUpdate(ApplyTestBase):
    def test_apply_updates_last_applied_timestamp(self):
        r = _fixture_record("t0001-readme-add-section")
        # Build a small registry payload we can roundtrip.
        registry_path = self._tmp / "series.json"
        payload = {
            "schema_version": "1",
            "records": [dict(r)],  # shallow copy
        }
        result = apply_mod.apply_patch(
            r, self.vendor_root, _PATCHES_DIR,
            dry_run=False, yes=False,
            registry_path=registry_path, all_records=payload,
        )
        self.assertTrue(result["success"], result["message"])
        # Registry file written.
        self.assertTrue(registry_path.exists())
        saved = registry.load(registry_path)
        saved_rec = saved["records"][0]
        self.assertIn("last_applied", saved_rec)
        # ISO UTC format, ends with Z.
        self.assertTrue(
            saved_rec["last_applied"].endswith("Z"),
            saved_rec["last_applied"],
        )
        # Parse to ensure well-formed.
        import datetime as dt
        dt.datetime.strptime(saved_rec["last_applied"], "%Y-%m-%dT%H:%M:%SZ")

    def test_apply_updates_last_result(self):
        r = _fixture_record("t0001-readme-add-section")
        registry_path = self._tmp / "series.json"
        payload = {
            "schema_version": "1",
            "records": [dict(r)],
        }
        result = apply_mod.apply_patch(
            r, self.vendor_root, _PATCHES_DIR,
            dry_run=False, yes=False,
            registry_path=registry_path, all_records=payload,
        )
        self.assertTrue(result["success"], result["message"])
        saved = registry.load(registry_path)
        self.assertEqual(saved["records"][0].get("last_result"), "patched")

    def test_apply_dry_run_does_not_touch_registry(self):
        r = _fixture_record("t0001-readme-add-section")
        registry_path = self._tmp / "series.json"
        payload = {
            "schema_version": "1",
            "records": [dict(r)],
        }
        # Dry-run pathway must not persist.
        result = apply_mod.apply_patch(
            r, self.vendor_root, _PATCHES_DIR,
            dry_run=True, yes=False,
            registry_path=registry_path, all_records=payload,
        )
        self.assertTrue(result["success"], result["message"])
        # File was never written.
        self.assertFalse(
            registry_path.exists(),
            f"registry should not be persisted on dry-run, found: {registry_path}",
        )


if __name__ == "__main__":
    unittest.main()
