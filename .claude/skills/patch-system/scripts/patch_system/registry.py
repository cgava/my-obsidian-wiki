"""Registry IO + schema validation for patches/series.json.

Schema v1 — aligned with docs/260420-patch-system-design.md §3.2.

Top-level registry layout::

    {
      "schema_version": "1",
      "vendor_baseline_sha": "...",          # optional, not strictly validated
      "records": [ <record>, ... ]
    }

Each record (registre logique) mandatory fields:
  id, order, status, severity, title, patch_file, patch_sha256, targets[]

Each targets[] entry mandatory fields:
  path, baseline_sha256, patched_sha256

Optional record fields: audit_ref, last_applied, last_result, notes.

Note: only the JSON registry drops the X-* prefix. DEP-3 patch headers
(§3.4) keep the X-Baseline-Sha256 / X-Patched-Sha256 / X-Audit-Ref /
X-Severity names.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Design §3.2 cites the schema_version as a string literal "1".
SCHEMA_VERSION = "1"

# Derived lifecycle state of a record — output of detect.py, also stored
# (when present) in the optional `last_result` field of a record.
VALID_STATES = ["clean", "patched", "dirty", "partial", "absent", "unknown"]

# Severity classes (design §3.2 — aligned with the dual-sensitivity audit
# taxonomy from the SOA analysis).
VALID_SEVERITIES = ["BLOCKING", "TROMPEUR", "COSMETIQUE", "INFO"]

# Top-level `status` on a record is a lifecycle marker (§3.2 / SOA §4.4).
VALID_LIFECYCLE = ["active", "disabled", "obsolete"]

_REQUIRED_RECORD_FIELDS = (
    "id",
    "order",
    "status",
    "severity",
    "title",
    "patch_file",
    "patch_sha256",
    "targets",
)

_OPTIONAL_RECORD_FIELDS = (
    "audit_ref",
    "last_applied",
    "last_result",
    "notes",
)

_REQUIRED_TARGET_FIELDS = ("path", "baseline_sha256", "patched_sha256")

# sha256 hex digest: exactly 64 lowercase or uppercase hex chars.
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def load(path: Path) -> dict[str, Any]:
    """Load series.json. Return an empty registry if the file is absent."""
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "records": []}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save(path: Path, data: dict[str, Any]) -> None:
    """Write series.json with stable formatting.

    indent=2 + sort_keys=False preserves the explicit ordering of the caller.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=False, ensure_ascii=False)
        f.write("\n")  # POSIX-friendly trailing newline.


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA256_RE.match(value))


def validate(data: dict[str, Any]) -> list[str]:
    """Return a list of error messages. Empty list = valid.

    Strict validation: every mandatory field must be present *and* of the
    right type/shape. Enums and sha256 formats are checked.
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["top-level object must be a dict"]

    sv = data.get("schema_version")
    if sv != SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {SCHEMA_VERSION!r}, got {sv!r}"
        )

    records = data.get("records")
    if not isinstance(records, list):
        errors.append("'records' must be a list")
        return errors  # no point validating individual entries

    seen_ids: set[str] = set()
    seen_orders: set[int] = set()

    for idx, record in enumerate(records):
        prefix = f"records[{idx}]"
        if not isinstance(record, dict):
            errors.append(f"{prefix}: must be a dict")
            continue

        # Required fields.
        for field in _REQUIRED_RECORD_FIELDS:
            if field not in record:
                errors.append(f"{prefix}: missing required field '{field}'")

        # id: non-empty string, unique.
        pid = record.get("id")
        if "id" in record:
            if not isinstance(pid, str) or not pid:
                errors.append(f"{prefix}.id: must be a non-empty string")
            else:
                if pid in seen_ids:
                    errors.append(f"{prefix}: duplicate id '{pid}'")
                seen_ids.add(pid)

        # order: positive int, unique. Bool is a subclass of int so reject it.
        order = record.get("order")
        if "order" in record:
            if isinstance(order, bool) or not isinstance(order, int):
                errors.append(f"{prefix}.order: must be an integer")
            else:
                if order <= 0:
                    errors.append(f"{prefix}.order: must be > 0")
                if order in seen_orders:
                    errors.append(f"{prefix}: duplicate order {order}")
                seen_orders.add(order)

        # status (lifecycle): active | disabled | obsolete.
        status = record.get("status")
        if "status" in record and status not in VALID_LIFECYCLE:
            errors.append(
                f"{prefix}.status: must be one of {VALID_LIFECYCLE}, "
                f"got {status!r}"
            )

        # severity: BLOCKING | TROMPEUR | COSMETIQUE | INFO.
        sev = record.get("severity")
        if "severity" in record and sev not in VALID_SEVERITIES:
            errors.append(
                f"{prefix}.severity: must be one of {VALID_SEVERITIES}, "
                f"got {sev!r}"
            )

        # title: non-empty string.
        title = record.get("title")
        if "title" in record and (not isinstance(title, str) or not title):
            errors.append(f"{prefix}.title: must be a non-empty string")

        # patch_file: non-empty string.
        patch_file = record.get("patch_file")
        if "patch_file" in record and (
            not isinstance(patch_file, str) or not patch_file
        ):
            errors.append(f"{prefix}.patch_file: must be a non-empty string")

        # patch_sha256: hex 64 chars.
        patch_sha = record.get("patch_sha256")
        if "patch_sha256" in record and not _is_sha256(patch_sha):
            errors.append(
                f"{prefix}.patch_sha256: must be a 64-char hex sha256 string, "
                f"got {patch_sha!r}"
            )

        # last_result (optional) uses the VALID_STATES enum.
        last = record.get("last_result")
        if "last_result" in record and last not in VALID_STATES:
            errors.append(
                f"{prefix}.last_result: must be one of {VALID_STATES}, "
                f"got {last!r}"
            )

        # targets: non-empty list of dicts, each with path + baseline + patched.
        targets = record.get("targets")
        if "targets" in record:
            if not isinstance(targets, list) or not targets:
                errors.append(f"{prefix}.targets: must be a non-empty list")
            else:
                for t_idx, tgt in enumerate(targets):
                    t_prefix = f"{prefix}.targets[{t_idx}]"
                    if not isinstance(tgt, dict):
                        errors.append(f"{t_prefix}: must be a dict")
                        continue
                    for tfield in _REQUIRED_TARGET_FIELDS:
                        if tfield not in tgt:
                            errors.append(
                                f"{t_prefix}: missing required field "
                                f"'{tfield}'"
                            )
                    path_val = tgt.get("path")
                    if "path" in tgt and (
                        not isinstance(path_val, str) or not path_val
                    ):
                        errors.append(
                            f"{t_prefix}.path: must be a non-empty string"
                        )
                    bsh = tgt.get("baseline_sha256")
                    if "baseline_sha256" in tgt and not _is_sha256(bsh):
                        errors.append(
                            f"{t_prefix}.baseline_sha256: must be a 64-char "
                            f"hex sha256 string, got {bsh!r}"
                        )
                    psh = tgt.get("patched_sha256")
                    if "patched_sha256" in tgt and not _is_sha256(psh):
                        errors.append(
                            f"{t_prefix}.patched_sha256: must be a 64-char "
                            f"hex sha256 string, got {psh!r}"
                        )

    return errors
