# Obsidian Link Fixer -- Phase 1 Design

## 1. Link Format Analysis

### 1.1 Wikilinks in body text

All wikilinks in the vault follow the `[[target|alias]]` pattern. Three sub-formats are used:

| Format | Example (real) | Count pattern |
|--------|---------------|---------------|
| `[[path/name\|Alias]]` | `[[concepts/personal-knowledge-management\|PKM]]` | Most common -- used for all cross-category links |
| `[[path/name]]` | `[[obsidian-knowledge-management]]` | Used in Sources sections, no alias |
| `[[name]]` | `[[llm-patterns]]` | Bare filename, no folder prefix -- Sources sections only |

No `[[name#heading]]` or `[[name#heading\|alias]]` anchor links were found. No embed syntax (`![[...]]`) was found.

### 1.2 Frontmatter properties containing file references

| Property | Format | Example (real) |
|----------|--------|----------------|
| `sources` | YAML list of relative paths (no `[[]]`) | `sources: [_raw/llm-patterns.md]` |
| `sources` | YAML list with quotes | `sources: ["_raw/meeting-transcript-km-system.md"]` |
| `sources` | Multi-line YAML list | `sources:\n  - _raw/obsidian-knowledge-management.md` |
| `sources` | External path (non-vault) | `sources: [/home/omc/workspace/my-obsidian-wiki]` |
| `sources` | Claude project path | `sources: ["~/.claude/projects/-home-omc-workspace-kiss-claw"]` |

No other frontmatter properties contain file references (no `related`, `parent`, `children` fields).

### 1.3 Markdown links

Standard markdown links `[text](path.md)` are present only in `_raw/` files (imported documents), not in the curated wiki pages. These are not Obsidian-managed and should be excluded from repair scope.

### 1.4 .manifest.json references

The `.manifest.json` file contains source paths and page paths that mirror the frontmatter `sources` field. This file should also be updated when files move.

---

## 2. Broken Link Patterns Identified

### 2.1 Moved files and their current locations

| Original path (referenced) | Current path (actual) |
|---|---|
| `_raw/llm-patterns.md` | `_raw/s0/2026-04/llm-patterns.md` |
| `_raw/obsidian-knowledge-management.md` | `_raw/s0/2026-04/obsidian-knowledge-management.md` |
| `_raw/agent-skills-architecture.md` | `_raw/s0/2026-04/agent-skills-architecture.md` |
| `_raw/meeting-transcript-km-system.md` | `_raw/s0/2026-04/meeting-transcript-km-system.md` |
| `_raw/chatgpt-export-documentation-practices.json` | `_raw/s0/2025-04/chatgpt-export-documentation-practices.json` |

### 2.2 Broken link types found

**Type A -- Frontmatter `sources` with stale path (14 occurrences)**

Files affected: `concepts/knowledge-graph.md`, `concepts/retrieval-augmented-generation.md`,
`concepts/personal-knowledge-management.md`, `concepts/chain-of-thought.md`,
`concepts/skill-routing.md`, `concepts/skill-based-architecture.md`, `concepts/tool-use.md`,
`concepts/zettelkasten.md`, `concepts/wiki-governance.md`, `concepts/documentation-metrics.md`,
`entities/obsidian.md`, `entities/langchain.md`, `skills/prompt-engineering-techniques.md`,
`skills/architecture-decision-records.md`, `synthesis/agents-vs-chatbots.md`,
`synthesis/llm-knowledge-systems.md`, `synthesis/documentation-as-code.md`.

```yaml
# BROKEN -- file no longer at this path
sources: [_raw/llm-patterns.md]

# FIXED -- actual location
sources: [_raw/s0/2026-04/llm-patterns.md]
```

**Type B -- Wikilink body text with bare filename (no folder prefix)**

Files affected: same set as above, in their `## Sources` sections.

```markdown
# BROKEN -- Obsidian can't resolve, no file at vault root
- [[obsidian-knowledge-management]] -- Source on Obsidian as a PKM tool

# FIXED -- full relative path
- [[_raw/s0/2026-04/obsidian-knowledge-management]] -- Source on Obsidian as a PKM tool
```

