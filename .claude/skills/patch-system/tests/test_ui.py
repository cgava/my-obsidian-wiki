"""Tests for patch_system.ui — §4.2 interactive menu (jalon 12).

Covers :

- 8 letters y / n / s / d / 3 / r / q / ? recognised.
- Default-on-empty → SKIP (§4.2 line 342 verbatim).
- EOF (non-TTY) → SKIP + notice.
- ? / unknown letter re-prints the menu.
- yes_refusal_message renders the §4.3 verbatim string.
"""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from patch_system import ui  # noqa: E402


def _record(order: int = 2, rid: str = "test-rec") -> dict:
    return {"id": rid, "order": order}


def _target(path: str = "vendor/x.md") -> dict:
    return {"path": path}


def _fake_prompt(seq):
    """Return a callable that pops one answer per call from seq, then EOF."""
    it = iter(seq)

    def _inner(_msg):
        try:
            return next(it)
        except StopIteration:
            raise EOFError
    return _inner


class TestMenuFormatting(unittest.TestCase):
    def test_header_uses_order_and_path(self):
        header = ui.format_menu_header(2, "vendor/foo.md", "partial")
        # §4.2 line 330 shape.
        self.assertEqual(
            header,
            "Patch 0002 target vendor/foo.md is partial.",
        )

    def test_menu_body_contains_all_8_letters(self):
        text = ui.format_menu(1, "x", "dirty")
        for letter_label in ("y  apply", "n  skip", "s  show", "d  diff",
                             "3  3way", "r  refresh", "q  quit", "?  help"):
            self.assertIn(letter_label, text)
        self.assertIn("Choice [y/n/s/d/3/r/q/?] (default n):", text)

    def test_yes_refusal_message_verbatim(self):
        msg = ui.yes_refusal_message("b1", "partial")
        # §4.3 lines 370-374 verbatim key strings.
        self.assertIn("[b1] partial -> ambiguous state.", msg)
        self.assertIn(
            "ERROR: --yes mode forbids interactive arbitration.", msg,
        )
        self.assertIn(
            "Rerun with --interactive to resolve, or --force to overwrite.",
            msg,
        )


class TestPromptChoice(unittest.TestCase):
    def test_letter_y_returns_apply(self):
        out = io.StringIO()
        choice = ui.prompt_target_choice(
            _record(), _target(), "partial",
            stream=out, prompt_fn=_fake_prompt(["y"]),
        )
        self.assertIs(choice, ui.Choice.APPLY)

    def test_letter_n_returns_skip(self):
        out = io.StringIO()
        choice = ui.prompt_target_choice(
            _record(), _target(), "partial",
            stream=out, prompt_fn=_fake_prompt(["n"]),
        )
        self.assertIs(choice, ui.Choice.SKIP)

    def test_letter_q_returns_quit(self):
        out = io.StringIO()
        choice = ui.prompt_target_choice(
            _record(), _target(), "dirty",
            stream=out, prompt_fn=_fake_prompt(["q"]),
        )
        self.assertIs(choice, ui.Choice.QUIT)

    def test_letter_3_returns_threeway(self):
        choice = ui.prompt_target_choice(
            _record(), _target(), "partial",
            stream=io.StringIO(), prompt_fn=_fake_prompt(["3"]),
        )
        self.assertIs(choice, ui.Choice.THREEWAY)

    def test_letter_r_returns_refresh(self):
        choice = ui.prompt_target_choice(
            _record(), _target(), "dirty",
            stream=io.StringIO(), prompt_fn=_fake_prompt(["r"]),
        )
        self.assertIs(choice, ui.Choice.REFRESH)

    def test_empty_input_is_skip(self):
        """§4.2 line 342 : default on empty = n (skip)."""
        choice = ui.prompt_target_choice(
            _record(), _target(), "dirty",
            stream=io.StringIO(), prompt_fn=_fake_prompt([""]),
        )
        self.assertIs(choice, ui.Choice.SKIP)

    def test_eof_on_stdin_is_skip_with_notice(self):
        out = io.StringIO()

        def _eof(_msg):
            raise EOFError
        choice = ui.prompt_target_choice(
            _record(), _target(), "dirty",
            stream=out, prompt_fn=_eof,
        )
        self.assertIs(choice, ui.Choice.SKIP)
        self.assertIn("stdin closed", out.getvalue())

    def test_question_mark_reprints_menu_then_accepts(self):
        out = io.StringIO()
        choice = ui.prompt_target_choice(
            _record(), _target(), "dirty",
            stream=out,
            prompt_fn=_fake_prompt(["?", "y"]),
        )
        self.assertIs(choice, ui.Choice.APPLY)
        # Menu header should appear at least twice (initial + ? reprint).
        self.assertGreaterEqual(out.getvalue().count("Choice [y/n/s/d/3/r/q/?]"), 2)

    def test_unknown_letter_reprompts(self):
        out = io.StringIO()
        choice = ui.prompt_target_choice(
            _record(), _target(), "dirty",
            stream=out,
            prompt_fn=_fake_prompt(["z", "n"]),
        )
        self.assertIs(choice, ui.Choice.SKIP)
        self.assertIn("unknown choice", out.getvalue())


if __name__ == "__main__":
    unittest.main()
