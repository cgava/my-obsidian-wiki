"""Refresh engine — recompute baseline_sha256 / patched_sha256 (jalon 10).

Design refs :

- §7 item 10 (verbatim) : "Commande ``refresh`` — recalcul baseline/patched
  sha depuis l'etat courant. Tests."
- §4.1 (line 308, verbatim) : ``refresh <id> | Recalcule baseline_sha256 +
  patched_sha256 depuis l'etat courant | --dry-run, --yes``
- §4.2 (line 336, verbatim) : ``r  refresh — met a jour baseline_sha256
  depuis l'etat local courant``.

Semantics
---------

When the vendor drifts (typically after a ``git pull`` of the submodule),
the ``baseline_sha256`` / ``patched_sha256`` recorded in series.json become
stale. ``refresh <id>`` recomputes them from the current on-disk state :

- If the record is in state ``clean`` (vendor pristine, patch not
  applied) → only ``baseline_sha256`` is refreshed ; ``patched_sha256``
  is left untouched (can only be known by actually applying the patch
  on the new baseline, which is the user's next step).
- If the record is in state ``patched`` (patch applied on current
  vendor) → only ``patched_sha256`` is refreshed ; ``baseline_sha256``
  is left untouched (the pre-patch state is no longer observable).
- Any other state (``dirty``, ``partial``, ``absent``, ``unknown``)
  → incoherent, refuse with exit 1.

A record ``refresh`` event is appended to
``patches/history/<order>-history.jsonl`` with the old → new SHA pair per
target.

Exit codes (design §4.1, verbatim) :

- ``0`` : refresh OK (or ``--dry-run`` OK).
- ``1`` : state incoherent / cannot safely refresh.
- ``2`` : record id unknown (argparse covers truly-invalid argv).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from patch_system import detect, registry


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_target_path(target_path: str, vendor_root: Path) -> Path:
    p = Path(target_path)
    if p.is_absolute():
        return p
    parts = p.parts
    if len(parts) >= 2 and parts[0] == "vendor":
        p = Path(*parts[2:])
    return vendor_root / p


def _utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_history(
    patches_dir: Path, order: int, event: dict[str, Any]
) -> None:
    """Append one JSONL event to ``patches/history/<order>-history.jsonl``.

    Design §3.2 : history is externalised per-record to avoid blowing up
    series.json on repeat operations.
    """
    hist_dir = patches_dir / "history"
    hist_dir.mkdir(parents=True, exist_ok=True)
    p = hist_dir / f"{order}-history.jsonl"
    with p.open("a", encoding="utf-8") as f:
        json.dump(event, f, ensure_ascii=False, sort_keys=False)
        f.write("\n")


def refresh_record(
    record: dict[str, Any],
    vendor_root: Path,
    patches_dir: Path,
    *,
    dry_run: bool = False,
    yes: bool = False,
    registry_path: Path | None = None,
    all_records: dict[str, Any] | None = None,
    stream=None,
    prompt_fn=None,
) -> dict[str, Any]:
    """Recompute baseline / patched sha256 for a record's targets.

    Parameters
    ----------
    record
        The record to refresh. Must contain ``id``, ``order``,
        ``targets[]``, ``patch_file``.
    vendor_root
        Vendor working tree root (resolve target paths under it).
    patches_dir
        Directory containing ``.patch`` files + ``history/``.
    dry_run
        Print what would change, write nothing.
    yes
        Skip confirmation prompt (non-interactive).
    registry_path
        Path to series.json. Required to persist the refresh.
    all_records
        Full registry dict — modified in-place before being saved.
    stream
        Output stream for messages (default ``sys.stdout``).
    prompt_fn
        Injection point for tests ; callable ``prompt(msg) -> str``. When
        ``yes`` is False and this is None, ``input`` is used.

    Returns
    -------
    dict
        ``{"success": bool, "message": str, "changes": [{"path", "field",
        "old", "new"}, ...]}``.
    """
    if stream is None:
        stream = sys.stdout
    if prompt_fn is None:
        prompt_fn = input

    rid = record.get("id", "<unknown>")
    order = record.get("order", 0)

    # Current state — sha-only aggregation is enough here, we need to know
    # pristine vs patched, not semantic drift.
    state = detect.detect_state(record, vendor_root)
    if state not in ("clean", "patched"):
        return {
            "success": False,
            "message": (
                f"[{rid}] cannot refresh : current state is {state!r}, "
                "expected 'clean' or 'patched'. Resolve the conflict (apply "
                "or rollback) before refreshing."
            ),
            "changes": [],
        }

    # Compute per-target changes.
    changes: list[dict[str, str]] = []
    for t in record.get("targets", []):
        full = _resolve_target_path(t.get("path", ""), vendor_root)
        if not full.exists():
            return {
                "success": False,
                "message": (
                    f"[{rid}] target missing on disk: {t.get('path', '')} "
                    "— cannot refresh."
                ),
                "changes": [],
            }
        observed = _sha256_of_file(full)
        if state == "clean":
            field = "baseline_sha256"
        else:  # state == "patched"
            field = "patched_sha256"
        old = t.get(field, "")
        if observed != old:
            changes.append({
                "path": t.get("path", ""),
                "field": field,
                "old": old,
                "new": observed,
            })

    if not changes:
        stream.write(f"[{rid}] no changes — {state} state sha already matches registry\n")
        return {
            "success": True,
            "message": f"[{rid}] no changes needed (already up-to-date)",
            "changes": [],
        }

    # Preview — always printed.
    stream.write(f"[{rid}] refresh from state={state}:\n")
    for c in changes:
        stream.write(
            f"  {c['path']}: {c['field']} "
            f"{c['old'][:12] or '(empty)'}... -> {c['new'][:12]}...\n"
        )

    if dry_run:
        stream.write(f"[{rid}] [dry-run] no write performed\n")
        return {
            "success": True,
            "message": f"[{rid}] dry-run: {len(changes)} change(s) would be applied",
            "changes": changes,
        }

    # Confirmation prompt unless --yes.
    if not yes:
        try:
            ans = prompt_fn(
                f"[{rid}] apply {len(changes)} change(s) to series.json? (y/N) "
            )
        except EOFError:
            ans = ""
        if ans.strip().lower() not in ("y", "yes"):
            return {
                "success": False,
                "message": f"[{rid}] aborted by user",
                "changes": changes,
            }

    # Mutate registry in place + persist.
    if registry_path is None or all_records is None:
        return {
            "success": False,
            "message": f"[{rid}] internal: registry_path/all_records missing for persistence",
            "changes": changes,
        }

    target_record = None
    for r in all_records.get("records", []):
        if r.get("id") == rid:
            target_record = r
            break
    if target_record is None:
        return {
            "success": False,
            "message": f"[{rid}] record not found in registry",
            "changes": changes,
        }

    # Apply changes target-by-target.
    for c in changes:
        for t in target_record.get("targets", []):
            if t.get("path") == c["path"]:
                t[c["field"]] = c["new"]
                break

    registry.save(registry_path, all_records)

    # History event.
    _append_history(
        patches_dir,
        order,
        {
            "ts": _utc_now_iso(),
            "action": "refresh",
            "result": state,
            "operator": "auto",
            "commit": None,
            "changes": changes,
        },
    )

    stream.write(
        f"[{rid}] registry updated: {len(changes)} change(s) persisted\n"
    )
    return {
        "success": True,
        "message": f"[{rid}] refreshed {len(changes)} target(s)",
        "changes": changes,
    }
