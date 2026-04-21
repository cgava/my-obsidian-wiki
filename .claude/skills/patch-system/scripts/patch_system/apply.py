"""Apply engine — ``git apply --index`` + fallback ``patch(1)`` + 3way.

See docs/260420-patch-system-design.md :

- §5.2 no auto-commit.
- §5.7 flock (handled by the bash dispatcher + ``cli.apply_all``).
- §3.2 last_applied / last_result persistence.
- §3.3 runtime.json strategies (``apply.method`` = ``git-apply`` | ``patch``).
- §4.1 flags : ``--dry-run``, ``--yes``, ``--interactive``, ``--force``,
  ``--auto-3way`` (§5.5).
- §4.2 interactive menu (letters y/n/s/d/3/r/q/?) — delegated to
  :mod:`patch_system.ui`.
- §4.3 canonical messages (``clean -> applying``, idempotent skip, dry-run,
  drift refusal under ``--yes``).
- §5.5 escalade upstream drift ; ``--auto-3way`` opt-in attempts
  ``git apply --3way --index`` before prompting.

Scope covered now (jalons 6 + 12 + 14) :

- Forward apply via ``git apply --index`` (default) **or** ``patch(1)``
  (when ``runtime.json`` sets ``apply.method == "patch"``).
- Idempotence : already-patched target is a no-op.
- Non-interactive arbitration : ``dirty`` / ``partial`` without
  ``--interactive`` or ``--force`` returns an error with §4.3 hint.
- ``--yes`` alone refuses ambiguous states with the §4.3 verbatim message.
- ``--interactive`` drives the §4.2 menu per-record.
- ``--force`` behaves as an implicit ``y`` on every ambiguous state.
- ``--auto-3way`` attempts ``git apply --3way --index`` on
  ``partial``/``dirty``. If 3way succeeds, commit the result and mark
  ``last_result=patched`` (a log line flags the provenance).
- ``--dry-run`` runs ``git apply --check`` (or ``patch --dry-run``) only.
- Persists ``last_applied`` (ISO UTC) + ``last_result`` on success.
"""

from __future__ import annotations

import datetime as _dt
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional

from patch_system import detect, registry, runtime as runtime_mod, ui as ui_mod


# -- Small helpers ------------------------------------------------------------


def _utc_now_iso() -> str:
    """ISO-8601 UTC Zulu (matches §3.2 ``last_applied`` example)."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_patch_path(record: dict[str, Any], patches_dir: Path) -> Path:
    return patches_dir / record.get("patch_file", "")


def _result(
    success: bool,
    from_state: str,
    to_state: str,
    message: str,
    **extra: Any,
) -> dict[str, Any]:
    """Canonical return dict (shared shape with rollback)."""
    out: dict[str, Any] = {
        "success": success,
        "from_state": from_state,
        "to_state": to_state,
        "message": message,
    }
    out.update(extra)
    return out


# -- Backend runners ----------------------------------------------------------


def _git_apply_index(
    patch_path: Path,
    vendor_root: Path,
    *,
    check_only: bool = False,
    reverse: bool = False,
    threeway: bool = False,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Single shell-out to ``git apply``. Args assembled per-call to keep
    the surface small and testable (callers just flip flags).
    """
    args = ["git", "apply"]
    if extra_args:
        args.extend(extra_args)
    else:
        args.append("--index")
    if reverse:
        args.append("--reverse")
    if threeway:
        args.append("--3way")
    if check_only:
        args.append("--check")
    args.append(str(patch_path))
    return subprocess.run(
        args, cwd=str(vendor_root),
        capture_output=True, text=True, check=False,
    )


def _patch_tool_available() -> bool:
    return shutil.which("patch") is not None


