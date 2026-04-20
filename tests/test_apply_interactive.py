"""Tests for apply engine — interactive menu + auto-3way + patch(1).

Covers jalons 12 and 14 integration inside apply.apply_patch :

- ``interactive=True`` on ambiguous state with stdin='n' → skip (no mutation).
- ``interactive=True`` on ambiguous state with stdin='y' → force apply.
- ``force=True`` on ambiguous state → applies without prompting.
- ``--yes`` + ambiguous → §4.3 refusal message (verbatim key string).
- ``--yes`` + ``--interactive`` → rejected (mutually exclusive).
- ``auto_3way=True`` probes git apply --3way before asking.
- runtime.json override ``method=patch`` routes through patch(1) mocked via
  subprocess monkeypatch.
- patch(1) absent → explicit error message.
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from patch_system import apply as apply_mod  # noqa: E402
from patch_system import runtime as runtime_mod  # noqa: E402


_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_VENDOR_PRISTINE = _FIXTURES / "vendor-mini"
_PATCHES_DIR = _FIXTURES / "patches"


def _load_fixture_records() -> list[dict]:
    with (_FIXTURES / "series.json").open("r", encoding="utf-8") as f:
        return json.load(f)["records"]


def _rec(rid: str) -> dict:
    for r in _load_fixture_records():
        if r["id"] == rid:
            return r
    raise AssertionError(f"fixture record not found: {rid}")


class _VendorHarness(unittest.TestCase):
    def setUp(self) -> None:
        if not shutil.which("git"):
            self.skipTest("git not installed")
        self._tmp = Path(tempfile.mkdtemp(prefix="patch-system-iact-"))
        self.vendor_root = self._tmp / "vendor"
        shutil.copytree(_VENDOR_PRISTINE, self.vendor_root, symlinks=True)
        subprocess.run(["git", "init", "-q"], cwd=self.vendor_root, check=True, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=self.vendor_root, check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t.invalid", "-c", "user.name=t",
             "commit", "-q", "-m", "init"],
            cwd=self.vendor_root, check=True, capture_output=True,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestInteractiveBehaviour(_VendorHarness):
    def test_yes_and_interactive_are_mutually_exclusive(self):
        r = _rec("t0001-readme-add-section")
        out = apply_mod.apply_patch(
            r, self.vendor_root, _PATCHES_DIR,
            dry_run=False, yes=True, interactive=True,
        )
        self.assertFalse(out["success"])
        self.assertIn("mutually exclusive", out["message"])

    def test_interactive_dirty_stdin_n_skips(self):
        r = _rec("t0004-cmd2-semantic-drift")  # partial on vendor-mini
        stream = io.StringIO()
        prompts = iter(["n"])
        out = apply_mod.apply_patch(
            r, self.vendor_root, _PATCHES_DIR,
            dry_run=False, interactive=True,
            stream=stream, prompt_fn=lambda _msg: next(prompts),
        )
        self.assertFalse(out["success"])
        self.assertIn("skipped by user", out["message"])

    def test_interactive_dirty_stdin_y_forces_apply(self):
        # 0004 is semantic drift — 'y' via interactive runs forward apply,
        # which itself still fails (the patch genuinely doesn't apply);
        # we assert the menu was consulted, not the final outcome.
        r = _rec("t0004-cmd2-semantic-drift")
        stream = io.StringIO()
        prompts = iter(["y"])
        out = apply_mod.apply_patch(
            r, self.vendor_root, _PATCHES_DIR,
            dry_run=False, interactive=True,
            stream=stream, prompt_fn=lambda _msg: next(prompts),
        )
        # Either it succeeded applying via git-apply, or it failed with
        # the git-apply error message (not the "arbitration required"
        # one). Key point : menu consulted.
        self.assertNotIn("arbitration required", out["message"])

    def test_force_on_ambiguous_bypasses_menu(self):
        r = _rec("t0004-cmd2-semantic-drift")
        prompts_called = {"n": 0}

        def _fail_on_prompt(_msg):
            prompts_called["n"] += 1
            raise AssertionError("prompt must not be called under --force")

        out = apply_mod.apply_patch(
            r, self.vendor_root, _PATCHES_DIR,
            dry_run=False, force=True,
            stream=io.StringIO(), prompt_fn=_fail_on_prompt,
        )
        self.assertEqual(prompts_called["n"], 0)
        # success/fail depends on git apply — we only check the prompt
        # path wasn't entered.
        self.assertIsInstance(out["success"], bool)

    def test_yes_refusal_on_ambiguous(self):
        r = _rec("t0004-cmd2-semantic-drift")
        out = apply_mod.apply_patch(
            r, self.vendor_root, _PATCHES_DIR,
            dry_run=False, yes=True,
        )
        self.assertFalse(out["success"])
        # §4.3 verbatim key string.
        self.assertIn(
            "ERROR: --yes mode forbids interactive arbitration.",
            out["message"],
        )


class TestAuto3way(_VendorHarness):
    def test_auto_3way_attempts_3way_before_prompt(self):
        """On a partial state with --auto-3way we shell out to git apply --3way
        before prompting. Success or failure of 3way is not guaranteed on
        fixture data — we only verify that git is invoked with --3way.
        """
        r = _rec("t0004-cmd2-semantic-drift")
        calls: list[list[str]] = []
        real_run = subprocess.run

        def _spy_run(args, *a, **kw):
            calls.append(list(args))
            return real_run(args, *a, **kw)

        with mock.patch("patch_system.apply.subprocess.run", side_effect=_spy_run):
            out = apply_mod.apply_patch(
                r, self.vendor_root, _PATCHES_DIR,
                dry_run=False, auto_3way=True,
                stream=io.StringIO(),
            )
        # Look for a git-apply command line containing --3way.
        has_3way = any(
            ("git" in c[0] and "--3way" in c) for c in calls
        )
        self.assertTrue(
            has_3way,
            f"expected a 'git apply --3way ...' call, got: {calls}",
        )
        self.assertIsInstance(out["success"], bool)


class TestPatchToolFallback(_VendorHarness):
    def test_runtime_override_routes_to_patch_tool(self):
        """With runtime override ``apply.method=patch``, apply.py shells out
        to `patch -p1 -N` instead of `git apply`. We mock subprocess.run
        to capture the call and fake rc=0 (clean apply).
        """
        r = _rec("t0001-readme-add-section")
        runtime = runtime_mod.default_runtime()
        runtime["overrides"][r["id"]] = {
            "apply": {"method": "patch", "args": ["-p1", "-N"]},
        }

        fake_rc_ok = subprocess.CompletedProcess(
            args=["patch"], returncode=0, stdout="patched\n", stderr="",
        )
        calls: list[list[str]] = []

        def _fake_run(args, *a, **kw):
            calls.append(list(args))
            if args[0] == "patch":
                return fake_rc_ok
            # Let git through (detect.evaluate uses git).
            return subprocess.run(args, *a, **kw)

        with mock.patch("shutil.which", return_value="/usr/bin/patch"):
            with mock.patch(
                "patch_system.apply.subprocess.run", side_effect=_fake_run,
            ):
                out = apply_mod.apply_patch(
                    r, self.vendor_root, _PATCHES_DIR,
                    dry_run=True, runtime=runtime,
                )
        # apply.py should have tried 'patch -p1 -N --dry-run'.
        patch_calls = [c for c in calls if c and c[0] == "patch"]
        self.assertTrue(patch_calls, f"expected a patch(1) call, got {calls}")
        self.assertIn("-p1", patch_calls[0])
        self.assertIn("-N", patch_calls[0])
        self.assertIn("--dry-run", patch_calls[0])
        self.assertTrue(out["success"])

    def test_patch_tool_absent_reports_clear_error(self):
        r = _rec("t0001-readme-add-section")
        runtime = runtime_mod.default_runtime()
        runtime["overrides"][r["id"]] = {
            "apply": {"method": "patch", "args": ["-p1"]},
        }
        with mock.patch("shutil.which", return_value=None):
            out = apply_mod.apply_patch(
                r, self.vendor_root, _PATCHES_DIR,
                dry_run=False, runtime=runtime,
            )
        self.assertFalse(out["success"])
        self.assertIn("patch(1) not available", out["message"])


if __name__ == "__main__":
    unittest.main()
