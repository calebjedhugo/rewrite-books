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
    gates.py                    # deterministic quality gates (see 0.7)
    prompts/                    # one filled-in instruction file per worker step (see 0.6)
    chapters/
      ch01/                     # (tree is non-exhaustive; workers add intermediate files)
        original.txt
        rewrite.txt             # current best rewrite
        footnotes.json          # editorial footnotes for EPUB
        footnotes-verified.json # verifier audit + durable "verify ran" resume marker
        line-edit.json          # transient line-edit findings (also footnotes-line-edit.json)
        status.txt              # "pending" | "needs_work" | "approved"
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

### 0.6 Compile Worker Prompt Files

**This is the step that keeps the orchestrator's context clean.** Workers are dispatched by the orchestrator directly (managers and `claude -p` no longer exist), each told only to read its instruction file. You produce those instruction files here so the orchestrator never has to author or read prompt text.

1. Read `~/.claude/commands/rewrite-book/agent-templates.md`.
2. For each template in the "Worker Templates" section, fill in `[Book Title]` and every absolute `[path]` with this book's real values. Leave `CHAP_DIR` literally as `CHAP_DIR` — the orchestrator supplies each worker's concrete chapter directory at dispatch time.
3. Write each filled-in template verbatim to `[path]/rewrite/prompts/`, one file per step:

   | output file | from template |
   |---|---|
   | `prompts/rewrite.md` | Rewrite Worker Template |
   | `prompts/line-edit.md` | Line Editor Worker Template |
   | `prompts/revise.md` | Revision Worker Template |
   | `prompts/footnote.md` | Footnote Worker Template |
   | `prompts/footnote-line-edit.md` | Footnote Line Editor Worker Template |
   | `prompts/footnote-revise.md` | Footnote Revision Worker Template |
   | `prompts/footnote-verify.md` | Footnote Verifier Worker Template |
   | `prompts/reviewer.md` | Reviewer Worker Template |
   | `prompts/revise-highlevel.md` | High-Level Revision Worker Template |

There is **one file per step, not one per chapter** — the chapter number/dir varies per dispatch, not per file. Use the **Write tool** for each (pre-approved; avoids Bash permission prompts).

4. Verify all nine files exist before returning.

### 0.7 Write the Gate Script

The pipeline's quality gates must be **deterministic**, not "trust the orchestrator's narration." A prior run shipped a book whose adversarial reviews found 75 real issues that were then silently never applied, because nothing verified fix-application. The orchestrator runs these gates and routes on their tiny pass/fail output — chapter/footnote CONTENT never enters its context.

Write this file **verbatim** to `[path]/rewrite/gates.py` (use the Write tool):

