# epub-utils

Shared EPUB utilities for the `/rewrite-book` skill. Extracted from the Journey to the Center of the Earth build script.

## Usage

Copy `epub_utils.py` into your working directory, then import:

```python
from epub_utils import build_rewritten_epub, validate_chapter_map

# Or for custom build scripts, import individual functions:
from epub_utils import (
    text_to_xhtml_paragraphs,
    write_endnotes_file,
    add_epub_namespace,
    update_manifest_and_spine,
    update_toc,
    update_title,
)
```

## Functions

### High-Level Build

| Function | Purpose |
|----------|---------|
| `build_rewritten_epub(rewrite_dir, dry_run=False)` | One-call EPUB build from `chapter-map.json`. Returns stats dict. `dry_run=True` tests heading detection only (no file modifications). |
| `validate_chapter_map(build_subdir="epub-build")` | Validates `chapter-map.json` schema + file existence. Returns `{valid, errors, warnings}`. Pass absolute path to `extracted/` for Phase 0. |

Run `validate_chapter_map()` then `build_rewritten_epub('.', dry_run=True)` before the real build to catch issues early.

**Requires** `chapter-map.json` with a `_metadata` key — see the `/rewrite-book` skill docs for the full schema.

### Low-Level Utilities

For custom build scripts when `build_rewritten_epub()` doesn't fit an unusual EPUB structure:

| Function | Purpose |
|----------|---------|
| `text_to_xhtml_paragraphs(text, chapter_num, footnotes, source_file)` | Convert plain text to XHTML `<p>` tags with Kobo-compatible footnote markers inserted via 6 quote-matching strategies |
| `write_endnotes_file(all_footnotes, build_dir, css_files=None)` | Generate `endnotes.xhtml` with all footnotes organized by chapter. Auto-detects CSS files if not specified |
| `add_epub_namespace(xhtml_files, build_dir)` | Add `xmlns:epub` declaration to XHTML files that need it |
| `update_manifest_and_spine(opf_path, before_spine_idref=None)` | Add endnotes.xhtml to OPF manifest and spine |
| `update_toc(ncx_path)` | Add "Notes" entry to NCX table of contents |
| `update_title(opf_path, ncx_path, suffix=" (rewritten)")` | Append suffix to book title in OPF and NCX |
| `replace_pg_boilerplate(build_dir, front_matter_path, opf_path, ...)` | Replace PG header/footer with custom "About This Edition" front matter. Supports `.html` (raw XHTML) or `.txt` (auto-wrapped in `<p>` tags). Also strips PG footer from spine. |

## IMPORTANT

- Only stdlib imports (`os`, `re`, `html`, `glob`, `json`) — no dependencies
- All Kobo footnote quirks are baked in — see below
- **Do NOT modify the 6 quote-matching strategies** without testing against a real Kobo device — the order and logic are battle-tested

## Kobo Footnote Quirks (baked into the utilities)

1. `id` on `<p>` inside `<aside>`, NOT on `<aside>` itself — Kobo can't resolve IDs on `<aside>` elements
2. IDs must end with a number (e.g., `fn1n1`, `fn28n3`) — Kobo heuristic for popup detection
3. Footnotes in separate `endnotes.xhtml` — never inline, never hidden with CSS
4. `xmlns:epub` must be declared on all XHTML files using `epub:type`
5. **Sentinel noteref workaround** — Kobo won't show a popup for the last `epub:type="noteref"` in a file. After `ebook-convert` splits chapters into separate XHTML files, the real last footnote becomes the last noteref and loses its popup. Fix: each chapter gets an invisible sentinel noteref (empty `<sup>`) appended after the last paragraph, with a matching empty target in `endnotes.xhtml`. This ensures the real last footnote is never "last in file."
6. Back-links (↩) in `endnotes.xhtml` use plain `<a>` without `epub:type="noteref"` — they're navigation links, not footnote references
