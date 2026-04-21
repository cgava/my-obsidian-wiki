# tests/fixtures — patch-system test fixtures

Reusable fixture tree for `tests/test_detect.py`, `tests/test_registry.py`
and follow-up jalons (apply / rollback / cli).

## Layout

```
fixtures/
  vendor-mini/            pristine vendor tree (5 files)
    README.md             (3 lines)
    bin/cmd1.sh           (5 lines bash)
    bin/cmd2.sh           (9 lines bash — includes a top blank line
                          that simulates a cosmetic upstream drift
                          vs. patch 0003's recorded baseline)
    config/.env.example   (3 lines)
    lib/helper.py         (8 lines python)

  vendor-mini-patched/    same tree, with patches 0001 + 0002 applied
                          (cmd2.sh is the "patched + blank-line drift"
                          variant — sha ≠ patched_sha256 on 0003)

  patches/
    0001-readme-add-section.patch       applies cleanly on README.md
    0002-cmd1-fix-typo.patch            applies cleanly on bin/cmd1.sh
    0003-cmd2-drifted.patch             cosmetic drift — `git apply
                                        --check` succeeds on vendor-mini
                                        (offset 1 line) despite sha
                                        mismatch, `--reverse --check`
                                        succeeds on vendor-mini-patched.
    0004-cmd2-semantic-drift.patch      2-hunk patch — hunk 1 still
                                        matches, hunk 2 references
                                        "cmd2 line three RENAMED_UPSTREAM"
                                        which no longer exists →
                                        `partial` via per-hunk split.

  series.json             registry pointing at the 4 patches above, with
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

## Expected detection states — sha256-only (`detect.detect_state`)

| vendor_root used          | 0001    | 0002    | 0003  | 0004  |
|---------------------------|---------|---------|-------|-------|
| `vendor-mini/`            | clean   | clean   | dirty | dirty |
| `vendor-mini-patched/`    | patched | patched | dirty | dirty |

Rationale:
- 0003's baseline/patched shas refer to a *pristine* (no top blank line)
  cmd2.sh that does not exist as an on-disk fixture — it is only the
  conceptual pre-drift reference. Both vendor-mini and vendor-mini-patched
  carry a blank-line-drifted variant → neither sha matches → `dirty`.
- 0004's patched_sha256 is a placeholder (all zeros) because the semantic
  drift means the "after apply" state is not reachable.

## Expected detection states — composite (`detect.evaluate`, jalon 5)

| vendor_root used          | 0001  | 0002  | 0003                          | 0004                    |
|---------------------------|-------|-------|-------------------------------|-------------------------|
| `vendor-mini/`            | clean | clean | clean (cosmetic, forward)     | partial (hunk 1 only)   |
| `vendor-mini-patched/`    | patched | patched | patched (cosmetic, reverse) | partial (hunk 1 only)   |

`evaluate()` falls back to `git apply --check` when sha-based aggregation
is `dirty` :

- Forward `git apply --check` succeeds → `state="clean"`,
  `drift_hint="cosmetic"`. The patch would still apply forward, so the
  file is in a *pre-patch* compatible state with cosmetic drift on the
  baseline — lifecycle is `clean`.
- Reverse `git apply --reverse --check` succeeds → `state="patched"`,
  `drift_hint="cosmetic"`. The patch can still be reverted, so the file
  is in a *post-patch* compatible state with cosmetic drift on the
  patched side — lifecycle is `patched`.
- Neither succeeds but per-hunk split finds some applyable hunks →
  `state="partial"`, `drift_hint="semantic"`.
- All hunks fail → `state="dirty"`, `drift_hint="semantic"`.

`can_auto_3way` is `True` for 0003 in both trees (trivial 3way via offset),
`False` for 0004 (semantic mismatch on hunk 2).

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
