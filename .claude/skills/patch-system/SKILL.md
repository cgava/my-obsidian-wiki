---
name: patch-system
description: Apply, rollback, verify, refresh and audit quilt-style local patches over a pristine vendored tree. Triggers on "patch-system", "patch apply", "patch rollback", "patches/series", "quilt-style patches", "vendor drift", "b1/b2/b3 patches", "DEP-3 patches", or any mention of the local patch registry stored under `patches/`.
---

# patch-system

Local, idempotent patch manager inspired by **quilt + DEP-3** and **Gentoo `etc-update`**. Corrects anomalies in a vendored tree (`vendor/obsidian-wiki`) without touching upstream: patches live in the super-repo under `patches/`, the vendor working tree stays pristine, and patches are re-applied on demand.

## When to invoke

Trigger this skill whenever the user:
- asks to **apply / rollback / refresh / verify / list / describe / diff** a patch
- mentions `patches/series.json`, `patches/runtime.json`, `.rej` files, DEP-3 headers
- reports **drift** between the vendored tree and registered baselines
- needs to **audit** the state of the local patch registry (`status`, `verify`)
- asks to add a new patch (workflow is in `patches/README.md`, CLI used is this skill)

## CLI — entrypoint

```bash
.claude/skills/patch-system/scripts/patch-system <subcommand> [args]
```

The shim resolves `PATCH_SYSTEM_ROOT` via a layered strategy:
1. `$PATCH_SYSTEM_ROOT` env override
2. walk up from `$(pwd)` looking for `patches/series.json`
3. `git rev-parse --show-toplevel`
4. `$(pwd)` (last resort)

Mutating subcommands (`apply`, `rollback`, `refresh`, `record`) acquire a `flock` on `patches/.lock`; read-only subcommands do not.

## Subcommands at a glance

| Command | Purpose | Mutates |
|---|---|---|
| `list` | Show registry records (id, status, severity, title) | no |
| `status` | Detect per-target state (`clean` / `patched` / `partial` / `dirty` / `absent` / `unknown`) | no |
| `describe <id>` | Full record dump + DEP-3 header | no |
| `diff <id>` | Show the raw `.patch` body | no |
| `verify [--json] [--strict]` | Check `patch_sha256`, vendor drift, target coherence | no |
| `apply <id> [--dry-run] [--interactive] [--force] [--auto-3way]` | Apply one patch | yes |
| `apply --all [--stop-on-fail]` | Apply every `active` record in order | yes |
| `rollback <id> [--dry-run]` / `rollback --all` | Reverse a patch (refuses unless `last_result=patched`) | yes |
| `refresh <id> [--dry-run] [--yes]` | Recompute `baseline_sha256` or `patched_sha256` based on current state | yes |
| `record <id>` | (stub, J12 not yet implemented — returns exit 2) | yes |

Global flags: `--series <path>`, `--vendor-root <path>` (before the subcommand).

## Typical flows

**Check before you change anything:**
```bash
patch-system verify           # integrity + drift
patch-system status           # per-target state
patch-system apply b3 --dry-run
```

**Apply a specific patch, interactively:**
```bash
patch-system apply b3-vendor-env-remove --interactive
# prompts y/n/s/d/3/r/q/? — etc-update style
```

**Batch-apply every active record, fail-fast:**
```bash
patch-system apply --all --stop-on-fail
```

**Rollback to pristine state:**
```bash
patch-system rollback --all
```

## Deeper documentation (progressive disclosure)

Do **not** dump the whole diataxis stack into context upfront. Load only what the task needs:

| Need | File |
|---|---|
| First-time walk-through on fixtures (~15 min) | `references/tutorial.md` |
| "How do I do X?" recipes (batch, interactive, gitignored, refresh…) | `references/how-to.md` |
| Exit codes, JSON schemas, state semantics, all flags | `references/reference.md` |
| Why this design: vendor pristine, composite detection, no auto-commit, runtime.json split | `references/explanation.md` |

## Key design invariants (do not violate)

- **Vendor tree stays pristine.** Never commit changes to `vendor/obsidian-wiki/`; patches are stored in the super-repo and re-applied on demand.
- **`series.json` is logical registry; `runtime.json` is execution strategy.** They are *separate* (ADR-0002). Never mix schema evolution into the other.
- **`.patch` header SHAs are the source of truth**, `series.json` is derived. When they disagree, trust the header and run `refresh`.
- **`flock` mandatory for mutating commands.** The shim handles this; never call `python3 -m patch_system apply` directly unless you know what you're doing.
- **No auto-commit.** The tool never invokes `git commit` — user decides when to commit.

## Tests

The skill ships its own pytest suite under `tests/`. Run from the skill root:

```bash
cd .claude/skills/patch-system
python -m pytest tests/
```

Tests bootstrap `sys.path` themselves; no external install required. One E2E test (`test_b3_runtime_override.py`) uses `git rev-parse` to find the invoking project root and skips if `vendor/obsidian-wiki/.env` is absent.

## Upstream pointers

Authoritative design docs live *outside* the skill (they predate it and are historically frozen):

- `docs/260420-patch-system-design.md` — design §2 architecture, §3 storage, §4 CLI UX, §5 open points, §7 milestone plan
- `docs/260420-patch-system-soa.md` — state of the art (quilt / DEP-3 / etc-update / Ansible / Puppet comparison)
- `docs/adr/ADR-0001-vendor-submodule-pristine.md`
- `docs/adr/ADR-0002-registre-runtime-separation.md`
- `patches/README.md` — maintainer guide for adding/retiring patches
