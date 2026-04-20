"""CLI argument parsing and command dispatch for patch_system.

Design refs :
- §4.1 commands + transverse flags (``--json``, ``--dry-run``, ``--yes``,
  ``--verbose``, ``--quiet``).
- §4.2 interactive mode (jalon 12 — stubbed here).
- §4.3 canonical messages.
- §4.4 ``status`` table layout + ``--json`` schema.
- §5.5 drift escalation (surfaced via ``state`` + stretch metadata).
- §5.7 flock (taken by the bash dispatcher, not here).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import contextlib

from patch_system import apply as apply_mod
from patch_system import detect, registry, rollback as rb_mod
from patch_system import refresh as refresh_mod
from patch_system import runtime as runtime_mod
from patch_system import verify as verify_mod


# -------------------------------------------------------------------------
# Flock helper — design §5.7 (verbatim) requires `patches/.lock` around
# every mutating operation. For `--all` runs, one lock covers the whole
# iteration (brief line: "1 flock pour la run entière, pas par record").
# -------------------------------------------------------------------------


@contextlib.contextmanager
def _patches_flock(patches_dir: Path):
    """Acquire a non-blocking advisory lock on ``patches/.lock``.

    Uses :mod:`fcntl` when available (POSIX). A no-op fallback is used
    when fcntl is missing (non-POSIX dev platforms) — correctness
    depends on POSIX in practice, but tests must still pass cross-OS.
    """
    lock_path = patches_dir / ".lock"
    try:
        patches_dir.mkdir(parents=True, exist_ok=True)
        fh = open(lock_path, "a+")
    except OSError as e:
        print(f"patch-system: cannot open lock {lock_path}: {e}", file=sys.stderr)
        raise
    try:
        try:
            import fcntl  # noqa: F401
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print(
                    "patch-system: another operation in progress "
                    "(patches/.lock held)",
                    file=sys.stderr,
                )
                raise SystemExit(1)
        except ImportError:
            pass  # best-effort on non-POSIX
        yield fh
    finally:
        try:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        fh.close()


# -------------------------------------------------------------------------
# Path helpers — `PATCH_SYSTEM_ROOT` is exported by the bash dispatcher.
# -------------------------------------------------------------------------


def _project_root() -> Path:
    return Path(os.environ.get("PATCH_SYSTEM_ROOT", os.getcwd()))


def _patches_dir() -> Path:
    return _project_root() / "patches"


def _series_path() -> Path:
    return _patches_dir() / "series.json"


def _vendor_root() -> Path:
    return _project_root() / "vendor" / "obsidian-wiki"


def _load_ctx(args: argparse.Namespace) -> tuple[Path, Path, Path, dict[str, Any]]:
    """Return (series_path, vendor_root, patches_dir, registry_data)."""
    series_path = Path(args.series) if args.series else _series_path()
    vendor_root = (
        Path(args.vendor_root) if args.vendor_root else _vendor_root()
    )
    patches_dir = series_path.parent
    data = registry.load(series_path)
    return series_path, vendor_root, patches_dir, data


def _record_by_id(data: dict[str, Any], rid: str) -> dict[str, Any] | None:
    for r in data.get("records", []):
        if r.get("id") == rid:
            return r
    return None


# -------------------------------------------------------------------------
# `list` — one line per record.
# -------------------------------------------------------------------------


def _cmd_list(args: argparse.Namespace) -> int:
    """List records (design §4.1).

    Columns : order, id, severity, lifecycle-status, title. Filterable
    with ``--status=active|disabled|obsolete``. ``--json`` emits the raw
    record dicts.
    """
    _, _, _, data = _load_ctx(args)
    records = data.get("records", [])

    status_filter = getattr(args, "status_filter", None)
    if status_filter:
        records = [r for r in records if r.get("status") == status_filter]

    if getattr(args, "json", False):
        json.dump(
            {"records": records}, sys.stdout, indent=2, ensure_ascii=False
        )
        sys.stdout.write("\n")
        return 0

    if not records:
        print("(empty)")
        return 0

    for r in sorted(records, key=lambda rec: rec.get("order", 0)):
        print(
            f"{r.get('order', '?'):>4}  {r.get('id', '?'):40s}  "
            f"{r.get('severity', '?'):11s}  "
            f"{r.get('status', '?'):8s}  "
            f"- {r.get('title', '')}"
        )
    return 0


# -------------------------------------------------------------------------
# `status` — tabular per-record live state (§4.4).
# -------------------------------------------------------------------------


def _targets_fraction(agg_state: str, per_target: list[dict]) -> str:
    """Return "N/M" targets fraction consistent with the aggregated state.

    Design §4.4 shows `1/1 patched`, `9/12 partial`, etc. — N reflects
    how many targets are in a "good" state for the record as a whole :

    - If agg_state is `clean` : count targets whose sha-state is `clean`.
    - If agg_state is `patched` : count targets whose sha-state is
      `patched` **OR** `dirty` (cosmetic drift → composite promoted).
    - If agg_state is `partial` : count targets whose sha-state is
      `clean` or `patched` (the ones that already hold a known state).
    - If agg_state is `dirty` / `absent` / `unknown` : count targets whose
      sha-state matches the aggregated state (best-effort).
    """
    total = len(per_target)
    if total == 0:
        return "0/0"
    raw = [pt.get("state", "unknown") for pt in per_target]
    if agg_state == "clean":
        good = sum(1 for s in raw if s == "clean")
    elif agg_state == "patched":
        # Composite detection may promote dirty->patched for cosmetic
        # drift. Treat those targets as "in the patched lane".
        good = sum(1 for s in raw if s in ("patched", "dirty"))
    elif agg_state == "partial":
        good = sum(1 for s in raw if s in ("clean", "patched"))
    else:
        good = sum(1 for s in raw if s == agg_state)
    return f"{good}/{total}"


def _gather_record_state(
    record: dict[str, Any], vendor_root: Path, patches_dir: Path
) -> dict[str, Any]:
    """Evaluate a record and return the shape used by `status` + `describe`."""
    probe = detect.evaluate(record, vendor_root, patches_dir)
    return {
        "id": record.get("id"),
        "severity": record.get("severity"),
        "order": record.get("order"),
        "title": record.get("title"),
        "status_lifecycle": record.get("status"),
        "state": probe["state"],
        "per_target": probe["per_target"],
        "can_auto_3way": probe["can_auto_3way"],
        "drift_hint": probe["drift_hint"],
    }


def _cmd_status(args: argparse.Namespace) -> int:
    """Tabular per-record state (§4.4).

    Flags : ``--id <id>`` (single record), ``--json`` (machine output),
    ``--only-failing`` (filter to dirty/partial/absent).
    """
    _, vendor_root, patches_dir, data = _load_ctx(args)
    records = data.get("records", [])

    if args.id:
        records = [r for r in records if r.get("id") == args.id]
        if not records:
            print(f"no record with id={args.id!r}", file=sys.stderr)
            return 1

    # Resolve state once per record (git calls can be slow).
    states = [
        _gather_record_state(r, vendor_root, patches_dir)
        for r in sorted(records, key=lambda rec: rec.get("order", 0))
    ]
    if args.only_failing:
        states = [s for s in states if s["state"] in ("dirty", "partial", "absent")]

    # Aggregate summary counters.
    summary: dict[str, int] = {}
    for lifecycle in ("active", "disabled", "obsolete"):
        summary[lifecycle] = sum(
            1 for r in records if r.get("status") == lifecycle
        )
    for st in ("clean", "patched", "dirty", "partial", "absent", "unknown"):
        summary[st] = sum(1 for s in states if s["state"] == st)

    vendor_baseline = data.get("vendor_baseline_sha")
    vendor_baseline_status = "ok" if vendor_baseline else "not-recorded"

    if args.json:
        payload = {
            "vendor_baseline": vendor_baseline_status,
            "vendor_baseline_sha": vendor_baseline,
            "summary": summary,
            "records": states,
        }
        json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    if not states:
        print("(empty)")
        return 0

    # Header — column widths taken from §4.4 example (id up to 33 chars).
    header = f"{'ID':<33}  {'SEV':<9}  {'TARGETS':<8}  {'STATE':<9}  ORDER"
    print(header)
    for s in states:
        tgt_frac = _targets_fraction(s["state"], s["per_target"])
        print(
            f"{s['id']:<33}  {s['severity']:<9}  {tgt_frac:<8}  "
            f"{s['state']:<9}  {s['order']}"
        )

    print()
    if vendor_baseline:
        short = vendor_baseline[:8]
        print(f"Vendor baseline: {vendor_baseline_status} (recorded sha {short})")
    else:
        print("Vendor baseline: not-recorded")
    summary_bits = []
    if summary.get("active"):
        summary_bits.append(f"{summary['active']} active")
    for st in ("patched", "clean", "partial", "dirty", "absent"):
        if summary.get(st):
            summary_bits.append(f"{summary[st]} {st}")
    print("Summary: " + " / ".join(summary_bits) if summary_bits else "Summary: (empty)")
    return 0


# -------------------------------------------------------------------------
# `describe <id>` — fiche complète d'un record (§4.1).
# -------------------------------------------------------------------------


def _read_history(patches_dir: Path, order: int, limit: int | None) -> list[dict]:
    """Read patches/history/<order>-history.jsonl if present.

    Each line is a JSON event (§3.2). Returns the last `limit` events if
    set. Missing file -> empty list.
    """
    p = patches_dir / "history" / f"{order}-history.jsonl"
    if not p.exists():
        return []
    events: list[dict] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                # Malformed line — skip silently; verify will flag it.
                continue
    if limit is not None and limit > 0:
        events = events[-limit:]
    return events


def _cmd_describe(args: argparse.Namespace) -> int:
    _, vendor_root, patches_dir, data = _load_ctx(args)
    rec = _record_by_id(data, args.rid)
    if rec is None:
        print(f"no record with id={args.rid!r}", file=sys.stderr)
        return 1

    state_info = _gather_record_state(rec, vendor_root, patches_dir)
    history = _read_history(patches_dir, rec.get("order", 0), args.limit_history)

    if args.json:
        payload = {
            "record": rec,
            "state": state_info["state"],
            "drift_hint": state_info["drift_hint"],
            "can_auto_3way": state_info["can_auto_3way"],
            "per_target": state_info["per_target"],
            "history": history,
        }
        json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    # Text mode — sectioned layout.
    print(f"id            : {rec.get('id')}")
    print(f"order         : {rec.get('order')}")
    print(f"status        : {rec.get('status')}")
    print(f"severity      : {rec.get('severity')}")
    print(f"title         : {rec.get('title')}")
    if rec.get("audit_ref"):
        print(f"audit_ref     : {rec['audit_ref']}")
    print(f"patch_file    : {rec.get('patch_file')}")
    print(f"patch_sha256  : {rec.get('patch_sha256')}")
    print(f"last_applied  : {rec.get('last_applied', '(never)')}")
    print(f"last_result   : {rec.get('last_result', '(never)')}")
    print(f"current state : {state_info['state']}"
          + (f" (drift={state_info['drift_hint']})"
             if state_info["drift_hint"] else ""))
    print(f"can_auto_3way : {state_info['can_auto_3way']}")
    print("targets :")
    for t, pt in zip(rec.get("targets", []), state_info["per_target"]):
        obs_sha = pt.get("sha256") or "(absent)"
        print(f"  - path       : {t.get('path')}")
        print(f"    baseline   : {t.get('baseline_sha256')}")
        print(f"    patched    : {t.get('patched_sha256')}")
        print(f"    observed   : {obs_sha}")
        print(f"    state      : {pt.get('state')}")

    if history:
        print(f"history ({len(history)} event(s)):")
        for ev in history:
            print(f"  - {ev}")
    else:
        print("history       : (no events — not yet externalised in this repo)")
    return 0


# -------------------------------------------------------------------------
# `diff <id>` — show the patch content, optionally coloured.
# -------------------------------------------------------------------------


_ANSI_RED = "\x1b[31m"
_ANSI_GREEN = "\x1b[32m"
_ANSI_CYAN = "\x1b[36m"
_ANSI_RESET = "\x1b[0m"


def _colorize_patch(text: str) -> str:
    out_lines: list[str] = []
    for ln in text.splitlines(keepends=True):
        if ln.startswith("+++ ") or ln.startswith("--- "):
            out_lines.append(ln)
        elif ln.startswith("+"):
            out_lines.append(_ANSI_GREEN + ln.rstrip("\n") + _ANSI_RESET + "\n"
                             if ln.endswith("\n") else
                             _ANSI_GREEN + ln + _ANSI_RESET)
        elif ln.startswith("-"):
            out_lines.append(_ANSI_RED + ln.rstrip("\n") + _ANSI_RESET + "\n"
                             if ln.endswith("\n") else
                             _ANSI_RED + ln + _ANSI_RESET)
        elif ln.startswith("@@"):
            out_lines.append(_ANSI_CYAN + ln.rstrip("\n") + _ANSI_RESET + "\n"
                             if ln.endswith("\n") else
                             _ANSI_CYAN + ln + _ANSI_RESET)
        else:
            out_lines.append(ln)
    return "".join(out_lines)


def _extract_target_paths(patch_text: str) -> list[str]:
    """Return the list of `b/` paths from `+++ b/...` lines in the patch."""
    targets = []
    for ln in patch_text.splitlines():
        if ln.startswith("+++ "):
            # strip `+++ ` and optional `b/` prefix
            p = ln[4:].strip()
            if p.startswith("b/"):
                p = p[2:]
            targets.append(p)
    return targets


def _cmd_diff(args: argparse.Namespace) -> int:
    _, _, patches_dir, data = _load_ctx(args)
    rec = _record_by_id(data, args.rid)
    if rec is None:
        print(f"no record with id={args.rid!r}", file=sys.stderr)
        return 1
    patch_path = patches_dir / rec.get("patch_file", "")
    if not patch_path.exists():
        print(f"patch file not found: {patch_path}", file=sys.stderr)
        return 1

    text = patch_path.read_text(encoding="utf-8")

    if args.targets_only:
        targets = _extract_target_paths(text)
        for t in targets:
            print(t)
        return 0

    use_color = sys.stdout.isatty() and not args.no_color
    if use_color:
        sys.stdout.write(_colorize_patch(text))
    else:
        sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")
    return 0


# -------------------------------------------------------------------------
# `apply` / `rollback` — call the engines from apply.py / rollback.py.
# -------------------------------------------------------------------------


def _apply_one(
    rec, series_path, vendor_root, patches_dir, data, args, runtime,
):
    """Invoke apply_patch with the current CLI flags. Shared between
    single-id `apply` and `apply --all`.
    """
    return apply_mod.apply_patch(
        rec, vendor_root, patches_dir,
        dry_run=args.dry_run, yes=args.yes,
        interactive=getattr(args, "interactive", False),
        force=getattr(args, "force", False),
        auto_3way=getattr(args, "auto_3way", False),
        registry_path=series_path if not args.dry_run else None,
        all_records=data if not args.dry_run else None,
        runtime=runtime,
        stream=sys.stdout,
    )


def _cmd_apply(args: argparse.Namespace) -> int:
    series_path, vendor_root, patches_dir, data = _load_ctx(args)
    runtime = runtime_mod.load_runtime(patches_dir)

    if getattr(args, "all", False):
        return _cmd_apply_all(
            args, series_path, vendor_root, patches_dir, data, runtime,
        )

    if not args.rid:
        print("apply: missing record id (or use --all)", file=sys.stderr)
        return 2
    rec = _record_by_id(data, args.rid)
    if rec is None:
        print(f"no record with id={args.rid!r}", file=sys.stderr)
        return 1

    with _patches_flock(patches_dir) if not args.dry_run else contextlib.nullcontext():
        result = _apply_one(
            rec, series_path, vendor_root, patches_dir, data, args, runtime,
        )
    print(result["message"])
    return 0 if result["success"] else 1


def _cmd_apply_all(
    args, series_path, vendor_root, patches_dir, data, runtime,
) -> int:
    """Apply every ``active`` record in ascending ``order`` (§2 lines 106-109).

    - ``--stop-on-fail`` : break on the first failure.
    - Without it : continue, collect errors, exit 1 if any record failed.
    - ``q`` in the interactive menu sets ``result["quit"]`` — we break
      iteration but treat the run as user-aborted (exit 0, no failure).
    - Flock is acquired once for the whole iteration (§5.7).
    """
    records = [
        r for r in data.get("records", [])
        if r.get("status", "active") == "active"
    ]
    records.sort(key=lambda r: r.get("order", 0))

    applied = skipped = failed = 0
    errors: list[str] = []
    user_quit = False

    ctx = (
        _patches_flock(patches_dir)
        if not args.dry_run
        else contextlib.nullcontext()
    )
    with ctx:
        for rec in records:
            result = _apply_one(
                rec, series_path, vendor_root, patches_dir, data, args, runtime,
            )
            print(result["message"])
            if result.get("quit"):
                user_quit = True
                break
            if result["success"]:
                if result.get("noop"):
                    skipped += 1
                else:
                    applied += 1
            else:
                failed += 1
                errors.append(result["message"])
                if getattr(args, "stop_on_fail", False):
                    break

    print(
        f"apply --all: {applied} applied, {skipped} skipped, {failed} failed"
        + (" (user quit)" if user_quit else "")
    )
    if user_quit:
        return 0
    return 0 if failed == 0 else 1


def _rollback_one(
    rec, series_path, vendor_root, patches_dir, data, args, runtime,
):
    return rb_mod.rollback_patch(
        rec, vendor_root, patches_dir,
        dry_run=args.dry_run, yes=args.yes,
        registry_path=series_path if not args.dry_run else None,
        all_records=data if not args.dry_run else None,
        runtime=runtime,
    )


def _cmd_rollback(args: argparse.Namespace) -> int:
    series_path, vendor_root, patches_dir, data = _load_ctx(args)
    runtime = runtime_mod.load_runtime(patches_dir)

    if getattr(args, "all", False):
        return _cmd_rollback_all(
            args, series_path, vendor_root, patches_dir, data, runtime,
        )

    if not args.rid:
        print("rollback: missing record id (or use --all)", file=sys.stderr)
        return 2
    rec = _record_by_id(data, args.rid)
    if rec is None:
        print(f"no record with id={args.rid!r}", file=sys.stderr)
        return 1

    with _patches_flock(patches_dir) if not args.dry_run else contextlib.nullcontext():
        result = _rollback_one(
            rec, series_path, vendor_root, patches_dir, data, args, runtime,
        )
    print(result["message"])
    return 0 if result["success"] else 1


def _cmd_rollback_all(
    args, series_path, vendor_root, patches_dir, data, runtime,
) -> int:
    """Pop records in descending order (design §4.1 line 307, verbatim)."""
    records = [
        r for r in data.get("records", [])
        if r.get("status", "active") == "active"
    ]
    records.sort(key=lambda r: r.get("order", 0), reverse=True)

    rolled = failed = skipped = 0
    ctx = (
        _patches_flock(patches_dir)
        if not args.dry_run
        else contextlib.nullcontext()
    )
    with ctx:
        for rec in records:
            # Skip records whose last_result isn't "patched" — the guard
            # in rollback_patch already handles this, but skipping pre-
            # hand produces cleaner output for --all.
            if rec.get("last_result") != "patched":
                skipped += 1
                print(f"[{rec.get('id')}] skip (last_result != 'patched')")
                continue
            result = _rollback_one(
                rec, series_path, vendor_root, patches_dir, data, args, runtime,
            )
            print(result["message"])
            if result["success"]:
                rolled += 1
            else:
                failed += 1
                if getattr(args, "stop_on_fail", False):
                    break

    print(
        f"rollback --all: {rolled} reverted, {skipped} skipped, {failed} failed"
    )
    return 0 if failed == 0 else 1


# -------------------------------------------------------------------------
# `verify` — stub until jalon 9/10 (REV-0004 note #5).
# -------------------------------------------------------------------------


def _cmd_verify(args: argparse.Namespace) -> int:
    """Integrity + drift + coherence checks (design §2.3, §4.1 line 309).

    Exit codes per design §4.1 (verbatim): 0 ok, 1 failure, 3 invalid
    registry.
    """
    _, vendor_root, patches_dir, data = _load_ctx(args)
    return verify_mod.verify(
        data, vendor_root, patches_dir,
        json_output=getattr(args, "json", False),
        strict=getattr(args, "strict", False),
        stream=sys.stdout,
    )


def _cmd_refresh(args: argparse.Namespace) -> int:
    """Recompute baseline / patched sha256 from current vendor state.

    Design §4.1 line 308 (verbatim) + §7 item 10 (verbatim).
    """
    series_path, vendor_root, patches_dir, data = _load_ctx(args)
    rec = _record_by_id(data, args.rid)
    if rec is None:
        print(f"no record with id={args.rid!r}", file=sys.stderr)
        return 2  # unknown id → argv-like invocation error

    result = refresh_mod.refresh_record(
        rec, vendor_root, patches_dir,
        dry_run=args.dry_run, yes=args.yes,
        registry_path=series_path if not args.dry_run else None,
        all_records=data if not args.dry_run else None,
        stream=sys.stdout,
    )
    if not result["success"]:
        print(result["message"], file=sys.stderr)
        return 1
    return 0


# -------------------------------------------------------------------------
# Other stubs (`record`) — deferred to jalon 11/12.
# -------------------------------------------------------------------------


def _cmd_not_implemented(name: str, jalon: str) -> int:
    print(
        f"patch-system: command '{name}' not yet implemented "
        f"(design §7 — {jalon})",
        file=sys.stderr,
    )
    return 2


# -------------------------------------------------------------------------
# Argparse construction.
# -------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="patch-system",
        description="Manage local patches on vendor/obsidian-wiki.",
    )
    # REV-0004 note #1 : --series is TOP-LEVEL, not per-subcommand.
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

    # list
    p_list = sub.add_parser("list", help="List records from the registry.")
    p_list.add_argument("--json", action="store_true", help="JSON output.")
    p_list.add_argument(
        "--status",
        dest="status_filter",
        choices=["active", "disabled", "obsolete"],
        default=None,
        help="Filter by lifecycle status.",
    )

    # status
    p_st = sub.add_parser("status", help="Per-record live detection state.")
    p_st.add_argument("--json", action="store_true", help="JSON output.")
    p_st.add_argument("--id", default=None, help="Filter to one record id.")
    p_st.add_argument(
        "--only-failing",
        action="store_true",
        help="Show only records in dirty/partial/absent state.",
    )

    # describe <id>
    p_desc = sub.add_parser("describe", help="Full fiche for a single record.")
    p_desc.add_argument("rid", metavar="id", help="Record id.")
    p_desc.add_argument("--json", action="store_true")
    p_desc.add_argument(
        "--limit-history",
        type=int,
        default=None,
        help="Limit the history block to the last N events.",
    )

    # diff <id>
    p_diff = sub.add_parser("diff", help="Show the patch content.")
    p_diff.add_argument("rid", metavar="id")
    p_diff.add_argument("--no-color", action="store_true")
    p_diff.add_argument(
        "--targets-only",
        action="store_true",
        help="Only print the list of targets touched by the patch.",
    )

    # apply <id> | apply --all
    p_apply = sub.add_parser(
        "apply",
        help="Apply a patch (or --all for the whole series).",
    )
    p_apply.add_argument("rid", metavar="id", nargs="?", default=None)
    p_apply.add_argument("--dry-run", action="store_true")
    p_apply.add_argument("--yes", action="store_true")
    p_apply.add_argument(
        "--interactive", action="store_true",
        help="Force the §4.2 arbitration menu even on clean states.",
    )
    p_apply.add_argument(
        "--force", action="store_true",
        help="Implicit 'y' on every ambiguous state (overwrite local).",
    )
    p_apply.add_argument(
        "--auto-3way", dest="auto_3way", action="store_true",
        help="Opt-in (§5.5): try git apply --3way --index before prompting.",
    )
    p_apply.add_argument(
        "--all", action="store_true",
        help="Apply every active record in order.",
    )
    p_apply.add_argument(
        "--stop-on-fail", dest="stop_on_fail", action="store_true",
        help="With --all: stop at the first failure.",
    )

    # rollback <id> | rollback --all
    p_rb = sub.add_parser(
        "rollback",
        help="Reverse-apply a patch (or --all to pop the whole stack).",
    )
    p_rb.add_argument("rid", metavar="id", nargs="?", default=None)
    p_rb.add_argument("--dry-run", action="store_true")
    p_rb.add_argument("--yes", action="store_true")
    p_rb.add_argument(
        "--all", action="store_true",
        help="Reverse every applied record in descending order.",
    )
    p_rb.add_argument(
        "--stop-on-fail", dest="stop_on_fail", action="store_true",
        help="With --all: stop at the first failure.",
    )

    # verify
    p_ver = sub.add_parser(
        "verify",
        help="Integrity + drift + target coherence (design §4.1).",
    )
    p_ver.add_argument("--json", action="store_true", help="JSON output.")
    p_ver.add_argument(
        "--strict",
        action="store_true",
        help="Upgrade drift warnings to failures (exit 1).",
    )

    # refresh <id>
    p_ref = sub.add_parser(
        "refresh",
        help="Recompute baseline/patched sha256 from current state.",
    )
    p_ref.add_argument("rid", metavar="id")
    p_ref.add_argument("--dry-run", action="store_true")
    p_ref.add_argument("--yes", action="store_true")

    # record stub (jalon 11+ — scope of future work).
    p_rec = sub.add_parser("record", help="(not yet implemented — jalon 12)")
    p_rec.add_argument("rid", metavar="id")
    p_rec.add_argument("--from", dest="from_path")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    dispatch = {
        "list": _cmd_list,
        "status": _cmd_status,
        "describe": _cmd_describe,
        "diff": _cmd_diff,
        "apply": _cmd_apply,
        "rollback": _cmd_rollback,
        "verify": _cmd_verify,
        "refresh": _cmd_refresh,
    }
    handler = dispatch.get(args.cmd)
    if handler is not None:
        return handler(args)

    if args.cmd == "record":
        return _cmd_not_implemented("record", "jalon 12")

    parser.error(f"unknown command: {args.cmd}")
    return 2  # unreachable
