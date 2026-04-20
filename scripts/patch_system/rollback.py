"""Rollback engine — `git apply --reverse --index` with safety check.

See docs/260420-patch-system-design.md §7 pt 7 and §3.2.

Scope (jalon 7) :
- Reverse the patch via ``git apply --reverse --index``.
- Safety : refuse unless ``record["last_result"] == "patched"``. This
  prevents accidental rollback of a never-applied (or externally-applied)
  patch. ``--force`` (design §4.1) is reserved for jalon 14 and NOT
  implemented here — without it, rollback from anything other than a
  registry-confirmed `patched` state is refused.
- On success, update ``last_applied`` (UTC now) and ``last_result``
  (re-detected post-reverse, typically `clean`).
- ``--dry-run`` invokes ``git apply --reverse --check`` only; no writes.
- Respects the §5.7 flock which is taken by the bash dispatcher.

Out of scope:
- ``rollback --all`` iteration (jalon 13).
- ``--force`` override (jalon 14).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from patch_system import apply as apply_mod
from patch_system import detect, registry


def _git_apply_reverse(
    patch_path: Path, vendor_root: Path, *, check_only: bool = False
) -> subprocess.CompletedProcess[str]:
    args = ["git", "apply", "--reverse", "--index"]
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


def rollback_patch(
    record: dict[str, Any],
    vendor_root: Path,
    patches_dir: Path,
    *,
    dry_run: bool = False,
    yes: bool = False,
    registry_path: Path | None = None,
    all_records: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reverse-apply `record.patch_file` via `git apply --reverse --index`.

    Parameters mirror ``apply_patch``. Returns the same canonical dict
    ``{"success", "from_state", "to_state", "message", ...}``.

    Safety rules :

    - The record must have been explicitly applied before rolling back :
      ``record["last_result"] == "patched"`` is required. Without it,
      return a failure with a clear error (and a hint pointing at
      ``--force`` jalon 14).
    - The ``yes`` flag is accepted for CLI uniformity but has no effect
      on the guard : rollback does not prompt in any jalon-7 mode.
    """
    rid = record.get("id", "<unknown>")
    patch_path = patches_dir / record.get("patch_file", "")

    if not patch_path.exists():
        return apply_mod._result(
            success=False,
            from_state="unknown",
            to_state="unknown",
            message=(
                f"[{rid}] patch file not found: {patch_path} — cannot rollback."
            ),
        )

    # Safety guard : last_result must be "patched".
    last = record.get("last_result")
    if last != "patched":
        return apply_mod._result(
            success=False,
            from_state=str(last) if last is not None else "unknown",
            to_state=str(last) if last is not None else "unknown",
            message=(
                f"[{rid}] refuse to rollback : last_result={last!r} "
                f"(expected 'patched').\n"
                f"  If you know what you're doing, rerun with --force "
                f"(jalon 14, not yet implemented)."
            ),
        )

    # Detect current physical state. Must be `patched` (or patched with
    # cosmetic drift) for the reverse to apply.
    probe = detect.evaluate(record, vendor_root, patches_dir)
    initial_state = probe["state"]

    if dry_run:
        chk = _git_apply_reverse(patch_path, vendor_root, check_only=True)
        if chk.returncode == 0:
            return apply_mod._result(
                success=True,
                from_state=initial_state,
                to_state=initial_state,
                message=(
                    f"[{rid}] {initial_state} -> would rollback "
                    f"{patch_path.name}\n"
                    f"  [dry-run] git apply --reverse --check --index "
                    f"{patch_path.name}  OK\n"
                    f"  [dry-run] no write performed"
                ),
                dry_run=True,
            )
        return apply_mod._result(
            success=False,
            from_state=initial_state,
            to_state=initial_state,
            message=(
                f"[{rid}] {initial_state} -> dry-run git apply --reverse "
                f"--check FAILED\n"
                f"  {chk.stderr.strip()}"
            ),
            dry_run=True,
        )

    # Actually reverse.
    res = _git_apply_reverse(patch_path, vendor_root, check_only=False)
    if res.returncode != 0:
        return apply_mod._result(
            success=False,
            from_state=initial_state,
            to_state=initial_state,
            message=(
                f"[{rid}] {initial_state} -> git apply --reverse FAILED\n"
                f"  {res.stderr.strip()}"
            ),
        )

    post = detect.evaluate(record, vendor_root, patches_dir)
    final_state = post["state"]

    if registry_path is not None and all_records is not None:
        ts = apply_mod._utc_now_iso()
        for r in all_records.get("records", []):
            if r.get("id") == rid:
                r["last_applied"] = ts
                r["last_result"] = final_state
                break
        registry.save(registry_path, all_records)

    return apply_mod._result(
        success=True,
        from_state=initial_state,
        to_state=final_state,
        message=(
            f"[{rid}] {initial_state} -> reversing...\n"
            f"  target(s) reverted -> state={final_state}\n"
            f"  registry updated: last_result={final_state} "
            f"last_applied={apply_mod._utc_now_iso() if registry_path else '(unset)'}"
        ),
    )
