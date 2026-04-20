"""State detection — sha256 v1 + composite (git apply --check) v2.

See docs/260420-patch-system-design.md §2.2 (Moteur detection), §3.2
(state enum), §5.5 (escalade drift).

Two entry points:

- ``detect_state(record, vendor_root) -> str`` : backward-compat wrapper
  returning only the aggregated state (clean/patched/dirty/partial/absent/
  unknown). sha256 only — used by test_detect baseline (v1).

- ``evaluate(record, vendor_root, patches_dir) -> dict`` : full composite
  detection (jalon 5). When sha256 aggregation returns ``dirty``, escalate
  to ``git apply --check`` (forward / reverse / 3way) to distinguish
  cosmetic drift from semantic conflict and detect partial-hunk scenarios.

Composite state rules (jalon 5) :

- sha-agg is ``clean``/``patched``/``absent`` → return as-is, no git call.
- sha-agg is ``partial`` → return as-is (sha-based mix is authoritative).
- sha-agg is ``dirty`` → call git:
    - ``git apply --check`` (forward) succeeds → clean + drift_hint="cosmetic"
      (the patch would still apply forward → the file is pre-patch with
      cosmetic drift on baseline; lifecycle = clean).
    - ``--reverse --check`` succeeds → patched + drift_hint="cosmetic"
      (the patch could still be reverted → the file is post-patch with
      cosmetic drift on patched; lifecycle = patched).
    - Both fail, per-hunk split shows some hunks applyable → partial
      + drift_hint="semantic".
    - All hunks fail → dirty + drift_hint="semantic".
- ``can_auto_3way`` is independent: ``git apply --3way --check`` on the
  super-repo. ``True`` only if 3way would succeed cleanly.

Algorithm v1 (sha256 per target) :
  sha256(file) == baseline_sha256 -> clean
  sha256(file) == patched_sha256  -> patched
  file absent                     -> absent
  otherwise                       -> dirty

Multi-target aggregation:
  any absent              -> absent
  any dirty               -> dirty
  mix of clean + patched  -> partial
  all clean               -> clean
  all patched             -> patched
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_target_path(target: dict[str, Any], vendor_root: Path) -> Path:
    """Resolve a target `path` under vendor_root (or absolute as-is).

    target paths in the registry use the form `vendor/obsidian-wiki/...`.
    The caller points `vendor_root` at that subtree, so we strip a leading
    `vendor/<name>/` segment when relative. Absolute paths pass through.
    """
    rel = target.get("path", "")
    candidate = Path(rel)
    if candidate.is_absolute():
        return candidate
    parts = candidate.parts
    if len(parts) >= 2 and parts[0] == "vendor":
        candidate = Path(*parts[2:])
    return vendor_root / candidate


def _per_target_state(
    target: dict[str, Any], record: dict[str, Any], vendor_root: Path
) -> tuple[str, str | None]:
    """Resolve (state, observed_sha) for a single target entry."""
    full = _resolve_target_path(target, vendor_root)
    if not full.exists():
        return "absent", None

    baseline = target.get("baseline_sha256") or record.get("baseline_sha256")
    patched = target.get("patched_sha256") or record.get("patched_sha256")

    observed = _sha256_of_file(full)
    if baseline and observed == baseline:
        return "clean", observed
    if patched and observed == patched:
        return "patched", observed
    return "dirty", observed


def _aggregate(states: list[str]) -> str:
    """Combine per-target states into a single record-level state."""
    if not states:
        return "unknown"
    if any(s == "absent" for s in states):
        return "absent"
    if any(s == "dirty" for s in states):
        return "dirty"
    if all(s == "clean" for s in states):
        return "clean"
    if all(s == "patched" for s in states):
        return "patched"
    # mix of clean + patched (no dirty/absent) -> partial
    return "partial"


def detect_state(record: dict[str, Any], vendor_root: Path) -> str:
    """sha256-only aggregated state (backward-compat for jalon 4 tests).

    Returns one of registry.VALID_STATES. Does not call git.
    """
    targets = record.get("targets") or []
    if not targets:
        return "unknown"
    per_target = [_per_target_state(t, record, vendor_root)[0] for t in targets]
    return _aggregate(per_target)


# -------------------------------------------------------------------------
# Composite detection (jalon 5) — git apply --check fallback.
# -------------------------------------------------------------------------


def _git_available() -> bool:
    return shutil.which("git") is not None


def _run_git_apply(
    args: list[str], cwd: Path, patch_path: Path, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Thin wrapper around `git apply <args> <patch_path>` in cwd.

    Captures stdout/stderr as text. Does not raise on non-zero exit.
    """
    cmd = ["git", "apply", *args, str(patch_path)]
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        stdin=subprocess.PIPE if stdin is not None else None,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


