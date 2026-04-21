"""Runtime strategy resolver — reads ``patches/runtime.json`` (jalon 14).

Design refs :

- §3.3 lines 230-257 (verbatim) : `runtime.json` schema with
  ``schema_version``, ``defaults`` (detection / apply / rollback / drift),
  and ``overrides[id]`` that merge on top of defaults.
- §7 item 14 (verbatim) : "Fallback ``patch(1)`` + dial ``--auto-3way``
  + ``runtime.json`` overrides. Tests."
- §5.5 — escalade drift & ``--auto-3way`` semantics (consumed by apply.py).
- §5.8 — separation series (quoi) / runtime (comment).

``runtime.json`` is optional. When absent, hardcoded defaults matching
§3.3 (verbatim) are returned and all records fall back to the default
``git-apply --index`` strategy.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


# Defaults — structure and values copied verbatim from design §3.3
# (lines 238-245). Any change here must be reflected in the design doc.
_DEFAULTS: dict[str, Any] = {
    "detection": {
        "strategy": "composite",
        "signals": ["checksum", "git-apply-reverse-check"],
    },
    "apply": {
        "method": "git-apply",
        "args": ["--index", "--whitespace=nowarn"],
    },
    "rollback": {
        "method": "git-apply",
        "args": ["--reverse", "--index"],
    },
    "drift": {"mode": "verbose"},
}

_SUPPORTED_SCHEMA = "1"
_KNOWN_TOP_KEYS = {"schema_version", "defaults", "overrides"}
_KNOWN_SECTIONS = {"detection", "apply", "rollback", "drift"}


class RuntimeError_(Exception):
    """Raised when ``runtime.json`` is present but malformed."""


def default_runtime() -> dict[str, Any]:
    """Return the hardcoded defaults dict (copy — safe to mutate)."""
    return {
        "schema_version": _SUPPORTED_SCHEMA,
        "defaults": deepcopy(_DEFAULTS),
        "overrides": {},
    }


def load_runtime(patches_dir: Path) -> dict[str, Any]:
    """Load ``patches/runtime.json`` if present, else return defaults.

    Validates the shape:

    - ``schema_version`` must equal ``"1"`` (the only version we ship).
    - Top-level keys outside ``schema_version``, ``defaults``, ``overrides``
      raise ``RuntimeError_``.
    - Per-record override blocks may contain only ``detection``, ``apply``,
      ``rollback``, ``drift`` sections. Unknown sections raise.
    - Missing file → silent default (not an error ; absence is supported
      explicitly by design §3.3).
    """
    p = patches_dir / "runtime.json"
    if not p.exists():
        return default_runtime()

    with p.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, dict):
        raise RuntimeError_(f"runtime.json must be a JSON object, got {type(raw).__name__}")

    extra = set(raw.keys()) - _KNOWN_TOP_KEYS
    if extra:
        raise RuntimeError_(
            f"runtime.json has unknown top-level keys: {sorted(extra)}"
        )

    sv = raw.get("schema_version")
    if sv != _SUPPORTED_SCHEMA:
        raise RuntimeError_(
            f"runtime.json schema_version {sv!r} unsupported (expected "
            f"{_SUPPORTED_SCHEMA!r})"
        )

    # Merge user-provided defaults on top of hardcoded ones (user may
    # redefine sections ; missing sections keep the hardcoded values).
    merged_defaults = deepcopy(_DEFAULTS)
    user_defaults = raw.get("defaults", {}) or {}
    if not isinstance(user_defaults, dict):
        raise RuntimeError_("runtime.json 'defaults' must be an object")
    for section, value in user_defaults.items():
        if section not in _KNOWN_SECTIONS:
            raise RuntimeError_(
                f"runtime.json defaults: unknown section {section!r}"
            )
        merged_defaults[section] = value

    overrides = raw.get("overrides", {}) or {}
    if not isinstance(overrides, dict):
        raise RuntimeError_("runtime.json 'overrides' must be an object")
    for rid, ovr in overrides.items():
        if not isinstance(ovr, dict):
            raise RuntimeError_(
                f"runtime.json overrides[{rid!r}] must be an object"
            )
        for section in ovr:
            if section not in _KNOWN_SECTIONS:
                raise RuntimeError_(
                    f"runtime.json overrides[{rid!r}]: unknown section "
                    f"{section!r}"
                )

    return {
        "schema_version": _SUPPORTED_SCHEMA,
        "defaults": merged_defaults,
        "overrides": deepcopy(overrides),
    }


def resolve_strategy(record_id: str, runtime: dict[str, Any]) -> dict[str, Any]:
    """Return the effective strategy for ``record_id``.

    Merges ``runtime['defaults']`` with ``runtime['overrides'][record_id]``
    if present (overrides replace whole sections, not individual keys
    within a section — per §3.3 where each override block is a full
    section like ``{"apply": {"method": "patch", "args": [...]}}``).
    """
    defaults = runtime.get("defaults") or _DEFAULTS
    overrides_all = runtime.get("overrides") or {}
    ovr = overrides_all.get(record_id, {}) or {}

    resolved: dict[str, Any] = deepcopy(defaults)
    for section, value in ovr.items():
        if section in _KNOWN_SECTIONS:
            resolved[section] = deepcopy(value)
    return resolved
