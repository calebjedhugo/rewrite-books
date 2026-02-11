# Phase 0: Setup Agent Instructions

These instructions are for the Phase 0 Task agent. The orchestrator reads this file and passes its contents (with paths and config values filled in) to the setup agent.

---

### 0.1 Obtain the EPUB

**The orchestrator will tell you which mode to use based on config.**

#### Mode A: Remote Calibre (epub_source.type = "calibre")

1. Search the calibre library for the EPUB:
   ```bash
   ssh <calibre-ssh> "find <calibre-library-path> -ipath '*<search-term>*' -name '*.epub'"
   ```
2. If multiple results, ask the user which one.
3. Create a working directory: `<working-dir>/<book-slug>/` (slugified book title, lowercase, hyphens)
4. Copy the EPUB locally:
   ```bash
   scp "<calibre-ssh>:<remote-path>" "<working-dir>/<book-slug>/"
   ```
5. Extract the EPUB:
   ```bash
   unzip "<epub-file>" -d "<working-dir>/<book-slug>/extracted"
   ```

#### Mode B: Local EPUB (epub_source.type = "local")

1. Ask the user for the path to a local EPUB file (or check if one was provided as an argument).
2. Create a working directory: `<working-dir>/<book-slug>/` (slugified book title, lowercase, hyphens)
3. Copy the EPUB into the working directory:
   ```bash
   cp "<local-epub-path>" "<working-dir>/<book-slug>/"
   ```
4. Extract the EPUB:
   ```bash
   unzip "<epub-file>" -d "<working-dir>/<book-slug>/extracted"
   ```

### 0.2 Extract Chapters

**Analyze the EPUB structure first** before writing any extraction code. Check:
- Are chapters in separate XHTML files, or combined in fewer files?
- What heading tags/patterns delineate chapters? (e.g., `<h1>`, `<h2>`, "Chapter", "CHAPTER", roman numerals, named chapters, plain numbers)
- Is there a table of contents (toc.ncx, nav.xhtml) that maps chapter titles to file offsets?

Then write and run a Python script **tailored to this specific book's structure** that:
1. Extracts each chapter's text based on the patterns found
2. Strips HTML tags, preserving paragraph breaks (double newlines)
3. Writes each chapter to `rewrite/chapters/chNN/original.txt` (zero-padded: ch01, ch02, etc.)
4. Skips non-chapter content (front matter, license, table of contents)
5. **Writes `rewrite/chapter-map.json`** — Phase 6's `build_rewritten_epub()` depends on this to reassemble the EPUB. Must include a `_metadata` key and per-chapter entries (see schema below)
6. Prints a summary: chapter count and word counts

**chapter-map.json schema:**

```json
{
  "_metadata": {
    "content_dir": "OEBPS",
    "heading_tag": "h2",
    "subtitle_tag": "h4",
    "boundary_pattern": "<hr\\s+style=\"width:\\s*65%;\"\\s*/>",
    "spillover": {},
    "opf_file": "content.opf",
    "ncx_file": "toc.ncx",
    "before_spine_idref": null
  },
  "ch01": {
    "chapter_number": 1,
    "title": "CHAPTER 1",
    "subtitle": "Down the Rabbit-Hole",
    "source_file": "chapter-01.xhtml",
    "line_range": [10, 180],
    "heading_id": "ch1",
    "anchor_id": "chapter_1",
    "word_count": 1842
  }
}
```

**`_metadata` fields:**
- `content_dir`: Directory within the EPUB containing XHTML files (usually "OEBPS" or "OPS")
- `heading_tag`: HTML tag used for chapter headings (e.g., "h2", "h3")
- `subtitle_tag`: Tag for chapter subtitles, or `null` if none exist
- `boundary_pattern`: Regex for section separators between chapters (e.g., `<hr>` patterns), or `null` if chapters are in separate files
- `spillover`: Map of `{"filename.xhtml": "chNN"}` for files that start with the tail end of a prior chapter's content. Empty object if no spillover
- `opf_file`: Name of the OPF file (usually "content.opf")
- `ncx_file`: Name of the NCX file (usually "toc.ncx")
- `before_spine_idref`: Spine idref to insert endnotes before (e.g., "pg-footer"), or `null` to append at end