# A minimal hunk splitter: a hunk is a contiguous block that starts at
# `@@ ...` and runs until the next `@@` or EOF. The file headers (`---` /
# `+++`) are preserved for every synthetic mini-patch.
_HUNK_HEADER_RE = re.compile(r"^@@ .* @@", re.MULTILINE)


def _split_hunks(patch_body: str) -> list[str]:
    """Split a patch text into a list of single-hunk mini-patches.

    Preserves the `--- a/...` and `+++ b/...` file-header pair for each
    hunk. Returns an empty list if no hunks are found.

    Limitations: this splitter assumes one file per patch. Multi-file
    patches get their hunks grouped under the last seen file-header pair
    — good enough for fixture detection but should be revisited when
    real multi-file patches enter the suite.
    """
    # Find the body starting from the first `---` line.
    lines = patch_body.splitlines(keepends=True)
    # Locate the first `--- ` line; prior lines (DEP-3 header, `---`
    # separator) are discarded for splitting purposes.
    body_start = 0
    for i, ln in enumerate(lines):
        if ln.startswith("--- "):
            body_start = i
            break
    else:
        return []

    body_lines = lines[body_start:]
    # Track current file header pair.
    cur_minus: str | None = None
    cur_plus: str | None = None
    hunks: list[list[str]] = []
    i = 0
    while i < len(body_lines):
        ln = body_lines[i]
        if ln.startswith("--- "):
            cur_minus = ln
            if i + 1 < len(body_lines) and body_lines[i + 1].startswith("+++ "):
                cur_plus = body_lines[i + 1]
                i += 2
                continue
            i += 1
            continue
        if ln.startswith("@@ "):
            # Collect this hunk.
            hunk_lines = [ln]
            i += 1
            while i < len(body_lines) and not body_lines[i].startswith("@@ ") \
                    and not body_lines[i].startswith("--- "):
                hunk_lines.append(body_lines[i])
                i += 1
            if cur_minus and cur_plus:
                hunks.append([cur_minus, cur_plus, *hunk_lines])
            continue
        i += 1

    return ["".join(h) for h in hunks]


def _count_applyable_hunks(
    patch_path: Path, vendor_root: Path
) -> tuple[int, int]:
    """Return (n_applyable, n_total) via per-hunk split + `git apply --check`.

    Each synthetic mini-patch is fed on stdin to avoid cluttering disk.
    Requires a git tree at vendor_root — callers should pass the working
    tree. If vendor_root is not inside a git repo, we wrap it in a
    throwaway ephemeral repo so `git apply` has an index.
    """
    try:
        patch_text = patch_path.read_text(encoding="utf-8")
    except OSError:
        return 0, 0

    hunks = _split_hunks(patch_text)
    if not hunks:
        return 0, 0

    # Ensure we have a git repo at vendor_root for consistent `git apply`
    # semantics. If not, stage a copy under a tempdir.
    work_root, cleanup = _ensure_git_tree(vendor_root)
    try:
        applyable = 0
        for hunk in hunks:
            # Write mini-patch to a tempfile (stdin-input works but being
            # explicit simplifies error messages).
            with tempfile.NamedTemporaryFile(
                "w", suffix=".patch", delete=False, encoding="utf-8"
            ) as tf:
                tf.write(hunk)
                mini_path = Path(tf.name)
            try:
                res = _run_git_apply(["--check"], work_root, mini_path)
                if res.returncode == 0:
                    applyable += 1
            finally:
                mini_path.unlink(missing_ok=True)
        return applyable, len(hunks)
    finally:
        cleanup()


def _ensure_git_tree(vendor_root: Path):
    """Return (effective_root, cleanup_callable).

    If vendor_root is inside a git repo, return (vendor_root, noop).
    Otherwise copy it to a tempdir, `git init` + initial commit, return
    that tempdir + a cleanup callable that rmtrees it.
    """
    def _noop() -> None:
        pass

    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(vendor_root),
            capture_output=True,
            text=True,
            check=False,
        )
        toplevel = res.stdout.strip() if res.returncode == 0 else ""
        # Only reuse vendor_root's git repo if vendor_root IS the toplevel.
        # A submodule should satisfy this (its own .git/); a subdirectory
        # of an outer repo would report the outer repo's toplevel and its
        # HEAD index wouldn't necessarily match the current files → fall
        # through to the ephemeral-repo path for safety.
        if toplevel and Path(toplevel).resolve() == vendor_root.resolve():
            return vendor_root, _noop
    except (OSError, FileNotFoundError):
        pass

    tmp = Path(tempfile.mkdtemp(prefix="patch-system-detect-"))
    try:
        # Copy vendor_root into tmp preserving relative layout.
        shutil.copytree(vendor_root, tmp / "work", symlinks=True)
        work = tmp / "work"
        subprocess.run(
            ["git", "init", "-q"], cwd=str(work), check=False, capture_output=True
        )
        subprocess.run(
            ["git", "add", "-A"], cwd=str(work), check=False, capture_output=True
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=detect@patch-system.invalid",
                "-c",
                "user.name=detect",
                "commit",
                "-q",
                "-m",
                "snapshot",
                "--allow-empty",
            ],
            cwd=str(work),
            check=False,
            capture_output=True,
        )
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise

    def _cleanup() -> None:
        shutil.rmtree(tmp, ignore_errors=True)

    return work, _cleanup


