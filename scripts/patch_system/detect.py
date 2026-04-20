"""State detection v1 — sha256 only.

See docs/260420-patch-system-design.md §2.2 (Moteur detection) + §3.2.

This v1 covers: clean / patched / dirty / partial / absent. It does *not* yet
call `git apply --check` — that is jalon 5.

Algorithm (per target):
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
from pathlib import Path
from typing import Any


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _per_target_state(target: dict[str, Any], record: dict[str, Any], vendor_root: Path) -> str:
    """Resolve the state for a single target entry."""
    rel = target.get("path", "")
    # target paths in the design are stored as `vendor/obsidian-wiki/...`
    # relative to the project root. `vendor_root` points to that subtree, so
    # we strip a leading `vendor/<name>/` if present.
    candidate = Path(rel)
    if candidate.is_absolute():
        full = candidate
    else:
        parts = candidate.parts
        # Strip a leading `vendor/<x>/` prefix so the path is resolved under
        # vendor_root. This lets tests point vendor_root at an arbitrary dir.
        if len(parts) >= 2 and parts[0] == "vendor":
            candidate = Path(*parts[2:])
        full = vendor_root / candidate

    if not full.exists():
        return "absent"

    # sha256 preferences: per-target values override record-level defaults.
    # Design §3.2 uses un-prefixed names on both record and target. We still
    # accept record-level fallbacks for robustness (records may or may not
    # carry them depending on tooling phase).
    baseline = target.get("baseline_sha256") or record.get("baseline_sha256")
    patched = target.get("patched_sha256") or record.get("patched_sha256")

    observed = _sha256_of_file(full)
    if baseline and observed == baseline:
        return "clean"
    if patched and observed == patched:
        return "patched"
    return "dirty"


def detect_state(record: dict[str, Any], vendor_root: Path) -> str:
    """Return an element of registry.VALID_STATES for the record as a whole."""
    targets = record.get("targets") or []
    if not targets:
        return "unknown"

    per_target = [_per_target_state(t, record, vendor_root) for t in targets]

    if any(s == "absent" for s in per_target):
        return "absent"
    if any(s == "dirty" for s in per_target):
        return "dirty"
    if all(s == "clean" for s in per_target):
        return "clean"
    if all(s == "patched" for s in per_target):
        return "patched"
    # mix of clean + patched (no dirty/absent) -> partial
    return "partial"
