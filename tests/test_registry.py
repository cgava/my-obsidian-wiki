"""Tests for patch_system.registry — schema v1 (aligned with design §3.2)."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

# Make scripts/ importable so `import patch_system.*` resolves.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from patch_system import registry  # noqa: E402


# Placeholder hex sha256 — 64 chars, used widely across tests.
_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64


def _minimal_record() -> dict:
    """Return a single valid record (all required fields, design §3.2)."""
    return {
        "id": "b1-sample",
        "order": 1,
        "status": "active",
        "severity": "BLOCKING",
        "title": "sample record",
        "patch_file": "0001-sample.patch",
        "patch_sha256": _SHA_A,
        "targets": [
            {
                "path": "vendor/obsidian-wiki/README.md",
                "baseline_sha256": _SHA_B,
                "patched_sha256": _SHA_C,
            }
        ],
    }


def _minimal_registry(*records: dict) -> dict:
    return {
        "schema_version": registry.SCHEMA_VERSION,
        "records": list(records),
    }


class TestLoad(unittest.TestCase):
    def test_load_missing_file_returns_empty_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "does-not-exist.json"
            data = registry.load(path)
            self.assertEqual(data, {"schema_version": "1", "records": []})

    def test_load_valid_returns_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "series.json"
            payload = _minimal_registry(_minimal_record())
            path.write_text(json.dumps(payload), encoding="utf-8")
            data = registry.load(path)
            self.assertEqual(data, payload)


class TestSave(unittest.TestCase):
    def test_save_roundtrip_preserves_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "series.json"
            # Build a record with fields in a deliberate non-alphabetical order.
            r = {
                "id": "z-last-alpha",
                "order": 42,
                "status": "active",
                "severity": "TROMPEUR",
                "title": "non-alpha key order",
                "patch_file": "0042-z.patch",
                "patch_sha256": _SHA_A,
                "targets": [
                    {
                        "path": "vendor/obsidian-wiki/a.md",
                        "baseline_sha256": _SHA_B,
                        "patched_sha256": _SHA_C,
                    }
                ],
                "audit_ref": "docs/audit.md#z",
            }
            data = _minimal_registry(r)
            registry.save(path, data)
            raw = path.read_text(encoding="utf-8")
            # sort_keys=False must preserve insertion order of keys.
            idx_id = raw.index('"id"')
            idx_order = raw.index('"order"')
            idx_title = raw.index('"title"')
            self.assertLess(idx_id, idx_order)
            self.assertLess(idx_order, idx_title)
            # And the payload roundtrips byte-semantically.
            self.assertEqual(registry.load(path), data)


class TestValidate(unittest.TestCase):
    def test_validate_accepts_minimal_valid_record(self):
        data = _minimal_registry(_minimal_record())
        self.assertEqual(registry.validate(data), [])

    def test_validate_rejects_missing_required_field(self):
        r = _minimal_record()
        del r["title"]
        data = _minimal_registry(r)
        errors = registry.validate(data)
        self.assertTrue(any("title" in e for e in errors), errors)

    def test_validate_rejects_missing_status_lifecycle(self):
        r = _minimal_record()
        del r["status"]
        data = _minimal_registry(r)
        errors = registry.validate(data)
        self.assertTrue(
            any("'status'" in e for e in errors), errors
        )

    def test_validate_rejects_invalid_status_lifecycle(self):
        r = _minimal_record()
        r["status"] = "retired"  # not in active/disabled/obsolete
        data = _minimal_registry(r)
        errors = registry.validate(data)
        self.assertTrue(
            any(".status" in e and "retired" in e for e in errors), errors
        )

    def test_validate_rejects_invalid_severity(self):
        r = _minimal_record()
        r["severity"] = "P0"  # old enum — no longer valid
        data = _minimal_registry(r)
        errors = registry.validate(data)
        self.assertTrue(any("severity" in e for e in errors), errors)

    def test_validate_accepts_all_severity_values(self):
        for sev in ("BLOCKING", "TROMPEUR", "COSMETIQUE", "INFO"):
            r = _minimal_record()
            r["severity"] = sev
            data = _minimal_registry(r)
            errors = registry.validate(data)
            self.assertEqual(errors, [], f"severity={sev}: {errors}")

    def test_validate_rejects_missing_patch_sha256(self):
        r = _minimal_record()
        del r["patch_sha256"]
        data = _minimal_registry(r)
        errors = registry.validate(data)
        self.assertTrue(
            any("'patch_sha256'" in e for e in errors), errors
        )

    def test_validate_rejects_invalid_sha_format_too_short(self):
        r = _minimal_record()
        r["patch_sha256"] = "abc123"  # far too short
        data = _minimal_registry(r)
        errors = registry.validate(data)
        self.assertTrue(
            any(".patch_sha256" in e for e in errors), errors
        )

    def test_validate_rejects_invalid_sha_format_non_hex(self):
        r = _minimal_record()
        r["patch_sha256"] = "z" * 64  # right length, wrong alphabet
        data = _minimal_registry(r)
        errors = registry.validate(data)
        self.assertTrue(
            any(".patch_sha256" in e for e in errors), errors
        )

    def test_validate_rejects_invalid_target_sha(self):
        r = _minimal_record()
        r["targets"][0]["baseline_sha256"] = "nothex"
        data = _minimal_registry(r)
        errors = registry.validate(data)
        self.assertTrue(
            any("baseline_sha256" in e for e in errors), errors
        )

    def test_validate_rejects_missing_target_field(self):
        r = _minimal_record()
        del r["targets"][0]["patched_sha256"]
        data = _minimal_registry(r)
        errors = registry.validate(data)
        self.assertTrue(
            any("'patched_sha256'" in e for e in errors), errors
        )

    def test_validate_rejects_duplicate_id(self):
        a = _minimal_record()
        b = copy.deepcopy(a)
        b["order"] = 2  # avoid colliding on order too
        data = _minimal_registry(a, b)
        errors = registry.validate(data)
        self.assertTrue(
            any("duplicate id" in e for e in errors), errors
        )

    def test_validate_rejects_duplicate_order(self):
        a = _minimal_record()
        b = copy.deepcopy(a)
        b["id"] = "b2-other"
        # same order = 1
        data = _minimal_registry(a, b)
        errors = registry.validate(data)
        self.assertTrue(
            any("duplicate order" in e for e in errors), errors
        )

    def test_validate_rejects_bad_schema_version(self):
        data = {"schema_version": 99, "records": []}
        errors = registry.validate(data)
        self.assertTrue(
            any("schema_version" in e for e in errors), errors
        )

    def test_validate_rejects_integer_schema_version(self):
        # Design cites "1" as a string, not int.
        data = {"schema_version": 1, "records": []}
        errors = registry.validate(data)
        self.assertTrue(
            any("schema_version" in e for e in errors), errors
        )

    def test_validate_rejects_non_list_records(self):
        data = {"schema_version": "1", "records": "not-a-list"}
        errors = registry.validate(data)
        self.assertTrue(any("records" in e for e in errors), errors)

    def test_validate_rejects_empty_targets(self):
        r = _minimal_record()
        r["targets"] = []
        data = _minimal_registry(r)
        errors = registry.validate(data)
        self.assertTrue(any("targets" in e for e in errors), errors)

    def test_validate_rejects_invalid_last_result(self):
        r = _minimal_record()
        r["last_result"] = "bogus-state"
        data = _minimal_registry(r)
        errors = registry.validate(data)
        self.assertTrue(
            any("last_result" in e for e in errors), errors
        )

    def test_validate_accepts_optional_last_result(self):
        r = _minimal_record()
        r["last_result"] = "patched"
        data = _minimal_registry(r)
        self.assertEqual(registry.validate(data), [])


if __name__ == "__main__":
    unittest.main()