def _composite_probe(
    patch_path: Path, vendor_root: Path
) -> tuple[str, str | None, bool]:
    """Given a dirty sha-agg, run git checks and return (state, hint, can_3way).

    state ∈ {"clean", "patched", "partial", "dirty"}
    hint  ∈ {"cosmetic", "semantic", None}
    can_3way : True iff `git apply --3way --check` succeeds.

    Forward `--check` success means the file is pre-patch with cosmetic
    drift → state="clean". Reverse `--check` success means the file is
    post-patch with cosmetic drift → state="patched". These are two
    distinct semantics and must not be conflated.
    """
    if not _git_available():
        return "dirty", None, False
    if not patch_path.exists():
        return "dirty", None, False

    work_root, cleanup = _ensure_git_tree(vendor_root)
    try:
        # Forward check : if `git apply --check` succeeds, the patch would
        # still apply — the file is in a *pre-patch* compatible state with
        # cosmetic drift on the baseline. Lifecycle state = `clean`.
        fwd = _run_git_apply(["--check"], work_root, patch_path)
        if fwd.returncode == 0:
            can_3way = _run_git_apply(
                ["--3way", "--check"], work_root, patch_path
            ).returncode == 0
            return "clean", "cosmetic", can_3way

        # Reverse check : if `git apply --reverse --check` succeeds, the
        # patch can still be reverted — the file is in a *post-patch*
        # compatible state with cosmetic drift on the patched side.
        # Lifecycle state = `patched`.
        rev = _run_git_apply(["--reverse", "--check"], work_root, patch_path)
        if rev.returncode == 0:
            can_3way = _run_git_apply(
                ["--3way", "--check"], work_root, patch_path
            ).returncode == 0
            return "patched", "cosmetic", can_3way

        # Both fail. Per-hunk split to distinguish partial vs dirty.
    finally:
        cleanup()

    # Per-hunk count uses its own ephemeral repo — cleanup was already
    # invoked above. Doing two passes is acceptable for jalon 5 (simple,
    # legible; optimisable later).
    applyable, total = _count_applyable_hunks(patch_path, vendor_root)
    # can_3way independent of per-hunk split:
    work_root, cleanup = _ensure_git_tree(vendor_root)
    try:
        can_3way = _run_git_apply(
            ["--3way", "--check"], work_root, patch_path
        ).returncode == 0
    finally:
        cleanup()

    if applyable > 0 and applyable < total:
        return "partial", "semantic", can_3way
    return "dirty", "semantic", can_3way


def evaluate(
    record: dict[str, Any],
    vendor_root: Path,
    patches_dir: Path,
) -> dict[str, Any]:
    """Composite detection — sha256 + git apply --check escalation.

    Returns::

        {
          "state": "clean"|"patched"|"dirty"|"partial"|"absent"|"unknown",
          "per_target": [{"path": str, "state": str, "sha256": str|None}, ...],
          "can_auto_3way": bool,
          "drift_hint": "cosmetic"|"semantic"|None,
        }

    The sha-based aggregation is authoritative for clean/patched/partial/
    absent. For `dirty` alone we escalate to `git apply --check` on the
    super-repo (design §5.5) to distinguish cosmetic drift from semantic
    conflict, and to flag partial hunks.
    """
    targets = record.get("targets") or []
    per_target = []
    states: list[str] = []
    for t in targets:
        st, sha = _per_target_state(t, record, vendor_root)
        per_target.append({"path": t.get("path", ""), "state": st, "sha256": sha})
        states.append(st)

    agg = _aggregate(states)
    result: dict[str, Any] = {
        "state": agg,
        "per_target": per_target,
        "can_auto_3way": False,
        "drift_hint": None,
    }

    if agg != "dirty":
        return result

    # Dirty — try to distinguish cosmetic drift / partial / true dirty.
    patch_file = record.get("patch_file")
    if not patch_file:
        return result
    patch_path = patches_dir / patch_file

    state, hint, can_3way = _composite_probe(patch_path, vendor_root)
    result["state"] = state
    result["drift_hint"] = hint
    result["can_auto_3way"] = can_3way
    # Propagate the composite state to per_target entries that were sha-
    # dirty : a top-level reclassification to clean/patched means those
    # dirty targets are actually pre-patch / post-patch with cosmetic
    # drift. Leave `absent` entries untouched.
    if state in ("clean", "patched"):
        for pt in result["per_target"]:
            if pt["state"] == "dirty":
                pt["state"] = state
    return result
