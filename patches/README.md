# patches/ — local patch registry for vendor/obsidian-wiki

> **Audience** : maintainer of the super-repo who adds, removes, or
> inspects anomalies tracked against the vendored obsidian-wiki skills.
> For day-to-day usage (how to run the CLI, what each state means),
> see `scripts/docs/` (tutorial / how-to / reference / explanation).

## Layout (design §3.1 — verbatim)

```
patches/
  series.json                                # registre logique ordonne
  runtime.json                               # config d'execution par patch
  .lock                                      # flock pour concurrence (§5.7)
  0001-wiki-ingest-raw-fallback.patch        # diff unifie + header DEP-3
  0002-wiki-ingest-security-check.patch
  0003-vendor-env-remove.patch
  0004-vendor-env-subsumed.patch
  0005-read-dotenv-wording.patch             # p2 — 12 targets (voir §5.1)
  0006-raw-in-vault-wording.patch            # p2 — 6 targets (voir §5.1)
  ...
  history/                                   # audit trail (decharge de series.json)
    0001-history.jsonl                       # 1 record d'historique par ligne
    0002-history.jsonl
    ...
  archive/                                   # patches retires (status obsolete)
    ...
```

**Convention co-located** : `patches/series.json` is the registry ; the
`.patch` files sit next to it, named `<NNNN>-<slug>.patch` where `NNNN`
is the record's `order` field zero-padded to 4 digits. The CLI finds
them via `PATCH_SYSTEM_ROOT/patches/` — any other layout breaks the
dispatcher.

`runtime.json` (design §3.3) is not yet emitted by any engine and is
reserved for Phase-4 overrides.

## How to add a new patch

Follow these steps in order. **Never hand-edit `series.json` first** —
the `.patch` header's SHAs are the source of truth, the registry is
derived.

1. **Detect the anomaly.** Refer to
   `docs/260418-dual-sensitivity-analysis.md` for the canonical list.
   Note the audit code (ex. B3, B4, p2-xxx) and the severity.
2. **Generate the `.patch`.** Either manually (`diff -u original
   modified > patches/NNNN-slug.patch`) or via `git diff --no-prefix`
   on the vendor working tree. The filename must start with a 4-digit
   `order` zero-padded to match the `order` field you will put in
   series.json.
3. **Prepend a DEP-3 header** (design §3.4). Required fields :
   `Description:` (first line is the short title, following indented
   lines are the long description), `Origin:` (vendor|upstream|local),
   `Bug-Ref:` (audit pointer), `Forwarded:`, `Last-Update:`. Enriched
   extension fields (prefix `X-*`, design §5.4) :
   `X-Patch-Id:` (the kebab-case id used in series.json),
   `X-Audit-Ref:`, `X-Severity:`, `X-Baseline-Sha256:`,
   `X-Patched-Sha256:`. Separate header from body with a single line
   containing `---`.
4. **Compute the SHAs** :
   - `baseline_sha256` : `sha256sum` of the target file BEFORE applying.
   - `patched_sha256` : `sha256sum` of the target file AFTER applying.
   - `patch_sha256` : `sha256sum` of the `.patch` file itself.
5. **Add a record to `series.json`.** Match the schema in design §3.2
   (verbatim) : mandatory fields are `id, order, status, severity,
   title, patch_file, patch_sha256, targets[]`. Each `targets[]` entry
   needs `path`, `baseline_sha256`, `patched_sha256`. Optional fields :
   `audit_ref, last_applied, last_result, notes`.
6. **Validate.** Run :
   ```
   scripts/patch-system verify
   scripts/patch-system status
   scripts/patch-system apply <id> --dry-run
   ```
   - `verify` recomputes `patch_sha256` and checks target coherence.
   - `status` confirms the initial state is `clean` (pre-patch).
   - `apply --dry-run` runs `git apply --check` ; if it fails with
     "does not exist in index", the target is gitignored in the vendor
     repo — see the "gitignored targets" caveat below.
7. **Commit** `series.json` + the new `.patch` in the super-repo. The
   vendor working tree itself stays untouched (design §5.3 — vendor
   stays pristine ; patches are regenerated on demand).

## How to retire a patch

Per design §3.1, patches are never deleted from the tree ; they are
moved to `patches/archive/` and their record flips to
`status: obsolete` :

1. Flip `status` to `"obsolete"` in the record.
2. Move the `.patch` file to `patches/archive/NNNN-slug.patch`.
3. Update `patch_file` to `"archive/NNNN-slug.patch"` (or leave it
   pointing at the archived path — the dispatcher prefixes
   `patches_dir`).
4. Run `scripts/patch-system verify` to confirm nothing else references
   the archived record.
5. Commit the move.

Keeping obsolete records visible lets future maintainers see why a
particular fix was introduced, even if the upstream later fixed it.

## Caveats

### B3 deviation — vendor/.env is gitignored

The audit B3 recommended **option A** (delete `vendor/obsidian-wiki/.env`
entirely). The pilot record `b3-vendor-env-remove` opts instead for
**option B** (blank the hardcoded value) because the vendor repo's
`.gitignore` marks `.env` as gitignored :

- A pure delete patch can only be expressed against an untracked
  working-tree file.
- The jalon-6 apply engine uses `git apply --index`, which requires
  the target to exist in the vendor repo's index. Untracked files fail
  fast with `error: <file>: does not exist in index`.
- Consequence : `apply b3-vendor-env-remove --dry-run` currently
  returns **exit 1** with that error. This is a known framework
  limitation (the `--index` flag is hard-coded in `apply.py` / `detect.py`
  — future jalon will allow opting out per-record via `runtime.json`
  overrides, design §3.3).
- Workaround for now : apply B3 manually with `patch -p1 <
  patches/0003-vendor-env-remove.patch` from the vendor tree, or wait
  for the jalon-14 `runtime.json` override path to disable `--index`
  per record.

The DEP-3 header of `0003-vendor-env-remove.patch` documents the
deviation inline (`Description:` block).

### Detection of gitignored targets

`scripts/patch-system status` detects the state correctly for
gitignored files — the sha-256-based detector in
`scripts/patch_system/detect.py` does not require the file to be
git-tracked. Only the `apply` / `rollback` paths currently require
`--index` and therefore a tracked file.

## Related docs

- `docs/260420-patch-system-design.md` — authoritative design.
- `docs/260418-dual-sensitivity-analysis.md` — audit of anomalies.
- `docs/adr/ADR-0001-vendor-submodule-pristine.md` — why the vendor
  tree stays pristine.
- `scripts/docs/tutorial.md`, `how-to.md`, `reference.md`,
  `explanation.md` — user-facing docs.
