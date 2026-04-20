"""Verify engine — integrity + drift + target coherence checks (jalon 9).

Design refs :

- §2.3 "Flux verify" (lines 111-113, verbatim) : "pour chaque record,
  recalcule ``patch_sha256`` du ``.patch`` sur disque, compare a la valeur
  enregistree ; detecte drift vendor ; reporte."
- §4.1 commandes (line 309, verbatim) : ``verify | Integrite : recalcul
  patch_sha256, drift vendor, coherence targets | --json, --strict``.
- §4.1 exit codes (lines 293-296, verbatim) : ``0`` = succes, ``1`` =
  echec operationnel (conflit non resolu, drift non arbitre), ``2`` =
  erreur d'invocation (argv invalide), ``3`` = etat registry invalide.
- §2.2 "Detection drift vendor" / §3.2 schema (top-level
  ``vendor_baseline_sha``).
- §5.5 "Upstream drift" — escalade, jamais silencieux.

Scope :

Three checks per record :

1. **Integrity** : recompute SHA-256 of the ``.patch`` file on disk and
   compare to the record's ``patch_sha256``. Mismatch → the patch file was
   tampered with or manually edited after being registered.
2. **Drift (vendor)** : compare the top-level ``vendor_baseline_sha`` (if
   recorded) to the current submodule HEAD. Also flag per-target baseline
   drift when the current file SHA differs from BOTH ``baseline_sha256``
   and ``patched_sha256`` (target is neither pristine nor patched — may
   need refresh).
3. **Target coherence** : every ``targets[].path`` referenced by an
   ``active`` record must exist under ``vendor_root`` (missing target is a
   hard incoherence).

Exit code semantics (design §4.1, verbatim above) :

- ``0`` : all checks pass, or warnings only in non-strict mode.
- ``1`` : integrity mismatch OR missing target OR drift arbitrated
  strictly.
- ``3`` : registry schema violation (delegated to ``registry.validate``).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from patch_system import registry


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_target_path(target_path: str, vendor_root: Path) -> Path:
    """Resolve a registry target path relative to vendor_root.

    Mirrors ``detect._resolve_target_path`` — keep behaviour consistent :
    registry target paths use the ``vendor/<name>/...`` form and the
    caller points ``vendor_root`` at that subtree, so we strip a leading
    two-part prefix when relative.
    """
    p = Path(target_path)
    if p.is_absolute():
        return p
    parts = p.parts
    if len(parts) >= 2 and parts[0] == "vendor":
        p = Path(*parts[2:])
    return vendor_root / p


def _current_vendor_head(vendor_root: Path) -> str | None:
    """Return the current submodule HEAD, or None when git unavailable /
    not a git tree."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(vendor_root),
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, FileNotFoundError):
        return None
    if res.returncode != 0:
        return None
    head = res.stdout.strip()
    return head or None


# -------------------------------------------------------------------------
# Per-record checks
# -------------------------------------------------------------------------


def _check_integrity(
    record: dict[str, Any], patches_dir: Path
) -> tuple[str, list[str]]:
    """Recompute patch_sha256 and compare (design §2.3 Flux verify).

    Returns (status, issues) where status ∈ {"ok", "mismatch", "missing"}.
    """
    patch_file = record.get("patch_file", "")
    expected = record.get("patch_sha256", "")
    patch_path = patches_dir / patch_file

    if not patch_path.exists():
        return (
            "missing",
            [f"patch file missing on disk: {patch_path}"],
        )
    observed = _sha256_of_file(patch_path)
    if observed != expected:
        return (
            "mismatch",
            [
                f"integrity mismatch for {patch_file}: "
                f"registry={expected[:12]}... disk={observed[:12]}... "
                "— patch file tampered/edited"
            ],
        )
    return "ok", []


def _check_target_coherence(
    record: dict[str, Any], vendor_root: Path
) -> tuple[str, list[str]]:
    """Verify every target path exists under vendor_root.

    Returns (status, issues) where status ∈ {"ok", "missing_targets"}.
    An ``active`` record with a missing target is an incoherence ; a
    record with ``status`` != ``active`` only emits a warning.
    """
    missing: list[str] = []
    for t in record.get("targets", []):
        full = _resolve_target_path(t.get("path", ""), vendor_root)
        if not full.exists():
            missing.append(t.get("path", ""))
    if missing:
        kind = (
            "missing target" if record.get("status") == "active"
            else "warning: missing target (record non-active)"
        )
        return (
            "missing_targets",
            [f"{kind}: {', '.join(missing)}"],
        )
    return "ok", []


def _check_drift(
    record: dict[str, Any],
    vendor_root: Path,
    recorded_baseline_head: str | None,
    current_head: str | None,
) -> tuple[str, list[str]]:
    """Drift signals — top-level + per-target.

    Returns (status, issues) where status ∈ {"ok", "detected"}.

    - Top-level drift : ``vendor_baseline_sha`` recorded in series.json
      differs from the current submodule HEAD (design §2.2 drift.py).
    - Per-target drift : the on-disk sha256 of a target differs from
      BOTH ``baseline_sha256`` and ``patched_sha256`` — the target has a
      third state and the record's references may need a ``refresh``.
    """
    issues: list[str] = []

    # Top-level drift.
    if recorded_baseline_head and current_head and recorded_baseline_head != current_head:
        issues.append(
            f"vendor baseline drift: recorded "
            f"{recorded_baseline_head[:12]}... current "
            f"{current_head[:12]}..."
        )

    # Per-target drift — file exists but matches neither baseline nor
    # patched. Signals that the target on-disk has an unknown third state.
    for t in record.get("targets", []):
        full = _resolve_target_path(t.get("path", ""), vendor_root)
        if not full.exists():
            continue  # handled by coherence check
        observed = _sha256_of_file(full)
        baseline = t.get("baseline_sha256", "")
        patched = t.get("patched_sha256", "")
        if observed != baseline and observed != patched:
            issues.append(
                f"per-target drift on {t.get('path', '')}: "
                f"observed {observed[:12]}... "
                f"matches neither baseline {baseline[:12]}... "
                f"nor patched {patched[:12]}..."
            )

    return ("detected" if issues else "ok", issues)


