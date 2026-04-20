"""Interactive UI — etc-update-like arbitration menu (jalon 12).

Isolated and unit-testable. All stdin/stdout is injectable via callables
so tests can drive the menu without touching real TTY.

Design refs (verbatim where quoted) :

- §4.2 lines 322-346 — menu à 8 lettres ``y/n/s/d/3/r/q/?``, defaut vide
  = ``n`` (skip non-destructif). ``q`` = quit propre (pas ``abort`` :
  les décisions déjà persistées restent).
- §4.3 lignes 369-375 — message drift avec ``--yes`` (verbatim) :
  ``--yes mode forbids interactive arbitration.``
- §5.5 — escalade utilisateur par défaut ; ``--auto-3way`` opt-in.

The menu prompt is reproduced line-for-line from §4.2 lines 329-339,
modulo the literal record id (substituted at runtime).
"""

from __future__ import annotations

import sys
from enum import Enum
from typing import Any, Callable, Optional


class Choice(Enum):
    """User arbitration outcomes for a single target, per §4.2."""

    APPLY = "y"       # force l'application (ecrase les modifs locales)
    SKIP = "n"        # laisse la cible telle quelle (default on empty)
    SHOW = "s"        # affiche le diff 3-points (pristine | local | patched)
    DIFF = "d"        # affiche seulement le diff patch -> local
    THREEWAY = "3"    # tente `git apply --3way`
    REFRESH = "r"     # met a jour baseline_sha256 depuis l'etat courant
    QUIT = "q"        # arrete le run ; pas de rollback
    HELP = "?"        # re-affiche le menu


# -- Prompt text (§4.2 lines 329-339, verbatim) -------------------------------

_MENU_BODY = (
    "   y  apply — force l'application (ecrase les modifs locales si conflit)\n"
    "   n  skip  — laisse la cible telle quelle, status sera 'dirty'\n"
    "   s  show  — affiche le diff 3-points (pristine | local | patched)\n"
    "   d  diff  — affiche seulement le diff patch->local\n"
    "   3  3way  — tente `git apply --3way` (merge automatique)\n"
    "   r  refresh — met a jour baseline_sha256 depuis l'etat local courant\n"
    "   q  quit  — arrete le run, les patches deja traites restent appliques\n"
    "   ?  help  — re-affiche ce menu\n"
)

_PROMPT_TAIL = "Choice [y/n/s/d/3/r/q/?] (default n): "


def format_menu_header(order: int, target_path: str, observed_state: str) -> str:
    """Return the first line of the menu (§4.2 line 330, verbatim shape).

    Example rendered::

        Patch 0002 target vendor/obsidian-wiki/.skills/wiki-ingest/SKILL.md is partial.
    """
    return (
        f"Patch {order:04d} target {target_path} is {observed_state}."
    )


def format_menu(order: int, target_path: str, observed_state: str) -> str:
    """Assemble the full menu text (header + body + prompt tail)."""
    return (
        format_menu_header(order, target_path, observed_state)
        + "\n"
        + _MENU_BODY
        + _PROMPT_TAIL
    )


# -- Ambiguous-state message under --yes (§4.3 lines 369-375, verbatim) -------

_YES_REFUSAL_MSG_TMPL = (
    "[{rid}] {state} -> ambiguous state.\n"
    "  ERROR: --yes mode forbids interactive arbitration.\n"
    "  Rerun with --interactive to resolve, or --force to overwrite."
)


def yes_refusal_message(rid: str, state: str) -> str:
    """Return the canonical --yes refusal message (§4.3 verbatim)."""
    return _YES_REFUSAL_MSG_TMPL.format(rid=rid, state=state)


# -- Core prompt --------------------------------------------------------------

_VALID_LETTERS = {c.value for c in Choice}


def prompt_target_choice(
    record: dict[str, Any],
    target: dict[str, Any],
    observed_state: str,
    *,
    stream=None,
    prompt_fn: Optional[Callable[[str], str]] = None,
) -> Choice:
    """Display the §4.2 menu and return the user's :class:`Choice`.

    Parameters
    ----------
    record
        The patch record ; only ``id`` and ``order`` are consumed for the
        header.
    target
        The target dict ; ``path`` is consumed for the header.
    observed_state
        Composite state for this target (``partial``, ``dirty``, ``clean``,
        ``patched``, ``absent``).
    stream
        Output stream (defaults to ``sys.stdout``). The menu is written
        exactly once ; ``?`` re-prints it.
    prompt_fn
        Callable with ``input()`` signature. Defaults to :func:`input`.
        Tests inject a fake prompt to drive letters without a real TTY.

    Returns
    -------
    Choice
        Mapped from the first character of the user's answer (lower-cased).
        Empty answer → :attr:`Choice.SKIP` (§4.2 default rule).
        EOF (non-TTY, closed stdin) → :attr:`Choice.SKIP` with a notice.
        Unknown letter → re-prints the menu (same semantics as ``?``) and
        re-prompts. This loop has no hard cap, consistent with ``etc-update``.
    """
    if stream is None:
        stream = sys.stdout
    if prompt_fn is None:
        prompt_fn = input

    order = int(record.get("order", 0) or 0)
    path = str(target.get("path", "<unknown>"))

    menu_text = format_menu(order, path, observed_state)
    stream.write(menu_text)
    stream.flush()

    while True:
        try:
            raw = prompt_fn("")
        except EOFError:
            stream.write(
                "\n[ui] stdin closed (non-TTY) — defaulting to 'n' (skip).\n"
            )
            stream.flush()
            return Choice.SKIP

        letter = (raw or "").strip().lower()
        if letter == "":
            return Choice.SKIP  # §4.2 default-on-empty rule
        first = letter[0]
        if first not in _VALID_LETTERS:
            stream.write(f"unknown choice {first!r} — try one of y/n/s/d/3/r/q/?\n")
            stream.write(menu_text)
            stream.flush()
            continue
        if first == "?":
            # Re-affiche le menu (help).
            stream.write(menu_text)
            stream.flush()
            continue
        return Choice(first)
