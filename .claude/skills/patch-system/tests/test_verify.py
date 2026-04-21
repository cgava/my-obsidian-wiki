"""Tests for patch_system.verify — jalon 9.

Covers :
- Empty registry → exit 0, "nothing to verify".
- All-ok record → exit 0, ``[id] ok`` line per record.
- Integrity mismatch (patch file on disk edited) → exit 1.
- Missing target file (active record) → exit 1.
- ``--json`` produces valid JSON with ``records`` + ``summary``.
- ``--strict`` upgrades drift warning to failure.
- Invalid registry (schema violation) → exit 3.
"""

from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from patch_system import registry, verify  # noqa: E402

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_VENDOR_PRISTINE = _FIXTURES / "vendor-mini"
_PATCHES_DIR = _FIXTURES / "patches"
_SERIES_FIX = _FIXTURES / "series.json"


class VerifyTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="patch-system-verify-"))
        # Layout a fresh project root.
        self.vendor_root = self._tmp / "vendor"
        shutil.copytree(_VENDOR_PRISTINE, self.vendor_root, symlinks=True)
        self.patches_dir = self._tmp / "patches"
        self.patches_dir.mkdir()
        shutil.copy2(_SERIES_FIX, self.patches_dir / "series.json")
        for p in _PATCHES_DIR.glob("*.patch"):
            shutil.copy2(p, self.patches_dir / p.name)
        self.data = registry.load(self.patches_dir / "series.json")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestVerifyEmpty(unittest.TestCase):
    def test_empty_registry_exit_0(self):
        data = {"schema_version": "1", "records": []}
        buf = io.StringIO()
        rc = verify.verify(data, Path("/tmp"), Path("/tmp"), stream=buf)
        self.assertEqual(rc, 0)
        self.assertIn("empty", buf.getvalue())

    def test_empty_registry_json(self):
        data = {"schema_version": "1", "records": []}
        buf = io.StringIO()
        rc = verify.verify(
            data, Path("/tmp"), Path("/tmp"), json_output=True, stream=buf
        )
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["records"], {})
        self.assertEqual(payload["summary"]["ok"], 0)


class TestVerifyIntegrity(VerifyTestBase):
    def test_all_ok_exit_0(self):
        # vendor-mini is pristine for t0001 + t0002 ; integrity of every
        # patch on disk matches the recorded sha. Records t0003/t0004 are
        # fixture cases exercising drift (cmd2.sh doesn't match their
        # recorded baseline — by design of the fixture).
        # In non-strict mode drift is a warning → exit 0.
        buf = io.StringIO()
        rc = verify.verify(
            self.data, self.vendor_root, self.patches_dir, stream=buf
        )
        self.assertEqual(rc, 0, buf.getvalue())
        out = buf.getvalue()
        # Records 0001 + 0002 : fully ok.
        self.assertIn("[t0001-readme-add-section] ok", out, out)
        self.assertIn("[t0002-cmd1-fix-typo] ok", out, out)
        # Records 0003 + 0004 : drift detected, still non-strict-OK.
        self.assertIn("drift=detected", out, out)
        self.assertIn("all records ok", out)

    def test_tampered_patch_exits_1(self):
        # Append a garbage line to 0001-patch → integrity breaks.
        target = self.patches_dir / "0001-readme-add-section.patch"
        with target.open("a", encoding="utf-8") as f:
            f.write("garbage-tamper\n")
        buf = io.StringIO()
        rc = verify.verify(
            self.data, self.vendor_root, self.patches_dir, stream=buf
        )
        self.assertEqual(rc, 1, buf.getvalue())
        self.assertIn("integrity", buf.getvalue())
        self.assertIn("tampered", buf.getvalue())

    def test_missing_patch_file_exits_1(self):
        (self.patches_dir / "0001-readme-add-section.patch").unlink()
        buf = io.StringIO()
        rc = verify.verify(
            self.data, self.vendor_root, self.patches_dir, stream=buf
        )
        self.assertEqual(rc, 1, buf.getvalue())
        self.assertIn("missing", buf.getvalue())


class TestVerifyCoherence(VerifyTestBase):
    def test_missing_target_exits_1(self):
        # Remove README.md from the vendor tree.
        (self.vendor_root / "README.md").unlink()
        buf = io.StringIO()
        rc = verify.verify(
            self.data, self.vendor_root, self.patches_dir, stream=buf
        )
        self.assertEqual(rc, 1, buf.getvalue())
        self.assertIn("missing target", buf.getvalue())


class TestVerifyDrift(VerifyTestBase):
    def test_per_target_drift_warning_non_strict(self):
        # Mutate README.md so its sha is neither baseline nor patched.
        readme = self.vendor_root / "README.md"
        with readme.open("a", encoding="utf-8") as f:
            f.write("rogue drift line\n")
        buf = io.StringIO()
        rc = verify.verify(
            self.data, self.vendor_root, self.patches_dir, stream=buf
        )
        # Drift alone without --strict is a warning → exit 0 still.
        self.assertEqual(rc, 0, buf.getvalue())
        self.assertIn("drift=detected", buf.getvalue())

    def test_per_target_drift_strict_exits_1(self):
        readme = self.vendor_root / "README.md"
        with readme.open("a", encoding="utf-8") as f:
            f.write("rogue drift line\n")
        buf = io.StringIO()
        rc = verify.verify(
            self.data, self.vendor_root, self.patches_dir,
            strict=True, stream=buf,
        )
        self.assertEqual(rc, 1, buf.getvalue())


class TestVerifyJSON(VerifyTestBase):
    def test_json_valid_output(self):
        buf = io.StringIO()
        rc = verify.verify(
            self.data, self.vendor_root, self.patches_dir,
            json_output=True, stream=buf,
        )
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["registry_valid"])
        self.assertIn("t0001-readme-add-section", payload["records"])
        rec = payload["records"]["t0001-readme-add-section"]
        self.assertEqual(rec["integrity"], "ok")
        self.assertEqual(rec["coherence"], "ok")

    def test_json_after_tamper(self):
        target = self.patches_dir / "0001-readme-add-section.patch"
        with target.open("a", encoding="utf-8") as f:
            f.write("garbage\n")
        buf = io.StringIO()
        rc = verify.verify(
            self.data, self.vendor_root, self.patches_dir,
            json_output=True, stream=buf,
        )
        self.assertEqual(rc, 1)
        payload = json.loads(buf.getvalue())
        self.assertEqual(
            payload["records"]["t0001-readme-add-section"]["integrity"],
            "mismatch",
        )


class TestVerifyInvalidRegistry(VerifyTestBase):
    def test_schema_violation_exit_3(self):
        # Remove a required field from a record → registry.validate fails.
        bad = {
            "schema_version": "1",
            "records": [
                {"id": "x", "order": 1, "status": "active",
                 "severity": "INFO", "title": "t",
                 # missing patch_file / patch_sha256 / targets
                 },
            ],
        }
        buf = io.StringIO()
        rc = verify.verify(
            bad, self.vendor_root, self.patches_dir, stream=buf
        )
        self.assertEqual(rc, 3, buf.getvalue())
        self.assertIn("registry invalid", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