# -------------------------------------------------------------------------
# Public entry point
# -------------------------------------------------------------------------


def verify(
    data: dict[str, Any],
    vendor_root: Path,
    patches_dir: Path,
    *,
    json_output: bool = False,
    strict: bool = False,
    stream=None,
) -> int:
    """Run the three checks for every record.

    Parameters
    ----------
    data
        Raw registry dict (``{"schema_version", "vendor_baseline_sha",
        "records"}``).
    vendor_root
        Vendor working tree root.
    patches_dir
        Directory containing ``.patch`` files.
    json_output
        Emit a single JSON dict to ``stream``. Implies ``--no-color``
        (there is no colour output anyway).
    strict
        Upgrade warnings (drift only — never integrity/coherence) to
        failures. See design §5.5 : drift must never be silent.
    stream
        Output stream (defaults to ``sys.stdout``). Tests inject StringIO.

    Returns
    -------
    int
        Exit code per design §4.1 : ``0`` ok, ``1`` failure, ``3``
        registry invalid.
    """
    if stream is None:
        stream = sys.stdout

    # Registry validity (§4.1 exit 3).
    errors = registry.validate(data)
    if errors:
        if json_output:
            json.dump(
                {"registry_valid": False, "errors": errors},
                stream, indent=2, ensure_ascii=False,
            )
            stream.write("\n")
        else:
            stream.write("verify: registry invalid\n")
            for e in errors:
                stream.write(f"  {e}\n")
        return 3

    records = data.get("records", [])
    if not records:
        if json_output:
            json.dump(
                {"registry_valid": True, "records": {}, "summary": {"ok": 0, "failed": 0, "warnings": 0}},
                stream, indent=2, ensure_ascii=False,
            )
            stream.write("\n")
        else:
            stream.write("verify: (empty registry — nothing to verify)\n")
        return 0

    recorded_baseline = data.get("vendor_baseline_sha")
    current_head = _current_vendor_head(vendor_root)

    per_record: dict[str, Any] = {}
    exit_code = 0

    for rec in sorted(records, key=lambda r: r.get("order", 0)):
        rid = rec.get("id", "<unknown>")
        integrity_status, integrity_issues = _check_integrity(rec, patches_dir)
        coherence_status, coherence_issues = _check_target_coherence(
            rec, vendor_root
        )
        drift_status, drift_issues = _check_drift(
            rec, vendor_root, recorded_baseline, current_head
        )
        all_issues = integrity_issues + coherence_issues + drift_issues

        per_record[rid] = {
            "integrity": integrity_status,
            "drift": drift_status,
            "coherence": coherence_status,
            "issues": all_issues,
        }

        # Escalation rules (§4.1 exit codes) :
        # - integrity mismatch / missing patch file → always fail (1)
        # - coherence missing_targets (active record) → always fail (1)
        # - drift detected → warning, failure only in --strict
        if integrity_status in ("mismatch", "missing"):
            exit_code = 1
        if (
            coherence_status == "missing_targets"
            and rec.get("status") == "active"
        ):
            exit_code = 1
        if strict and drift_status == "detected":
            exit_code = 1

    # Render.
    if json_output:
        summary = {
            "ok": sum(
                1 for r in per_record.values()
                if not r["issues"]
            ),
            "failed": sum(
                1 for r in per_record.values()
                if r["integrity"] in ("mismatch", "missing")
                or r["coherence"] == "missing_targets"
            ),
            "warnings": sum(
                1 for r in per_record.values()
                if r["drift"] == "detected"
            ),
        }
        payload = {
            "registry_valid": True,
            "vendor_baseline_recorded": recorded_baseline,
            "vendor_baseline_current": current_head,
            "records": per_record,
            "summary": summary,
            "strict": strict,
        }
        json.dump(payload, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        return exit_code

    # Text rendering — one line per record plus indented issue list.
    for rid, info in per_record.items():
        flags = []
        if info["integrity"] != "ok":
            flags.append(f"integrity={info['integrity']}")
        if info["coherence"] != "ok":
            flags.append(f"coherence={info['coherence']}")
        if info["drift"] != "ok":
            flags.append(f"drift={info['drift']}")
        if not flags:
            stream.write(f"[{rid}] ok\n")
        else:
            stream.write(f"[{rid}] {' '.join(flags)}\n")
            for issue in info["issues"]:
                stream.write(f"    - {issue}\n")

    # Footer.
    if recorded_baseline and current_head and recorded_baseline != current_head:
        stream.write(
            f"Vendor baseline drift: recorded={recorded_baseline[:12]}... "
            f"current={current_head[:12]}...\n"
        )
    elif not recorded_baseline:
        stream.write("Vendor baseline: not recorded in series.json\n")

    if exit_code == 0:
        stream.write("verify: all records ok\n")
    else:
        stream.write("verify: failures detected\n")
    return exit_code
