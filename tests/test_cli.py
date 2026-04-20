"""Tests for patch_system.cli — invoked via `python3 -m patch_system`.

Each test invokes the CLI as a subprocess so the full argparse + main()
pipeline is exercised, including env-var-based path resolution. The
project root for each invocation is a throwaway tempdir shaped like:

    tmp/
      patches/
        series.json
        0001-readme-add-section.patch  ← copied from fixtures
        ...
      vendor/obsidian-wiki/  ← copy of vendor-mini/ (for status commands)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_VENDOR_PRISTINE = _FIXTURES / "vendor-mini"
_PATCHES_FIX = _FIXTURES / "patches"
_SERIES_FIX = _FIXTURES / "series.json"


def _make_project_root() -> Path:
    """Assemble a throwaway PATCH_SYSTEM_ROOT with patches/ + vendor/."""
    root = Path(tempfile.mkdtemp(prefix="patch-system-cli-"))
    # patches/
    patches = root / "patches"
    patches.mkdir()
    shutil.copy2(_SERIES_FIX, patches / "series.json")
    for p in _PATCHES_FIX.glob("*.patch"):
        shutil.copy2(p, patches / p.name)
    # vendor/obsidian-wiki/
    vendor_parent = root / "vendor"
    vendor_parent.mkdir()
    shutil.copytree(_VENDOR_PRISTINE, vendor_parent / "obsidian-wiki")
    return root


def _run_cli(
    argv: list[str], root: Path, env_extra: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATCH_SYSTEM_ROOT"] = str(root)
    env["PYTHONPATH"] = str(_SCRIPTS_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "patch_system", *argv],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


class CLITestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = _make_project_root()

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


class TestListCmd(CLITestBase):
    def test_list_json_output_is_valid_json(self):
        res = _run_cli(["list", "--json"], self.root)
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        self.assertIn("records", payload)
        self.assertEqual(len(payload["records"]), 4)
        ids = {r["id"] for r in payload["records"]}
        self.assertEqual(
            ids,
            {
                "t0001-readme-add-section",
                "t0002-cmd1-fix-typo",
                "t0003-cmd2-drifted",
                "t0004-cmd2-semantic-drift",
            },
        )

    def test_list_filter_by_status_lifecycle(self):
        # All fixture records are `active`, so --status=disabled returns [].
        res = _run_cli(["list", "--json", "--status", "disabled"], self.root)
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["records"], [])

        res = _run_cli(["list", "--json", "--status", "active"], self.root)
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        self.assertEqual(len(payload["records"]), 4)


class TestStatusCmd(CLITestBase):
    def test_status_table_format_columns(self):
        res = _run_cli(["status"], self.root)
        self.assertEqual(res.returncode, 0, res.stderr)
        lines = res.stdout.splitlines()
        # First non-empty line is the header (§4.4).
        self.assertTrue(lines, res.stdout)
        header = lines[0]
        for col in ("ID", "SEV", "TARGETS", "STATE", "ORDER"):
            self.assertIn(col, header, header)
        # Each fixture record has its id somewhere in the table body.
        body = "\n".join(lines[1:])
        for rid in (
            "t0001-readme-add-section",
            "t0002-cmd1-fix-typo",
            "t0003-cmd2-drifted",
            "t0004-cmd2-semantic-drift",
        ):
            self.assertIn(rid, body)
        # A summary line exists and starts with "Summary:".
        self.assertTrue(
            any(l.startswith("Summary:") for l in lines),
            "missing Summary line: " + res.stdout,
        )

    def test_status_json_summary_block(self):
        res = _run_cli(["status", "--json"], self.root)
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        self.assertIn("summary", payload)
        self.assertIn("records", payload)
        self.assertIn("vendor_baseline", payload)
        # Summary must count by state for the live probe.
        summary = payload["summary"]
        self.assertIn("active", summary)
        # sum of state counts should be <= total records
        states_sum = sum(
            summary.get(st, 0)
            for st in ("clean", "patched", "dirty", "partial", "absent", "unknown")
        )
        self.assertLessEqual(states_sum, 4)

    def test_status_only_failing_filter(self):
        res = _run_cli(["status", "--json", "--only-failing"], self.root)
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        # Every returned record must have state ∈ {dirty, partial, absent}.
        for r in payload["records"]:
            self.assertIn(r["state"], ("dirty", "partial", "absent"), r)

    def test_status_id_filter(self):
        res = _run_cli(
            ["status", "--json", "--id", "t0001-readme-add-section"], self.root
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        self.assertEqual(len(payload["records"]), 1)
        self.assertEqual(payload["records"][0]["id"], "t0001-readme-add-section")


class TestDescribeCmd(CLITestBase):
    def test_describe_shows_all_fields(self):
        res = _run_cli(["describe", "t0001-readme-add-section"], self.root)
        self.assertEqual(res.returncode, 0, res.stderr)
        out = res.stdout
        for field in (
            "id", "order", "status", "severity", "title",
            "patch_file", "patch_sha256", "targets",
            "current state", "can_auto_3way",
        ):
            self.assertIn(field, out, f"missing {field!r} in describe output:\n{out}")
        # The target path appears too.
        self.assertIn("vendor/obsidian-wiki/README.md", out)

    def test_describe_json_output(self):
        res = _run_cli(
            ["describe", "t0001-readme-add-section", "--json"], self.root
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        for key in ("record", "state", "per_target", "history", "can_auto_3way"):
            self.assertIn(key, payload)
        self.assertEqual(payload["record"]["id"], "t0001-readme-add-section")

    def test_describe_unknown_id_returns_1(self):
        res = _run_cli(["describe", "bogus"], self.root)
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)


class TestDiffCmd(CLITestBase):
    def test_diff_outputs_patch_content(self):
        res = _run_cli(["diff", "t0001-readme-add-section"], self.root)
        self.assertEqual(res.returncode, 0, res.stderr)
        # The DEP-3 header + hunk should appear.
        self.assertIn("--- a/README.md", res.stdout)
        self.assertIn("+++ b/README.md", res.stdout)
        self.assertIn("Local notes", res.stdout)

    def test_diff_no_color_flag(self):
        res = _run_cli(
            ["diff", "t0001-readme-add-section", "--no-color"], self.root
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        # No ANSI escape sequences with --no-color.
        self.assertNotIn("\x1b[", res.stdout)

    def test_diff_targets_only_parses_patch(self):
        res = _run_cli(
            ["diff", "t0003-cmd2-drifted", "--targets-only"], self.root
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        # Should print just the target path, nothing else.
        lines = [l for l in res.stdout.splitlines() if l.strip()]
        self.assertEqual(lines, ["bin/cmd2.sh"])


class TestVerifyStub(CLITestBase):
    def test_verify_nonempty_registry_returns_1(self):
        # Non-empty fixture registry : stub returns exit 1 (note #5).
        res = _run_cli(["verify"], self.root)
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("not yet implemented", res.stderr)

    def test_verify_empty_registry_returns_0(self):
        # Replace series.json with an empty registry.
        (self.root / "patches" / "series.json").write_text(
            json.dumps({"schema_version": "1", "records": []}),
            encoding="utf-8",
        )
        res = _run_cli(["verify"], self.root)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("empty", res.stderr)


class TestTopLevelSeriesFlag(CLITestBase):
    """REV-0004 note #1 : --series is top-level, not per-subcommand."""

    def test_series_flag_works_before_subcommand(self):
        # Point --series at a different file outside root/patches/.
        alt = self.root / "alt-series.json"
        alt.write_text(
            json.dumps({"schema_version": "1", "records": []}),
            encoding="utf-8",
        )
        res = _run_cli(
            ["--series", str(alt), "list", "--json"], self.root
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["records"], [])


if __name__ == "__main__":
    unittest.main()