```python
#!/usr/bin/env python3
"""Deterministic quality gates for the rewrite-book pipeline.
The orchestrator runs these via Bash and routes on the tiny pass/fail output;
chapter and footnote CONTENT never enters the orchestrator's context.
Exit code is non-zero if ANY checked item fails."""
import sys, os, json, glob

BASE = os.path.dirname(os.path.abspath(__file__))   # the rewrite/ dir
CH = os.path.join(BASE, "chapters")

def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()

def revise_applied(chapters):
    """FAIL a chapter if any line-edit.json finding's `quote` is still a verbatim
    substring of rewrite.txt — i.e. the suggested fix was NOT applied. Run this
    immediately after each revise wave, against the line-edit.json revise consumed."""
    rc = 0
    for c in chapters:
        d = os.path.join(CH, c)
        le, rw = os.path.join(d, "line-edit.json"), os.path.join(d, "rewrite.txt")
        if not (os.path.isfile(le) and os.path.isfile(rw)):
            print(f"{c}: ERROR missing line-edit.json or rewrite.txt"); rc = 1; continue
        try:
            j = json.load(open(le, encoding="utf-8"))
        except Exception as e:
            print(f"{c}: ERROR line-edit.json invalid JSON ({e})"); rc = 1; continue
        if j.get("verdict") != "has_issues":
            print(f"{c}: APPLIED (verdict={j.get('verdict')}, nothing to apply)"); continue
        text = _read(rw)
        issues = j.get("issues", [])
        quoted = [i.get("quote", "") for i in issues if i.get("quote", "")]
        remain = [q for q in quoted if q in text]
        if remain:
            print(f"{c}: NOT-APPLIED ({len(remain)}/{len(quoted)} flagged quotes still present)"); rc = 1
        else:
            print(f"{c}: APPLIED ({len(quoted)} fixes)")
    return rc

def json_valid(paths):
    """FAIL any path that is not parseable JSON (catches unescaped quotes etc.)."""
    rc = 0
    for p in paths:
        try:
            json.load(open(p, encoding="utf-8")); print(f"{p}: OK")
        except Exception as e:
            print(f"{p}: BAD ({e})"); rc = 1
    return rc

def footnote_substrings(chapters):
    """FAIL any footnote whose `quote` is not an exact substring of rewrite.txt.
    These get silently dropped from the EPUB otherwise. Run before Phase 6 build."""
    rc = 0
    chapters = chapters or sorted(os.path.basename(d) for d in glob.glob(os.path.join(CH, "ch*")))
    for c in chapters:
        d = os.path.join(CH, c)
        fj, rw = os.path.join(d, "footnotes.json"), os.path.join(d, "rewrite.txt")
        if not os.path.isfile(fj):
            continue
        if not os.path.isfile(rw):
            print(f"{c}: ERROR missing rewrite.txt"); rc = 1; continue
        try:
            arr = json.load(open(fj, encoding="utf-8"))
        except Exception as e:
            print(f"{c}: BAD footnotes.json ({e})"); rc = 1; continue
        if isinstance(arr, dict):   # {"needs_work": true, ...}
            print(f"{c}: SKIP (needs_work)"); continue
        text = _read(rw)
        bad = [fn.get("quote", "") for fn in arr if fn.get("quote", "") not in text]
        if bad:
            for q in bad:
                print(f"{c}: MISMATCH quote not in rewrite: {q[:70]!r}")
            rc = 1
        else:
            print(f"{c}: OK ({len(arr)} footnotes)")
    return rc

def audit(_):
    """End-of-run self-audit: run every gate across ALL chapters plus structural
    completeness and status-vs-gate consistency. Prints a compact sectioned report
    and a final ALL-CLEAR / FAILURES line. Exit non-zero if anything is wrong.
    This is the deterministic half of Phase 8 — the orchestrator runs it directly;
    it re-checks objective facts (substrings, JSON) it cannot fake."""
    chapters = sorted(os.path.basename(d) for d in glob.glob(os.path.join(CH, "ch*")))
    rc = 0
    print("== structural completeness ==")
    for c in chapters:
        miss = [f for f in ("original.txt", "rewrite.txt", "footnotes.json", "status.txt")
                if not os.path.isfile(os.path.join(CH, c, f))]
        if miss:
            print(f"{c}: MISSING {', '.join(miss)}"); rc = 1
    print("== json-valid ==")
    jpaths = [os.path.join(CH, c, f) for c in chapters
              for f in ("line-edit.json", "footnotes.json", "footnotes-verified.json")
              if os.path.isfile(os.path.join(CH, c, f))]
    if json_valid(jpaths): rc = 1
    print("== revise-applied ==")
    if revise_applied([c for c in chapters if os.path.isfile(os.path.join(CH, c, "line-edit.json"))]): rc = 1
    print("== footnote-substrings ==")
    if footnote_substrings(chapters): rc = 1
    print("== status vs gates ==")
    for c in chapters:
        sp = os.path.join(CH, c, "status.txt")
        st = _read(sp).strip() if os.path.isfile(sp) else "(none)"
        print(f"{c}: status={st}")
    print("== high-level review currency ==")
    reviews = glob.glob(os.path.join(BASE, "high-level", "review-round-*.md"))
    if not reviews:
        print("STALE: no high-level review found — Phase 4 not yet run"); rc = 1
    else:
        newest_review = max(os.path.getmtime(p) for p in reviews)
        stale = [c for c in chapters
                 if os.path.isfile(os.path.join(CH, c, "rewrite.txt"))
                 and os.path.getmtime(os.path.join(CH, c, "rewrite.txt")) > newest_review]
        if stale:
            print(f"STALE: {len(stale)} chapter(s) changed after the last review "
                  f"({', '.join(stale)}) — re-run Phase 4 against the final text"); rc = 1
        else:
            print("current (no rewrite.txt newer than the latest review)")
    print()
    print("AUDIT: " + ("FAILURES FOUND" if rc else "ALL-CLEAR"))
    return 1 if rc else 0

USAGE = "usage: gates.py {revise-applied chNN... | json-valid path... | footnote-substrings [chNN...] | audit}"
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(USAGE); sys.exit(2)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "revise-applied":     sys.exit(revise_applied(args))
    if cmd == "json-valid":         sys.exit(json_valid(args))
    if cmd == "footnote-substrings": sys.exit(footnote_substrings(args))
    if cmd == "audit":              sys.exit(audit(args))
    print(USAGE); sys.exit(2)
```

Confirm it runs: `python [path]/rewrite/gates.py` (prints usage, exit 2) before returning.

**Return to the orchestrator** (keep it short): working directory path, chapter count, word-count range (min/max), and confirmation that `chapter-map.json`, `style-guide.md`, `chapter-bible.md`, all nine `prompts/*.md` files, and `gates.py` were created.
