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
        # Patch 0003 references a conceptual "pristine" baseline sha; the
        # on-disk vendor-mini/bin/cmd2.sh carries a top blank-line drift,
        # so its sha matches neither baseline_sha256 nor patched_sha256.
        # Aggregated sha-only detect returns `dirty` (composite detection
        # reclassifies it to `clean`+cosmetic on forward --check success —
        # see TestEvaluateComposite).
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


class TestEvaluateComposite(unittest.TestCase):
    """Composite detection (jalon 5) — sha256 + git apply --check.

    Semantic mapping:
      - forward `--check` succeeds → state=clean, drift_hint=cosmetic
        (pre-patch compatible state with baseline drift).
      - reverse `--check` succeeds → state=patched, drift_hint=cosmetic
        (post-patch compatible state with patched drift).

    Exercised against the enriched fixture set:
      - t0003-cmd2-drifted      cosmetic drift (blank line drift)
      - t0004-cmd2-semantic-drift semantic drift (partial: 1/2 hunks)
    """

    PATCHES_DIR = _FIXTURES / "patches"

    def setUp(self) -> None:
        # Skip if git is not installed. Composite detection requires it.
        import shutil as _shutil

        if not _shutil.which("git"):
            self.skipTest("git not installed — composite detection skipped")

    def test_evaluate_returns_full_dict(self):
        """evaluate() returns the contract dict: state/per_target/
        can_auto_3way/drift_hint keys always present."""
        p = _patch_by_id("t0001-readme-add-section")
        result = detect.evaluate(p, _VENDOR_PRISTINE, self.PATCHES_DIR)
        for key in ("state", "per_target", "can_auto_3way", "drift_hint"):
            self.assertIn(key, result, f"missing key {key} in {result}")
        self.assertIsInstance(result["per_target"], list)
        self.assertEqual(len(result["per_target"]), 1)
        # On a clean sha-match record, state stays `clean` and drift_hint
        # is None (we never call git).
        self.assertEqual(result["state"], "clean")
        self.assertIsNone(result["drift_hint"])

    def test_evaluate_forward_cosmetic_drift_is_clean(self):
        """Patch 0003 on vendor-mini (pre-patch content + blank-line drift):
        sha-agg=dirty, forward `git apply --check` succeeds → state=clean,
        hint=cosmetic. The patch would still apply forward, so the file is
        in a pre-patch compatible state with cosmetic drift on baseline."""
        p = _patch_by_id("t0003-cmd2-drifted")
        result = detect.evaluate(p, _VENDOR_PRISTINE, self.PATCHES_DIR)
        self.assertEqual(
            result["state"], "clean", f"result={result}"
        )
        self.assertEqual(result["drift_hint"], "cosmetic")
        # per_target[0] should reflect the composite reclassification.
        self.assertEqual(result["per_target"][0]["state"], "clean")

    def test_evaluate_reverse_cosmetic_drift_is_patched(self):
        """Patch 0003 on vendor-mini-patched (post-patch content + blank-
        line drift): sha-agg=dirty, forward --check fails, reverse --check
        succeeds → state=patched, hint=cosmetic. The patch can still be
        reverted, so the file is post-patch with cosmetic drift on the
        patched side."""
        p = _patch_by_id("t0003-cmd2-drifted")
        result = detect.evaluate(p, _VENDOR_PATCHED, self.PATCHES_DIR)
        self.assertEqual(
            result["state"], "patched", f"result={result}"
        )
        self.assertEqual(result["drift_hint"], "cosmetic")
        self.assertEqual(result["per_target"][0]["state"], "patched")

    def test_evaluate_semantic_drift_returns_partial_or_dirty(self):
        """Patch 0004 on vendor-mini: 2-hunk patch, hunk 1 applyable,
        hunk 2 rejected (upstream renamed a line). Expected: partial."""
        p = _patch_by_id("t0004-cmd2-semantic-drift")
        result = detect.evaluate(p, _VENDOR_PRISTINE, self.PATCHES_DIR)
        self.assertIn(
            result["state"],
            ("partial", "dirty"),
            f"expected partial or dirty, got {result}",
        )
        # Per-hunk split: 1/2 hunks apply → partial is the precise answer.
        self.assertEqual(
            result["state"], "partial", f"result={result}"
        )
        self.assertEqual(result["drift_hint"], "semantic")

    def test_evaluate_can_auto_3way_true_for_cosmetic(self):
        """Cosmetic drift (offset-only): `git apply --3way --check` succeeds."""
        p = _patch_by_id("t0003-cmd2-drifted")
        result = detect.evaluate(p, _VENDOR_PRISTINE, self.PATCHES_DIR)
        self.assertTrue(
            result["can_auto_3way"],
            f"can_auto_3way should be True for cosmetic drift, got {result}",
        )

    def test_evaluate_can_auto_3way_false_for_semantic(self):
        """Semantic drift (renamed line): 3way can't bridge the gap."""
        p = _patch_by_id("t0004-cmd2-semantic-drift")
        result = detect.evaluate(p, _VENDOR_PRISTINE, self.PATCHES_DIR)
        self.assertFalse(
            result["can_auto_3way"],
            f"can_auto_3way should be False for semantic drift, got {result}",
        )

    def test_evaluate_clean_does_not_invoke_git(self):
        """Sanity: a sha-matching `clean` record never hits the git path.

        We smoke-test this by pointing `patches_dir` at a non-existent
        directory — if evaluate() tried to read the .patch file we would
        see a lookup error. With state=clean, it must stay clean.
        """
        p = _patch_by_id("t0001-readme-add-section")
        result = detect.evaluate(p, _VENDOR_PRISTINE, Path("/nope/does-not-exist"))
        self.assertEqual(result["state"], "clean")


if __name__ == "__main__":
    unittest.main()
