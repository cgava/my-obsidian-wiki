### REV-0001

- **date**     : 2026-04-16
- **subject**  : kiss-executor task -- Phase 1 design document (link-fixer-design.md)
- **verdict**  : approved-with-notes

**Summary**
Design document correctly identifies the three wikilink sub-formats, frontmatter `sources` references, and manifest entries. The four broken link types (A-D) are confirmed against the actual vault contents. CLI design is pragmatic and the dry-run report format is clear. A few gaps and one inaccuracy found.

**Issues**
- [minor] Missing broken reference `_raw/prompt-engineering-notes.md` in `skills/prompt-engineering-techniques.md` sources -- file does not exist anywhere in the vault. The tool should warn on "file not found" cases but this reference should be listed in section 2.1.
- [minor] Section 1.1 states "No embed syntax (`![[...]]`) was found" -- one instance exists in `_raw/s2/2026-04/my-corpus-ai/doc/archives/process/image-handling.md`. Correct for curated wiki pages but the claim is imprecise.
- [minor] Tech stack (3.7) lists `pyyaml` but also says "no external dependencies (stdlib only)". `pyyaml` is not stdlib. Design should commit to one approach: either require pyyaml or use regex/manual YAML parsing for the simple `sources:` field. Given the simple structure, manual parsing is fine and keeps the zero-dependency promise.
- [minor] No `--backup` or undo mechanism mentioned. A simple `.bak` or git-dirty check before writing would be prudent for Phase 2.
- [minor] The affected file list in Type A claims "14 occurrences" but lists 17 files. Likely 14 unique source paths across 17 files (some share the same stale path). Clarify the counting.

**For kiss-orchestrator**
Proceed to next step -- issues are all minor and can be addressed at implementation time.

### REV-0002

- **date**     : 2026-04-16
- **subject**  : kiss-executor task -- Phase 2 implementation fix-links.py
- **verdict**  : approved-with-notes

**Summary**
Script is well-structured, stdlib-only, implements all 9 CLI flags from the design, and correctly handles the three wikilink formats and five frontmatter source variants. The resolution algorithm (discover old paths, compute changes, apply or dry-run report) matches the design spec. A few minor edge-case gaps found, none blocking for the current vault.

**Issues**
- [minor] No fenced code block detection -- wikilinks inside ``` blocks would be incorrectly replaced. Not a problem today (no such cases in the vault), but fragile for future use.
- [minor] Multi-line frontmatter regex `^  - (.+)$` (line 291) matches all `  - ` items in frontmatter, not only those under `sources:`. Safe now (no other list fields contain file paths) but could cause false positives if frontmatter evolves.
- [minor] Non-`.md` extensions stripped in wikilink replacement (line 448 uses `new_no_ext`). A wikilink `[[file.json]]` would become `[[path/file]]` without `.json`. Obsidian needs the extension for non-md files. Only affects `_archives`/`_raw` files currently, so no practical impact.
- [minor] `apply_changes` uses `str.replace()` without scoping frontmatter changes to the frontmatter block -- a frontmatter path appearing verbatim in body text would also be replaced. Low risk given path formats.
- [minor] Design mentions preserving original quoting style in YAML. The replacement preserves surrounding quotes (since only the path inside is swapped), but does not explicitly track or enforce quote style. Works correctly in practice.

**For kiss-orchestrator**
Proceed to next step -- all issues are minor and do not affect correctness for the current vault.
