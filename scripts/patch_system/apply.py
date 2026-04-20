"""Apply engine v1 — `git apply --index` with idempotence + registry update.

See docs/260420-patch-system-design.md §5.2 (no auto-commit), §5.7 (flock —
handled by the bash dispatcher), §3.2 (last_applied / last_result), §4.3
(apply messages).

Scope (jalon 6) :
- Forward application via ``git apply --index``.
- Idempotence: if already patched, no-op, do not re-write the registry.
- Non-interactive arbitration: `dirty` / `partial` without ``--yes``
  return a non-zero result with a "rerun with --interactive" hint.
  ``--yes`` alone does NOT force-apply (design §4.3 message: "--yes mode
  forbids interactive arbitration" → exit 1).
- ``--dry-run`` runs ``git apply --check`` only, never writes to disk or
  the registry.
- Updates ``last_applied`` (ISO UTC now) and ``last_result`` on success.

Explicitly out of scope:
- `--3way` / `--force` / `--interactive` (jalons 12, 14).
- `apply --all` (jalon 13).
- Fallback to ``patch(1)`` (jalon 14).
- Auto-commit in vendor submodule or super-repo (§5.2 — never).
"""

from __future__ import annotations

import datetime as _dt
import subprocess
from pathlib import Path
from typing import Any

from patch_system import detect, registry


def _utc_now_iso() -> str:
    """Return current time as an ISO-8601 string in UTC (Zulu suffix).

    Stored in `last_applied` — format aligned with design §3.2 example
    `"2026-04-20T10:52:13Z"`.
    """
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_patch_path(record: dict[str, Any], patches_dir: Path) -> Path:
    patch_file = record.get("patch_file", "")
    return patches_dir / patch_file


def _git_apply_index(
    patch_path: Path, vendor_root: Path, *, check_only: bool = False
) -> subprocess.CompletedProcess[str]:
    args = ["git", "apply", "--index"]
    if check_only:
        args.append("--check")
    args.append(str(patch_path))
    return subprocess.run(
        args,
        cwd=str(vendor_root),
        capture_output=True,
        text=True,
        check=False,
    )


def _result(
    success: bool,
    from_state: str,
    to_state: str,
    message: str,
    **extra: Any,
) -> dict[str, Any]:
    """Canonical return dict for apply_patch / rollback_patch."""
    out: dict[str, Any] = {
        "success": success,
        "from_state": from_state,
        "to_state": to_state,
        "message": message,
    }
    out.update(extra)
    return out