Bare-name wikilinks found for:
- `[[obsidian-knowledge-management]]` (4 files)
- `[[llm-patterns]]` (6 files)
- `[[agent-skills-architecture]]` (4 files)

**Type C -- .manifest.json stale source keys**

The `.manifest.json` `sources` object has keys like `"_raw/llm-patterns.md"` that no longer match the actual file location.

**Type D -- Archived copies (_archives/)**

The `_archives/2026-04-15T12-00-00Z/` directory contains snapshot copies with the same broken links. These should likely be left unchanged (archives are frozen snapshots) -- configurable via CLI flag.

---

## 3. CLI Specification

### 3.1 Usage

```
obsidian-link-fixer [OPTIONS] [FILE_NAMES...]

Fix broken links in an Obsidian vault after files have been moved.
```

### 3.2 Positional arguments

```
FILE_NAMES    One or more filenames (basenames) that were moved.
              The tool will locate each file in the vault and update
              all references pointing to old paths.
              Example: obsidian-link-fixer llm-patterns.md agent-skills-architecture.md
```

### 3.3 Options

```
--vault PATH          Path to the Obsidian vault root.
                      Default: current directory.

--file PATH           Read list of moved filenames from a text file
                      (one filename per line). Can be combined with
                      positional args.

--dry-run             Show what would be changed without modifying files.
                      Prints a structured report (see 3.4).

--include-archives    Also fix links inside _archives/ directories.
                      Default: skip archives.

--include-manifest    Also update .manifest.json source keys and page
                      source references. Default: skip.

--verbose, -v         Show detailed per-file processing info.

--quiet, -q           Suppress all output except errors.

--help, -h            Show help and exit.
```

### 3.4 Dry-run report format

```
=== DRY RUN REPORT ===

File: concepts/knowledge-graph.md
  [frontmatter:sources] _raw/obsidian-knowledge-management.md -> _raw/s0/2026-04/obsidian-knowledge-management.md
  [wikilink:body]       [[obsidian-knowledge-management]] -> [[_raw/s0/2026-04/obsidian-knowledge-management]]

File: concepts/retrieval-augmented-generation.md
  [frontmatter:sources] _raw/llm-patterns.md -> _raw/s0/2026-04/llm-patterns.md
  [wikilink:body]       [[llm-patterns]] -> [[_raw/s0/2026-04/llm-patterns]]

File: .manifest.json
  [manifest:source_key] _raw/llm-patterns.md -> _raw/s0/2026-04/llm-patterns.md
  [manifest:page_source] concepts/retrieval-augmented-generation.md sources[0]: _raw/llm-patterns.md -> _raw/s0/2026-04/llm-patterns.md

Summary:
  Files scanned:  85
  Files modified: 17
  Links fixed:    34
    frontmatter:sources  14
    wikilink:body        12
    manifest:source_key   4
    manifest:page_source  4
```

### 3.5 Resolution algorithm

1. For each moved filename, search the vault recursively to find its current location.
2. Build a mapping: `{old_basename: new_relative_path}`.
3. For old paths: check frontmatter `sources` values and `.manifest.json` keys to discover what path was previously used.
4. Scan all `.md` files (optionally `.json` for manifest):
   - Parse YAML frontmatter, check `sources` list entries.
   - Scan body for `[[basename]]` or `[[old/path/basename]]` wikilinks.
   - For each match, replace with the new relative path.
5. Write changes (or report in dry-run mode).

### 3.6 Edge cases to handle

- **Multiple files with same basename**: error out with a message listing the duplicates, require user to specify full path.
- **File not found in vault**: warn and skip.
- **Aliased wikilinks**: `[[old-path|Alias]]` -- update only the path portion, preserve the alias.
- **Quoted vs unquoted YAML values**: preserve the original quoting style.
- **File extensions in links**: Obsidian wikilinks omit `.md` but frontmatter `sources` includes it. Handle both.
- **Non-.md sources**: `.json` files referenced in frontmatter (e.g., `chatgpt-export-documentation-practices.json`).

### 3.7 Tech stack

- Python 3.10+
- No external dependencies (stdlib only: `pathlib`, `re`, `yaml` via `pyyaml` or manual parsing, `argparse`, `json`)
- Single file: `scripts/obsidian-link-fixer.py`
