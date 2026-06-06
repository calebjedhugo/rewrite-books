# Phase 6: EPUB Assembly & Upload

These instructions are for the Phase 6 Task agent. The orchestrator reads this file and passes its contents (with paths and config values filled in) to the assembly agent.

---

### 6.1 Rebuild the EPUB

1. **Copy the original extracted EPUB** to a new directory:
   ```bash
   cp -r [path]/extracted [path]/rewrite/epub-build
   ```

2. **Copy the shared EPUB utility into the working directory:**
   ```bash
   cp <epub-utils-path> [path]/rewrite/
   ```

3. **Pre-build validation.** Before building, run two checks that must both pass:

   ```bash
   cd [path]/rewrite
   # Check 1: Validate chapter-map.json schema + file references
   python -c "
from epub_utils import validate_chapter_map
import json
result = validate_chapter_map()
print(json.dumps(result, indent=2))
assert result['valid'], f'Validation failed: {result[\"errors\"]}'
print('Validation PASSED')
"

   # Check 2: Dry-run heading detection for all chapters
   python -c "
from epub_utils import build_rewritten_epub
import json
result = build_rewritten_epub('.', dry_run=True)
print(json.dumps(result, indent=2))
assert result['chapters_missing'] == 0, f'{result[\"chapters_missing\"]} chapters missing heading detection'
print('Dry run PASSED')
"
   ```

   If either check fails, fix `chapter-map.json` `_metadata` (wrong `heading_tag`, missing IDs, etc.) before proceeding. Do NOT run the real build until both pass.

4. **Run the generic build function.** The `build_rewritten_epub()` function reads `chapter-map.json` (including the `_metadata` written during Phase 0.2) and handles everything: chapter content replacement, footnote marker insertion via 6 quote-matching strategies, endnotes generation, epub namespace, manifest/spine/toc updates, title update, and front matter replacement. All Kobo popup footnote quirks are handled internally.

   **Front matter replacement (auto-detected):** If `front-matter.html` or `front-matter.txt` exists in the rewrite directory, the build automatically replaces the Project Gutenberg header boilerplate with this custom content and removes the PG footer from the spine. Use `.html` for raw XHTML (e.g., with `<em>`, `<a>` tags) or `.txt` for plain text (auto-wrapped in `<section>/<p>` tags). This is where the "About This Edition" page goes — credit the source, describe the adaptation, and declare the license.

   ```bash
   cd [path]/rewrite
   python -c "from epub_utils import build_rewritten_epub; result = build_rewritten_epub('.'); print(result)"
   ```

   Check the output for errors. If the function reports chapters it couldn't find headings for, the `_metadata` in chapter-map.json may need adjustment (wrong `heading_tag`, missing `heading_id`, etc.). Fix and re-run.

   **CRITICAL — footnote match count is a hard gate, not a statistic.** `build_rewritten_epub()` reports how many footnote quotes matched (e.g. "125/128"). Any unmatched footnote is **silently dropped** from the published book. You MUST NOT treat a partial match as success. If `matched < total`, identify the offending chapters and return them as an **error** to the orchestrator (list which `chNN` and which quote failed) — do not finalize the EPUB. The orchestrator runs `gates.py footnote-substrings` before calling you, so a clean pipeline should arrive here at 100%; if you still see a miss, something changed and it must be fixed (re-anchor the quote via footnote-verify), not shipped. Report the exact match count in your return regardless.

   **If the generic build fails on an unusual EPUB structure**, fall back to writing a custom build script. Import the individual utility functions (`text_to_xhtml_paragraphs`, `write_endnotes_file`, `add_epub_namespace`, `update_manifest_and_spine`, `update_toc`, `update_title`) and handle the book-specific layout manually. **Do NOT reimplement** footnote matching or endnotes generation — always use the utility functions.

   **CRITICAL — Kobo popup footnote markup (handled by the utilities, but for reference):**
   - Markers: `<a epub:type="noteref" role="doc-noteref" href="endnotes.xhtml#fn{ch}n{num}"><sup>[N]</sup></a>`
   - Targets: `<aside epub:type="footnote" role="doc-footnote"><p id="fn{ch}n{num}">...</p></aside>`
   - `id` on the `<p>` inside `<aside>`, NOT on `<aside>` itself (Kobo bug)
   - IDs must end with a number (e.g., `fn1n1`, `fn28n3`) — Kobo heuristic
   - `xmlns:epub` must be declared on all XHTML files using `epub:type`
   - Footnotes in separate `endnotes.xhtml` only — never inline, never hidden with CSS
   - Sentinel noteref: Kobo won't popup the last `noteref` in a file. Each chapter gets an invisible sentinel appended after the last paragraph (handled automatically by `text_to_xhtml_paragraphs`)

5. **Repackage as EPUB**:
   ```bash
   cd [path]/rewrite/epub-build
   # mimetype must be first and uncompressed
   zip -X0 "../<Book Title> (rewritten).epub" mimetype
   zip -Xr9D "../<Book Title> (rewritten).epub" META-INF OEBPS
   ```

6. Verify the EPUB was created and report its file size.

### 6.2 Upload to Calibre Server (Optional)

**The orchestrator will tell you whether upload is enabled based on config.** If upload is not enabled, skip this section entirely.

If enabled, the orchestrator provides: `<upload-ssh>` (SSH host) and `<upload-library-path>` (calibre library path on the remote server).

1. Copy EPUB to remote server: `scp "<local-epub>" <upload-ssh>:/tmp/`
2. Add to calibre library (try in order, use first that works):
   ```bash
   # Option 1: calibredb on host
   ssh <upload-ssh> "calibredb add '/tmp/<filename>.epub' --library-path <upload-library-path>"
   # Option 2: calibredb via Docker
   ssh <upload-ssh> "docker exec calibre-web calibredb add '/tmp/<filename>.epub' --library-path /calibre-library"
   # Option 3: Manual copy + restart (inform user if this fallback is used)
   ssh <upload-ssh> "mkdir -p '<upload-library-path>/<Author>/<Book Title> (rewritten) (NEW)'"
   scp "<local-epub>" "<upload-ssh>:<upload-library-path>/<Author>/<Book Title> (rewritten) (NEW)/"
   ssh <upload-ssh> "docker restart calibre-web"
   ```
3. Clean up: `ssh <upload-ssh> "rm -f '/tmp/<filename>.epub'"`

### 6.3 Kobo KEPUB Conversion (Optional)

**Only run this if the orchestrator tells you KEPUB conversion is enabled (config `upload.kepub: true`).** Skip otherwise.

Pre-convert the EPUB to KEPUB using `ebook-convert` on the remote server. calibre-web's on-the-fly conversion causes mid-word breaking and broken progress tracking on the Kobo.

```bash
ssh <upload-ssh> "ebook-convert '/tmp/<filename>.epub' '/tmp/<filename>.kepub.epub' --output-profile kobo"
```

Then register the KEPUB format manually (since `calibredb` normalizes `.kepub.epub` to `.epub`). This requires adding the KEPUB format entry to `metadata.db` on the remote server.

**Note:** Clearing Kobo sync state is only needed when **republishing** (replacing an EPUB the Kobo has already synced). For first-time uploads, the standard upload + KEPUB conversion is sufficient.
