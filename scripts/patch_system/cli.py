"""CLI argument parsing and command dispatch for patch_system."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from patch_system import registry, detect

# Commands that have a real implementation at this milestone.
_IMPLEMENTED = {"list", "status"}

# Commands declared by the design doc §4.1 but not yet implemented (jalons 5+).
_STUBBED = {"describe", "diff", "apply", "rollback", "verify", "refresh", "record"}


def _project_root() -> Path:
    """Return PATCH_SYSTEM_ROOT (set by bash dispatcher) or cwd."""
    return Path(os.environ.get("PATCH_SYSTEM_ROOT", os.getcwd()))


def _patches_dir() -> Path:
    return _project_root() / "patches"


def _series_path() -> Path:
    return _patches_dir() / "series.json"


def _vendor_root() -> Path:
    return _project_root() / "vendor" / "obsidian-wiki"


def _cmd_list(args: argparse.Namespace) -> int:
    """List records from the registry — TTY-friendly one-line-per-record output.

    Format (design §3.2/§4.1) : `<order> <id> <severity> <status> — <title>`
    where `status` is the lifecycle marker (active/disabled/obsolete),
    not a derived detection state.
    """
    series_path = Path(args.series) if args.series else _series_path()
    data = registry.load(series_path)
    records = data.get("records", [])
    if not records:
        print("(empty)")
        return 0
    # Sort by order for display stability.
    for r in sorted(records, key=lambda rec: rec.get("order", 0)):
        print(
            f"{r.get('order', '?'):>4}  {r.get('id', '?'):40s}  "
            f"{r.get('severity', '?'):11s}  "
            f"{r.get('status', '?'):8s}  "
            f"- {r.get('title', '')}"
        )
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    """Recompute per-record state via detect.py and display live state.

    Does not consult the stored `last_result` — that is a cache-only field.
    """
    series_path = Path(args.series) if args.series else _series_path()
    vendor_root = Path(args.vendor_root) if args.vendor_root else _vendor_root()
    data = registry.load(series_path)
    records = data.get("records", [])
    if not records:
        print("(empty)")
        return 0
    for r in sorted(records, key=lambda rec: rec.get("order", 0)):
        state = detect.detect_state(r, vendor_root)
        print(
            f"{r.get('order', '?'):>4}  {r.get('id', '?'):40s}  "
            f"{r.get('severity', '?'):11s}  "
            f"{state:8s}  "
            f"- {r.get('title', '')}"
        )
    return 0


def _cmd_not_implemented(name: str) -> int:
    """Uniform error for stubbed commands (jalons 5+)."""
    print(
        f"patch-system: command '{name}' not yet implemented (see design §7)",
        file=sys.stderr,
    )
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="patch-system",
        description="Manage local patches on vendor/obsidian-wiki.",
    )
    parser.add_argument(
        "--series",
        default=None,
        help="Path to series.json (default: $PATCH_SYSTEM_ROOT/patches/series.json).",
    )
    parser.add_argument(
        "--vendor-root",
        default=None,
        help="Vendor working tree root (default: $PATCH_SYSTEM_ROOT/vendor/obsidian-wiki).",
    )

    sub = parser.add_subparsers(dest="cmd", metavar="command")
    sub.required = True

    sub.add_parser("list", help="List records from the registry.")
    sub.add_parser("status", help="Show per-record detected state.")

    # Stubbed commands — registered so they parse, but fail cleanly with exit 2.
    for name in sorted(_STUBBED):
        p = sub.add_parser(name, help=f"(not yet implemented) {name}")
        p.add_argument("rest", nargs=argparse.REMAINDER)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "list":
        return _cmd_list(args)
    if args.cmd == "status":
        return _cmd_status(args)
    if args.cmd in _STUBBED:
        return _cmd_not_implemented(args.cmd)

    parser.error(f"unknown command: {args.cmd}")
    return 2  # unreachable
