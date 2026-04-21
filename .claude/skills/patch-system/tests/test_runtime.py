"""Tests for patch_system.runtime — runtime.json loading (jalon 14).

Covers :

- Absent file → hardcoded defaults per §3.3 (verbatim).
- Valid overrides merge on top of defaults.
- Unknown top-level keys raise.
- Unknown sections in overrides raise.
- Bad schema_version raises.
- resolve_strategy returns merged dict per id.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from patch_system import runtime as rt  # noqa: E402


class TestDefaults(unittest.TestCase):
    def test_defaults_shape_matches_design_3_3(self):
        d = rt.default_runtime()
        self.assertEqual(d["schema_version"], "1")
        # §3.3 lines 241-244 — verbatim shape.
        self.assertEqual(d["defaults"]["detection"]["strategy"], "composite")
        self.assertIn("checksum", d["defaults"]["detection"]["signals"])
        self.assertEqual(d["defaults"]["apply"]["method"], "git-apply")
        self.assertIn("--index", d["defaults"]["apply"]["args"])
        self.assertIn("--reverse", d["defaults"]["rollback"]["args"])
        self.assertEqual(d["defaults"]["drift"]["mode"], "verbose")

    def test_load_absent_file_returns_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            got = rt.load_runtime(p)
            self.assertEqual(got, rt.default_runtime())


class TestLoadValidation(unittest.TestCase):
    def _write(self, patches_dir: Path, payload: dict) -> None:
        patches_dir.mkdir(parents=True, exist_ok=True)
        (patches_dir / "runtime.json").write_text(json.dumps(payload))

    def test_unknown_top_level_key_raises(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            self._write(p, {"schema_version": "1", "bogus": {}})
            with self.assertRaises(rt.RuntimeError_):
                rt.load_runtime(p)

    def test_bad_schema_version_raises(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            self._write(p, {"schema_version": "999"})
            with self.assertRaises(rt.RuntimeError_):
                rt.load_runtime(p)

    def test_override_unknown_section_raises(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            self._write(p, {
                "schema_version": "1",
                "overrides": {"b1": {"bogus": {}}},
            })
            with self.assertRaises(rt.RuntimeError_):
                rt.load_runtime(p)

    def test_valid_override_loads(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            self._write(p, {
                "schema_version": "1",
                "overrides": {
                    "b1-foo": {
                        "apply": {"method": "patch", "args": ["-p1", "-N"]},
                    },
                },
            })
            got = rt.load_runtime(p)
            self.assertEqual(
                got["overrides"]["b1-foo"]["apply"]["method"], "patch",
            )


class TestResolveStrategy(unittest.TestCase):
    def test_resolve_no_override_returns_defaults(self):
        runtime = rt.default_runtime()
        strategy = rt.resolve_strategy("any-id", runtime)
        self.assertEqual(strategy["apply"]["method"], "git-apply")

    def test_resolve_with_override_merges(self):
        runtime = rt.default_runtime()
        runtime["overrides"]["b1"] = {
            "apply": {"method": "patch", "args": ["-p1", "-N"]},
        }
        strategy = rt.resolve_strategy("b1", runtime)
        self.assertEqual(strategy["apply"]["method"], "patch")
        self.assertEqual(strategy["apply"]["args"], ["-p1", "-N"])
        # Other sections untouched.
        self.assertEqual(strategy["rollback"]["args"], ["--reverse", "--index"])

    def test_resolve_other_id_not_impacted(self):
        runtime = rt.default_runtime()
        runtime["overrides"]["b1"] = {
            "apply": {"method": "patch", "args": ["-p1"]},
        }
        strategy = rt.resolve_strategy("b2", runtime)
        self.assertEqual(strategy["apply"]["method"], "git-apply")


if __name__ == "__main__":
    unittest.main()
