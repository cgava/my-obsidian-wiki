"""Tests for patch_system.detect — sha256-only v1."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from patch_system import detect  # noqa: E402


_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_VENDOR_PRISTINE = _FIXTURES / "vendor-mini"
_VENDOR_PATCHED = _FIXTURES / "vendor-mini-patched"


def _load_series() -> list[dict]:
    with (_FIXTURES / "series.json").open("r", encoding="utf-8") as f:
        return json.load(f)["records"]


def _patch_by_id(pid: str) -> dict:
    for p in _load_series():
        if p["id"] == pid:
            return p
    raise AssertionError(f"fixture record not found: {pid}")


class TestSingleTarget(unittest.TestCase):
    def test_detect_clean_single_target(self):
        # Pristine vendor + readme patch → clean.
        p = _patch_by_id("t0001-readme-add-section")
        self.assertEqual(detect.detect_state(p, _VENDOR_PRISTINE), "clean")

    def test_detect_patched_single_target(self):
        # Patched vendor + readme patch → patched.
        p = _patch_by_id("t0001-readme-add-section")
        self.assertEqual(detect.detect_state(p, _VENDOR_PATCHED), "patched")

    def test_detect_dirty_unknown_hash(self):
        # Patch 0003 uses placeholder sha256s that no real file matches.
        p = _patch_by_id("t0003-cmd2-drifted")
        self.assertEqual(detect.detect_state(p, _VENDOR_PRISTINE), "dirty")

    def test_detect_absent_file_missing(self):
        # Re-target a patch at a path that does not exist in vendor-mini.
        p = {
            "id": "synthetic-absent",
            "targets": [
                {
                    "path": "vendor/obsidian-wiki/does/not/exist.md",
                    "baseline_sha256": "a" * 64,
                    "patched_sha256": "b" * 64,
                }
            ],
        }
        self.assertEqual(detect.detect_state(p, _VENDOR_PRISTINE), "absent")


class TestMultiTarget(unittest.TestCase):
    """Synthesise multi-target scenarios by hand-crafting patch dicts that
    reference real files under vendor-mini/ + vendor-mini-patched/.

    sha256 values come straight from the fixture tree (see _compute_sha.sh).
    """

    README_PRISTINE = "8dfa1bea1fad11f744c49a033b15d6523c4da143fa37ae5c99289b9c20cb930d"
    README_PATCHED = "2d3f15457d3a07c545335d6ff73c1c8b1d8d65441120b94832eb944019d077c0"
    CMD1_PRISTINE = "e1b2b46114293ea085f91b6a36371821eafd9b94449203e12d2a2debe9afe34e"
    CMD1_PATCHED = "38ae63d40c263100b1bdcb6e4ea064ff4a3544f85de7f491cde5b9bd44275d8a"

    def _patch_two_targets(self) -> dict:
        return {
            "id": "synthetic-multi",
            "targets": [
                {
                    "path": "vendor/obsidian-wiki/README.md",
                    "baseline_sha256": self.README_PRISTINE,
                    "patched_sha256": self.README_PATCHED,
                },
                {
                    "path": "vendor/obsidian-wiki/bin/cmd1.sh",
                    "baseline_sha256": self.CMD1_PRISTINE,
                    "patched_sha256": self.CMD1_PATCHED,
                },
            ],
        }

    def test_detect_multi_target_all_clean(self):
        p = self._patch_two_targets()
        self.assertEqual(detect.detect_state(p, _VENDOR_PRISTINE), "clean")

    def test_detect_multi_target_all_patched(self):
        p = self._patch_two_targets()
        self.assertEqual(detect.detect_state(p, _VENDOR_PATCHED), "patched")

    def test_detect_multi_target_mixed_returns_partial(self):
        # Hybrid tree: README is patched, cmd1 is pristine. Swap targets:
        # point README at the pristine sha but cmd1 at the patched sha, and
        # resolve against the "patched" tree — actually a cleaner construction:
        # build an in-memory "patched README, pristine cmd1" tree via paths
        # that pick one file from each fixture root.
        p = {
            "id": "synthetic-mixed",
            "targets": [
                # README resolves under PATCHED tree -> patched hash matches.
                {
                    "path": "vendor/obsidian-wiki/README.md",
                    "baseline_sha256": self.README_PRISTINE,
                    "patched_sha256": self.README_PATCHED,
                },
                # cmd1 will ALSO be resolved under PATCHED tree -> patched.
                # To get a mix, retarget cmd1 at the PRISTINE tree via an
                # absolute path that sidesteps vendor_root.
                {
                    "path": str(_VENDOR_PRISTINE / "bin" / "cmd1.sh"),
                    "baseline_sha256": self.CMD1_PRISTINE,
                    "patched_sha256": self.CMD1_PATCHED,
                },
            ],
        }
        # First target hits PATCHED tree (patched), second hits PRISTINE
        # (clean via absolute path) -> partial.
        self.assertEqual(detect.detect_state(p, _VENDOR_PATCHED), "partial")

    def test_detect_multi_target_one_absent_returns_absent(self):
        p = {
            "id": "synthetic-one-absent",
            "targets": [
                {
                    "path": "vendor/obsidian-wiki/README.md",
                    "baseline_sha256": self.README_PRISTINE,
                    "patched_sha256": self.README_PATCHED,
                },
                {
                    "path": "vendor/obsidian-wiki/does/not/exist.md",
                    "baseline_sha256": "a" * 64,
                    "patched_sha256": "b" * 64,
                },
            ],
        }
        self.assertEqual(detect.detect_state(p, _VENDOR_PRISTINE), "absent")

    def test_detect_multi_target_one_dirty_returns_dirty(self):
        p = {
            "id": "synthetic-one-dirty",
            "targets": [
                {
                    "path": "vendor/obsidian-wiki/README.md",
                    "baseline_sha256": self.README_PRISTINE,
                    "patched_sha256": self.README_PATCHED,
                },
                # Wrong sha for cmd1 -> dirty for that target.
                {
                    "path": "vendor/obsidian-wiki/bin/cmd1.sh",
                    "baseline_sha256": "0" * 64,
                    "patched_sha256": "f" * 64,
                },
            ],
        }
        self.assertEqual(detect.detect_state(p, _VENDOR_PRISTINE), "dirty")


if __name__ == "__main__":
    unittest.main()