**Per-chapter fields:**
- `heading_id`: The `id` attribute on the chapter heading tag (for locating the heading in the XHTML)
- `anchor_id`: The `id` on an `<a>` anchor inside/near the heading (some EPUBs use this pattern instead)
- Both IDs should be set if available; the build function tries both when locating chapters

Create this directory structure:
```
<working-dir>/<book-slug>/
  <original>.epub
  extracted/                    # raw EPUB contents
  rewrite/
    style-guide.md
    chapter-bible.md
    chapter-map.json            # source file/offset mapping for EPUB reassembly
    progress.md                 # tracks iteration state
    chapters/
      ch01/
        original.txt
        rewrite.txt             # (created later)
        footnotes.json          # (created later)
        status.txt              # "pending"
      ch02/
        ...
    high-level/
      review-round-01.md
      ...
```

Initialize every chapter's `status.txt` to "pending".

### 0.2.1 Validate Extraction

**YOU MUST** validate the extraction before proceeding. Run these checks:

1. **Chapter count**: Compare the number of extracted chapters against the TOC (toc.ncx or nav.xhtml). If they don't match, investigate — the extraction script may have missed chapters or double-counted.
2. **No empty files**: Verify every `original.txt` has content (`wc -w` on each). Flag any with fewer than 50 words — likely a failed extraction.
3. **No HTML residue**: Read the first 10 lines of 3 chapters (first, middle, last) and check for raw HTML tags. If `<p>`, `<div>`, `<span>`, or `<br>` appear in the text, the HTML stripping failed.
4. **Word count sanity**: Check for outliers. Any chapter under 200 words or over 10,000 words is suspicious — it may be a partial extraction or two chapters merged.
5. **chapter-map.json validation**: Copy `epub_utils.py` and run programmatic validation:
   ```bash
   cp <epub-utils-path> [path]/rewrite/
   cd [path]/rewrite
   python -c "
from epub_utils import validate_chapter_map
import json
result = validate_chapter_map(build_subdir='[path]/extracted')
print(json.dumps(result, indent=2))
assert result['valid'], f'Validation failed: {result[\"errors\"]}'
print('chapter-map.json validation PASSED')
"
   ```
   Fix any reported errors and re-run extraction before proceeding.

If any check fails, fix the extraction script and re-run. Do NOT proceed with broken extraction — every downstream phase depends on it.

### 0.3 Create Style Guide

Read 3 chapters (first, middle, last) to understand the original voice. Then write `rewrite/style-guide.md` — an opinionated guide covering voice, tone, dialogue, pacing, what to preserve, and what to change freely. Adapt based on what you actually find in the book.

**CRITICAL constraints:**
- **MUST** match the original book's target audience — do NOT age up/down content, add mature themes, violence, or language not present in the original
- This is an **adaptation**, not a faithful translation — take artistic liberties while keeping content appropriate for the original audience

### 0.4 Create Chapter Bible

Skim all original chapters (read each briefly). Write `rewrite/chapter-bible.md`:

- **Characters**: Name, description, role, relationships, voice notes
- **Locations**: Key places, descriptions, significance
- **Terms**: Technical/scientific terms, invented words, foreign phrases
- **Timeline**: Major events in order with chapter references
- **Modernization Decisions**: Any name changes, term updates, or adaptations decided here

**IMPORTANT**: This is the single source of truth for consistency. All chapter agents reference this document. Be thorough.

### 0.5 Initialize Progress Tracker

Write `rewrite/progress.md`:
```markdown
# Rewrite Progress

## Chapter-Level Iterations
- Round 1: [pending]

## High-Level Iterations
- Round 1: [pending]

## Status Summary
[Will be updated as work proceeds]
```