def apply_patch(
    record: dict[str, Any],
    vendor_root: Path,
    patches_dir: Path,
    *,
    dry_run: bool = False,
    yes: bool = False,
    registry_path: Path | None = None,
    all_records: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply `record.patch_file` to `vendor_root` via `git apply --index`.

    Parameters
    ----------
    record
        The patch record (as loaded from series.json). Must contain
        ``patch_file`` and ``targets[]``.
    vendor_root
        Working tree under which the patch applies. Must be a git repo
        for --index to be meaningful.
    patches_dir
        Directory containing ``.patch`` files.
    dry_run
        If True, only ``git apply --check`` is invoked. Registry is not
        written. Return describes the dry-run outcome.
    yes
        Non-interactive. If the initial state is dirty/partial/absent,
        return a failure with a clear "rerun with --interactive" message
        (§4.3 drift message).
    registry_path
        Path to series.json. Required if the apply succeeds and should
        persist ``last_applied`` / ``last_result``. If None, registry is
        not written (unit test convenience).
    all_records
        Full registry dict (``{"schema_version": ..., "records": [...]}``).
        Required alongside ``registry_path`` for persistence — used to
        re-save the modified record in place.

    Returns
    -------
    dict
        ``{"success": bool, "from_state": str, "to_state": str,
        "message": str, ...}``.
    """
    rid = record.get("id", "<unknown>")
    patch_path = _resolve_patch_path(record, patches_dir)

    if not patch_path.exists():
        return _result(
            success=False,
            from_state="unknown",
            to_state="unknown",
            message=(
                f"[{rid}] patch file not found: {patch_path} — cannot apply."
            ),
        )

    # Initial state via the composite detector.
    probe = detect.evaluate(record, vendor_root, patches_dir)
    initial_state = probe["state"]

    # Idempotence — already patched, no-op (§4.3).
    if initial_state == "patched":
        return _result(
            success=True,
            from_state="patched",
            to_state="patched",
            message=f"[{rid}] patched -> skip (already applied)",
            noop=True,
        )

    # Dry-run — `git apply --check`, no writes.
    if dry_run:
        chk = _git_apply_index(patch_path, vendor_root, check_only=True)
        if chk.returncode == 0:
            return _result(
                success=True,
                from_state=initial_state,
                to_state=initial_state,  # nothing mutated
                message=(
                    f"[{rid}] {initial_state} -> would apply "
                    f"{patch_path.name}\n"
                    f"  [dry-run] git apply --check --index "
                    f"{patch_path.name}  OK\n"
                    f"  [dry-run] no write performed"
                ),
                dry_run=True,
            )
        return _result(
            success=False,
            from_state=initial_state,
            to_state=initial_state,
            message=(
                f"[{rid}] {initial_state} -> dry-run git apply --check "
                f"FAILED\n"
                f"  {chk.stderr.strip()}"
            ),
            dry_run=True,
        )

    # Absent → cannot apply.
    if initial_state == "absent":
        return _result(
            success=False,
            from_state="absent",
            to_state="absent",
            message=(
                f"[{rid}] one or more target files are absent — "
                f"cannot apply. Targets missing : "
                f"{[t['path'] for t in probe['per_target'] if t['state'] == 'absent']}"
            ),
        )

    # Dirty / partial without --interactive : block per §4.3.
    if initial_state in ("dirty", "partial"):
        if not yes:
            return _result(
                success=False,
                from_state=initial_state,
                to_state=initial_state,
                message=(
                    f"[{rid}] {initial_state} -> arbitration required.\n"
                    f"  Rerun with --interactive to resolve, or (jalon 14) "
                    f"--force to overwrite."
                ),
            )
        # yes alone still refuses (§4.3 message): --yes forbids arbitration.
        return _result(
            success=False,
            from_state=initial_state,
            to_state=initial_state,
            message=(
                f"[{rid}] {initial_state} -> ambiguous state.\n"
                f"  ERROR: --yes mode forbids interactive arbitration.\n"
                f"  Rerun with --interactive to resolve, or (jalon 14) "
                f"--force to overwrite."
            ),
        )

    # initial_state == "clean" → apply forward.
    res = _git_apply_index(patch_path, vendor_root, check_only=False)
    if res.returncode != 0:
        return _result(
            success=False,
            from_state=initial_state,
            to_state=initial_state,
            message=(
                f"[{rid}] {initial_state} -> git apply FAILED\n"
                f"  {res.stderr.strip()}"
            ),
        )

    # Re-detect post-apply. Expected: "patched".
    post_probe = detect.evaluate(record, vendor_root, patches_dir)
    final_state = post_probe["state"]

    # Persist registry if caller provided path + payload.
    if registry_path is not None and all_records is not None:
        ts = _utc_now_iso()
        # Mutate the record in-place within all_records to preserve
        # dict identity for the caller's convenience.
        for r in all_records.get("records", []):
            if r.get("id") == rid:
                r["last_applied"] = ts
                r["last_result"] = final_state
                break
        registry.save(registry_path, all_records)

    return _result(
        success=True,
        from_state=initial_state,
        to_state=final_state,
        message=(
            f"[{rid}] {initial_state} -> applying...\n"
            f"  target(s) patched -> state={final_state}\n"
            f"  registry updated: last_result={final_state} "
            f"last_applied={_utc_now_iso() if registry_path else '(unset)'}"
        ),
    )