def _run_patch_tool(
    patch_path: Path,
    vendor_root: Path,
    *,
    args: list[str],
    dry_run: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Shell out to ``patch(1)`` reading the diff from stdin.

    ``patch`` exit codes (GNU) :

    - 0 : all hunks applied cleanly.
    - 1 : some hunks rejected (``.rej`` left in working tree).
    - 2 : fatal error (bad args, I/O).
    """
    cmd = ["patch"] + list(args)
    if dry_run:
        cmd.append("--dry-run")
    diff_text = patch_path.read_text(encoding="utf-8")
    return subprocess.run(
        cmd, cwd=str(vendor_root), input=diff_text,
        capture_output=True, text=True, check=False,
    )


# -- Post-apply persistence ---------------------------------------------------


def _persist_after_apply(
    rid: str,
    final_state: str,
    registry_path: Optional[Path],
    all_records: Optional[dict[str, Any]],
) -> str:
    """Write ``last_applied`` + ``last_result`` on a record in ``all_records``
    and save the registry. Returns the ISO timestamp stored (or
    ``(unset)`` if nothing was persisted).
    """
    if registry_path is None or all_records is None:
        return "(unset)"
    ts = _utc_now_iso()
    for r in all_records.get("records", []):
        if r.get("id") == rid:
            r["last_applied"] = ts
            r["last_result"] = final_state
            break
    registry.save(registry_path, all_records)
    return ts


# -- Interactive arbitration (§4.2) -------------------------------------------


def _interactive_arbitrate(
    record: dict[str, Any],
    probe: dict[str, Any],
    patch_path: Path,
    vendor_root: Path,
    patches_dir: Path,
    *,
    stream,
    prompt_fn: Optional[Callable[[str], str]],
) -> tuple[bool, str, bool]:
    """Drive the §4.2 menu over each target until a resolution is reached.

    Returns ``(apply_ok, message, quit_flag)`` :

    - ``apply_ok`` = True  → proceed with real ``git apply`` (caller then
      materialises the write).
    - ``apply_ok`` = False → don't apply ; record stays dirty/partial.
    - ``quit_flag`` = True → caller should break its iteration (``q``).

    The menu supports the full 8-letter set ; non-mutating choices (``s``,
    ``d``, ``?``) loop back to the prompt. ``3`` attempts
    ``git apply --3way --index`` immediately. ``r`` defers to the
    ``refresh`` command (we don't mutate from here to keep concerns split).
    """
    rid = record.get("id", "<unknown>")
    per_target = probe.get("per_target", []) or []
    # Pick the first ambiguous target as the anchor for the header (the
    # menu is whole-record ; §4.2 line 330's "target X" addresses the
    # operator at that level).
    ambiguous = [
        pt for pt in per_target if pt.get("state") in ("partial", "dirty")
    ]
    target_anchor = ambiguous[0] if ambiguous else (
        per_target[0] if per_target else {"path": "(no targets)"}
    )
    observed_state = probe.get("state", "dirty")

    while True:
        choice = ui_mod.prompt_target_choice(
            record, target_anchor, observed_state,
            stream=stream, prompt_fn=prompt_fn,
        )
        if choice is ui_mod.Choice.APPLY:
            return True, f"[{rid}] user chose APPLY (force)", False
        if choice is ui_mod.Choice.SKIP:
            return (
                False,
                f"[{rid}] {observed_state} -> skipped by user (status remains {observed_state})",
                False,
            )
        if choice is ui_mod.Choice.QUIT:
            return (
                False,
                f"[{rid}] {observed_state} -> run aborted by user (q). Applied patches are kept.",
                True,
            )
        if choice is ui_mod.Choice.SHOW:
            stream.write(f"[{rid}] (s) 3-point diff not yet implemented — showing patch file:\n")
            stream.write(patch_path.read_text(encoding="utf-8"))
            stream.write("\n")
            continue
        if choice is ui_mod.Choice.DIFF:
            stream.write(f"[{rid}] (d) diff patch -> local ; showing patch content:\n")
            stream.write(patch_path.read_text(encoding="utf-8"))
            stream.write("\n")
            continue
        if choice is ui_mod.Choice.THREEWAY:
            res = _git_apply_index(
                patch_path, vendor_root, threeway=True, check_only=False,
            )
            if res.returncode == 0:
                return True, f"[{rid}] 3-way merge succeeded (applied from 3way)", False
            stream.write(
                f"[{rid}] 3-way merge failed:\n  {res.stderr.strip()}\n"
            )
            continue
        if choice is ui_mod.Choice.REFRESH:
            stream.write(
                f"[{rid}] (r) refresh must be run via "
                f"`patch-system refresh {rid}` ; leaving state unchanged.\n"
            )
            continue
        # HELP is already consumed inside ui.prompt_target_choice's loop.
        stream.write(f"[{rid}] unexpected choice: {choice}\n")
        return False, f"[{rid}] arbitration aborted (unexpected)", False


# -- Public API ---------------------------------------------------------------


def apply_patch(
    record: dict[str, Any],
    vendor_root: Path,
    patches_dir: Path,
    *,
    dry_run: bool = False,
    yes: bool = False,
    interactive: bool = False,
    force: bool = False,
    auto_3way: bool = False,
    registry_path: Path | None = None,
    all_records: dict[str, Any] | None = None,
    stream=None,
    prompt_fn: Optional[Callable[[str], str]] = None,
    runtime: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Apply ``record.patch_file`` to ``vendor_root``.

    Parameters
    ----------
    record
        Patch record from series.json. Needs ``patch_file`` + ``targets[]``.
    vendor_root
        Git working tree the patch applies against.
    patches_dir
        Directory containing ``.patch`` + ``runtime.json``.
    dry_run
        Simulate only. ``git apply --check`` (or ``patch --dry-run``).
    yes
        Non-interactive mode. Ambiguous state → §4.3 refusal message.
    interactive
        Force the §4.2 menu even on clean state (§4.1 line 318 verbatim).
    force
        Implicit ``y`` on every ambiguous state (§4.1 line 304). Bypasses
        the menu entirely.
    auto_3way
        §5.5 opt-in. If initial state is ``partial`` or ``dirty``, try
        ``git apply --3way --index`` before prompting / refusing. On
        success, continue as a normal apply ; on failure, fall through
        to the regular interactive / ``--yes`` logic.
    registry_path, all_records
        Both required together to persist ``last_applied`` / ``last_result``.
        ``None`` → no persistence (test convenience).
    stream
        Output stream for interactive messages (default: ``sys.stdout``).
    prompt_fn
        :func:`input`-like callable for the §4.2 menu ; tests inject here.
    runtime
        Pre-loaded ``runtime.json`` dict (see :mod:`patch_system.runtime`).
        If ``None``, it is loaded lazily from ``patches_dir``.

    Returns
    -------
    dict
        Canonical shape: ``{"success", "from_state", "to_state", "message",
        ...}``.  ``quit`` flag (bool) is set when the user pressed ``q``
        in the menu so callers (``apply --all``) can stop iteration.
    """
    import sys as _sys

    if stream is None:
        stream = _sys.stdout

    rid = record.get("id", "<unknown>")
    patch_path = _resolve_patch_path(record, patches_dir)

    # Validate mutually exclusive flags (design §4.1 line 317).
    if yes and interactive:
        return _result(
            False, "unknown", "unknown",
            f"[{rid}] invalid flags: --yes and --interactive are mutually exclusive.",
        )

    if not patch_path.exists():
        return _result(
            False, "unknown", "unknown",
            f"[{rid}] patch file not found: {patch_path} — cannot apply.",
        )

    # Resolve runtime strategy (§3.3).
    if runtime is None:
        runtime = runtime_mod.load_runtime(patches_dir)
    strategy = runtime_mod.resolve_strategy(rid, runtime)
    apply_section = strategy.get("apply", {}) or {}
    method = apply_section.get("method", "git-apply")
    method_args = list(apply_section.get("args", []) or [])

    # Initial state probe (composite).
    probe = detect.evaluate(record, vendor_root, patches_dir)
    initial_state = probe["state"]

    # Idempotence (§4.3).
    if initial_state == "patched":
        return _result(
            True, "patched", "patched",
            f"[{rid}] patched -> skip (already applied)",
            noop=True,
        )

    # Dry-run shortcut — honor runtime method.
    if dry_run:
        if method == "patch":
            if not _patch_tool_available():
                return _result(
                    False, initial_state, initial_state,
                    f"[{rid}] patch(1) not available, fallback impossible",
                    dry_run=True,
                )
            res = _run_patch_tool(
                patch_path, vendor_root, args=method_args, dry_run=True,
            )
            ok = (res.returncode == 0)
            msg = (
                f"[{rid}] {initial_state} -> would apply {patch_path.name} "
                f"via patch(1)\n"
                f"  [dry-run] patch {' '.join(method_args)} --dry-run  "
                f"{'OK' if ok else 'FAILED'}\n"
            )
            if not ok:
                msg += f"  stderr: {res.stderr.strip()}\n"
            return _result(
                ok, initial_state, initial_state, msg.rstrip(),
                dry_run=True,
            )
        # Default: git apply --check --index.
        chk = _git_apply_index(
            patch_path, vendor_root, check_only=True, extra_args=method_args,
        )
        if chk.returncode == 0:
            return _result(
                True, initial_state, initial_state,
                (
                    f"[{rid}] {initial_state} -> would apply {patch_path.name}\n"
                    f"  [dry-run] git apply --check --index {patch_path.name}  OK\n"
                    f"  [dry-run] no write performed"
                ),
                dry_run=True,
            )
        return _result(
            False, initial_state, initial_state,
            (
                f"[{rid}] {initial_state} -> dry-run git apply --check FAILED\n"
                f"  {chk.stderr.strip()}"
            ),
            dry_run=True,
        )

    # Non-dry-run. Absent → cannot apply (§4.3 shape).
    if initial_state == "absent":
        missing = [
            t["path"] for t in probe["per_target"] if t["state"] == "absent"
        ]
        return _result(
            False, "absent", "absent",
            (
                f"[{rid}] one or more target files are absent — cannot apply. "
                f"Targets missing : {missing}"
            ),
        )

    # Ambiguous state handling : partial / dirty.
    quit_flag = False
    provenance_note = ""
    if initial_state in ("dirty", "partial"):
        # --force : implicit 'y' — bypass menu entirely.
        # --auto-3way : try 3-way first ; if it succeeds the state is now
        # patched after our shell-out, so skip the normal forward apply.
        if auto_3way and not force:
            res3 = _git_apply_index(
                patch_path, vendor_root, threeway=True, check_only=False,
            )
            if res3.returncode == 0:
                provenance_note = " (applied from 3way merge)"
                final_state = detect.evaluate(
                    record, vendor_root, patches_dir,
                )["state"]
                ts = _persist_after_apply(
                    rid, final_state, registry_path, all_records,
                )
                return _result(
                    True, initial_state, final_state,
                    (
                        f"[{rid}] {initial_state} -> applying via 3way...\n"
                        f"  WARNING: applied from 3way merge (not pristine) — "
                        f"please review the result.\n"
                        f"  target(s) patched -> state={final_state}\n"
                        f"  registry updated: last_result={final_state} "
                        f"last_applied={ts}"
                    ),
                )
            stream.write(
                f"[{rid}] auto-3way failed:\n  {res3.stderr.strip()}\n"
            )
            # Fall through to normal ambiguous handling.

        if force:
            # Explicit operator override — proceed with forward apply.
            pass
        elif interactive:
            apply_ok, msg, quit_flag = _interactive_arbitrate(
                record, probe, patch_path, vendor_root, patches_dir,
                stream=stream, prompt_fn=prompt_fn,
            )
            if not apply_ok:
                return _result(
                    False, initial_state, initial_state, msg, quit=quit_flag,
                )
            # user chose y or 3way ; if it was 3way the tree is already
            # mutated — re-probe and persist as success.
            probe_post = detect.evaluate(record, vendor_root, patches_dir)
            if probe_post["state"] == "patched":
                ts = _persist_after_apply(
                    rid, "patched", registry_path, all_records,
                )
                return _result(
                    True, initial_state, "patched",
                    (
                        f"[{rid}] {initial_state} -> applied via interactive "
                        f"arbitration\n"
                        f"  {msg}\n"
                        f"  registry updated: last_result=patched "
                        f"last_applied={ts}"
                    ),
                )
            # Else fall through to forward apply (user said 'y').
        elif yes:
            return _result(
                False, initial_state, initial_state,
                ui_mod.yes_refusal_message(rid, initial_state),
            )
        else:
            return _result(
                False, initial_state, initial_state,
                (
                    f"[{rid}] {initial_state} -> arbitration required.\n"
                    f"  Rerun with --interactive to resolve, "
                    f"--auto-3way to merge automatically, or --force to overwrite."
                ),
            )

    # Now perform the actual forward apply (state is clean, or operator
    # chose 'y'/force on ambiguous).
    if method == "patch":
        if not _patch_tool_available():
            return _result(
                False, initial_state, initial_state,
                f"[{rid}] patch(1) not available, fallback impossible",
            )
        res = _run_patch_tool(
            patch_path, vendor_root, args=method_args, dry_run=False,
        )
        if res.returncode == 2:
            return _result(
                False, initial_state, initial_state,
                (
                    f"[{rid}] {initial_state} -> patch(1) fatal error\n"
                    f"  {res.stderr.strip()}"
                ),
            )
        if res.returncode == 1:
            # Rejects were left as .rej.
            return _result(
                False, initial_state, "dirty",
                (
                    f"[{rid}] {initial_state} -> patch(1) applied with rejects\n"
                    f"  stdout: {res.stdout.strip()}\n"
                    f"  check .rej files in {vendor_root}"
                ),
            )
        # rc == 0
    else:
        res = _git_apply_index(
            patch_path, vendor_root, check_only=False, extra_args=method_args,
        )
        if res.returncode != 0:
            return _result(
                False, initial_state, initial_state,
                (
                    f"[{rid}] {initial_state} -> git apply FAILED\n"
                    f"  {res.stderr.strip()}"
                ),
            )

    post_probe = detect.evaluate(record, vendor_root, patches_dir)
    final_state = post_probe["state"]
    ts = _persist_after_apply(rid, final_state, registry_path, all_records)

    return _result(
        True, initial_state, final_state,
        (
            f"[{rid}] {initial_state} -> applying{provenance_note}...\n"
            f"  target(s) patched -> state={final_state}\n"
            f"  registry updated: last_result={final_state} "
            f"last_applied={ts}"
        ),
    )
