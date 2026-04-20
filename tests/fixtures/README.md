# tests/fixtures — patch-system test fixtures

Reusable fixture tree for `tests/test_detect.py`, `tests/test_registry.py`
and follow-up jalons (apply / rollback).

## Layout

```
fixtures/
  vendor-mini/            pristine vendor tree (5 files)
    README.md             (3 lines)
    bin/cmd1.sh           (5 lines bash)
    bin/cmd2.sh           (5 lines bash, already drifted from the patch baseline)
    config/.env.example   (3 lines)
    lib/helper.py         (8 lines python)

  vendor-mini-patched/    same tree, with patches 0001 + 0002 applied
                          (cmd2.sh unchanged — patch 0003 would not apply)

  patches/
    0001-readme-add-section.patch    applies cleanly on README.md
    0002-cmd1-fix-typo.patch         applies cleanly on bin/cmd1.sh
    0003-cmd2-drifted.patch          baseline sha does not match vendor -> dirty

  series.json             registry pointing at the 3 patches above, with
                          per-record patch_sha256 and per-target
                          baseline_sha256 / patched_sha256 pre-computed
                          (schema aligned with design §3.2)

  _compute_sha.sh         helper to regenerate the expected sha256 values
                          if any fixture file is edited
```

## Schema alignment — design §3.2

The fixture `series.json` follows the design doc schema:

- Top-level : `{"schema_version": "1", "records": [...]}`.
- Mandatory record fields : `id`, `order`, `status` (lifecycle), `severity`,
  `title`, `patch_file`, `patch_sha256`, `targets[]`.
- Mandatory target fields : `path`, `baseline_sha256`, `patched_sha256`
  (no `x_*` prefix — that prefix only appears in DEP-3 patch headers).
- Severity enum : `BLOCKING | TROMPEUR | COSMETIQUE | INFO`.
- Status enum : `active | disabled | obsolete`.

Example record:

```json
{
  "id": "t0001-readme-add-section",
  "order": 1,
  "status": "active",
  "severity": "COSMETIQUE",
  "title": "README — add local notes section",
  "audit_ref": "tests/fixtures/README.md#0001",
  "patch_file": "0001-readme-add-section.patch",
  "patch_sha256": "c5ddbe71...",
  "targets": [
    {
      "path": "vendor/obsidian-wiki/README.md",
      "baseline_sha256": "8dfa1bea...",
      "patched_sha256": "2d3f1545..."
    }
  ]
}
```

## Expected detection states

Point `detect.detect_state(record, vendor_root)` at one of the two vendor
trees:

| vendor_root used          | patch 0001 | patch 0002 | patch 0003 |
|---------------------------|------------|------------|------------|
| `vendor-mini/`            | clean      | clean      | dirty      |
| `vendor-mini-patched/`    | patched    | patched    | dirty      |

Patch 0003 is `dirty` on both trees because its recorded baseline/patched
sha256 are placeholder zeros/ones that do not match any real file — this
simulates an upstream drift where the patch no longer applies.

## Regenerating the hashes

If you edit any fixture file, run:

```bash
tests/fixtures/_compute_sha.sh
```

and manually update:
- `tests/fixtures/series.json` (target `baseline_sha256` / `patched_sha256`
  + record `patch_sha256` for each edited `.patch` file)
- the `X-Baseline-Sha256` / `X-Patched-Sha256` headers in the relevant
  `tests/fixtures/patches/*.patch` (DEP-3 headers still use the X-* prefix)
