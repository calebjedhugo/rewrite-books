"""
Reusable EPUB utilities for footnote insertion, endnotes generation, and metadata updates.

Extracted from the Journey to the Center of the Earth build script. All functions are
parameterized — no globals, no hardcoded paths. Only stdlib imports.

Usage:
    from epub_utils import text_to_xhtml_paragraphs, write_endnotes_file, ...
"""

import os
import re
import html
import glob
import json


def text_to_xhtml_paragraphs(text, chapter_num, footnotes, source_file):
    """Convert plain text to XHTML paragraphs with footnote markers inserted.

    Footnote markers use same-file references for reliable Kobo KEPUB popups.
    Uses 6 matching strategies to find quote positions (exact, br-variant,
    case-insensitive, em-dash variants, regex word gaps, first+last 3 words).

    Args:
        text: Plain text chapter content (paragraphs separated by blank lines).
        chapter_num: Integer chapter number (used in footnote IDs).
        footnotes: List of dicts with 'quote' and 'note' keys.
        source_file: XHTML filename this chapter lives in (for back-links).

    Returns:
        (xhtml_string, matched_footnotes) where matched_footnotes is a list of
        (num, fn_id, fnref_id, note_text, source_file) tuples.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    footnote_counter = 0
    matched_footnotes = []

    result_paragraphs = []

    for para_text in paragraphs:
        escaped = html.escape(para_text)
        escaped = escaped.replace("\n", "<br/>\n")
        result_paragraphs.append(escaped)

    separator = "|||PARA_SEP|||"
    joined = separator.join(result_paragraphs)

    for fn in footnotes:
        quote = html.escape(fn["quote"])
        quote_br = quote.replace("\n", "<br/>\n")

        found = False
        match_end = -1

        # Strategy 1: Exact match
        idx = joined.find(quote)
        if idx != -1:
            match_end = idx + len(quote)
            found = True

        # Strategy 2: With <br/> variants
        if not found:
            idx = joined.find(quote_br)
            if idx != -1:
                match_end = idx + len(quote_br)
                found = True

        # Strategy 3: Case-insensitive
        if not found:
            lower_joined = joined.lower()
            lower_quote = quote.lower()
            idx = lower_joined.find(lower_quote)
            if idx != -1:
                match_end = idx + len(quote)
                found = True

        # Strategy 4: Try with double-dash converted to em dash and vice versa
        if not found:
            quote_emdash = quote.replace(" -- ", " \u2014 ").replace("--", "\u2014")
            idx = joined.find(quote_emdash)
            if idx != -1:
                match_end = idx + len(quote_emdash)
                found = True
            else:
                quote_dashes = quote.replace("\u2014", "--").replace(" \u2014 ", " -- ")
                idx = joined.find(quote_dashes)
                if idx != -1:
                    match_end = idx + len(quote_dashes)
                    found = True

        # Strategy 5: Regex with flexible gaps between words
        gap = r'(?:<[^>]*>|&[a-zA-Z0-9#]+;|\|{3}PARA_SEP\|{3}|[^a-zA-Z]){0,120}'
        if not found:
            raw_quote = fn["quote"]
            words = re.findall(r"[a-zA-Z']+", raw_quote)
            if len(words) >= 3:
                pattern_parts = [re.escape(w) for w in words]
                full_pattern = gap.join(pattern_parts)
                m = re.search(full_pattern, joined, re.DOTALL | re.IGNORECASE)
                if m:
                    idx = m.start()
                    match_end = m.end()
                    found = True

        # Strategy 6: First 3 + last 3 words with wide gap
        if not found:
            raw_quote = fn["quote"]
            words = re.findall(r"[a-zA-Z']+", raw_quote)
            if len(words) >= 6:
                first_words = words[:3]
                last_words = words[-3:]
                first_pat = gap.join(re.escape(w) for w in first_words)
                last_pat = gap.join(re.escape(w) for w in last_words)
                full_pattern = first_pat + r'.{0,2000}?' + last_pat
                m = re.search(full_pattern, joined, re.DOTALL | re.IGNORECASE)
                if m:
                    idx = m.start()
                    match_end = m.end()
                    found = True

        if found:
            footnote_counter += 1
            # IDs must end with a number for Kobo heuristic popup detection
            fn_id = f"fn{chapter_num}n{footnote_counter}"
            fnref_id = f"fnref{chapter_num}n{footnote_counter}"
            # Cross-file reference to endnotes.xhtml for Kobo popup detection
            marker = (
                f'<a epub:type="noteref" role="doc-noteref" '
                f'href="endnotes.xhtml#{fn_id}" id="{fnref_id}">'
                f'<sup>[{footnote_counter}]</sup></a>'
            )
            joined = joined[:match_end] + marker + joined[match_end:]
            matched_footnotes.append((footnote_counter, fn_id, fnref_id, fn["note"], source_file))
        else:
            print(f"  WARNING: Could not find quote in ch{chapter_num:02d}: \"{fn['quote'][:60]}...\"")

    result_paragraphs = joined.split(separator)

    xhtml_parts = []
    for para in result_paragraphs:
        xhtml_parts.append(f'<p>{para}</p>')

    # Kobo won't show a popup for the last epub:type="noteref" in a file.
    # After ebook-convert splits chapters into separate files, the real last
    # footnote becomes the last noteref and loses its popup. Fix: append an
    # invisible sentinel noteref so the real last footnote is never "last".
    if matched_footnotes:
        sentinel_fn_id = f"fn{chapter_num}n0"
        sentinel_fnref_id = f"fnref{chapter_num}n0"
        xhtml_parts.append(
            f'<p><a epub:type="noteref" role="doc-noteref" '
            f'href="endnotes.xhtml#{sentinel_fn_id}" id="{sentinel_fnref_id}">'
            f'<sup>\u200b</sup></a></p>'
        )

    return "\n".join(xhtml_parts), matched_footnotes


def write_endnotes_file(all_footnotes, build_dir, css_files=None):
    """Write a separate endnotes.xhtml file with all footnotes.

    Kobo requires footnotes to be fully rendered (not display:none) for popup detection.
    A separate file keeps them out of the chapter flow while remaining fully accessible.

    Args:
        all_footnotes: List of (chapter_num, title, subtitle, matched_fns) tuples.
            Each matched_fns is a list of (num, fn_id, fnref_id, note, source_file).
        build_dir: Path to the OEBPS directory (e.g., .../epub-build/OEBPS/).
        css_files: Optional list of CSS filenames to link. If None, auto-detects
            .css files in build_dir.
    """
    if not all_footnotes:
        print("\nNo footnotes to write")
        return

    if css_files is None:
        css_files = sorted(
            os.path.basename(f) for f in glob.glob(os.path.join(build_dir, "*.css"))
        )

    parts = []
    parts.append('<?xml version="1.0" encoding="utf-8"?>')
    parts.append('<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">')
    parts.append('<head>')
    parts.append('<meta charset="utf-8"/>')
    parts.append('<title>Notes</title>')
    for css in css_files:
        parts.append(f'<link href="{css}" rel="stylesheet" type="text/css"/>')
    parts.append('</head>')
    parts.append('<body>')
    parts.append('<h1>Notes</h1>')

    total_notes = 0
    for ch_num, title, subtitle, footnotes in all_footnotes:
        for num, fn_id, fnref_id, note, source_file in footnotes:
            escaped_note = html.escape(note)
            escaped_note = escaped_note.replace(" -- ", " \u2014 ")
            # id on <p>, not <aside> (Kobo bug: can't resolve ids on aside elements)
            parts.append(
                f'<aside epub:type="footnote" role="doc-footnote">'
                f'<p id="{fn_id}">'
                f'<sup>{num}.</sup> {escaped_note} '
                f'<a href="{source_file}#{fnref_id}">\u21a9</a>'
                f'</p></aside>'
            )
            total_notes += 1
        # Sentinel target for the invisible noteref at the end of each chapter.
        # See text_to_xhtml_paragraphs for why this is needed.
        sentinel_fn_id = f"fn{ch_num}n0"
        parts.append(
            f'<aside epub:type="footnote" role="doc-footnote">'
            f'<p id="{sentinel_fn_id}">\u200b</p></aside>'
        )

    parts.append('</body>')
    parts.append('</html>')

    filepath = os.path.join(build_dir, "endnotes.xhtml")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print(f"\nWrote endnotes.xhtml ({total_notes} footnotes)")


def add_epub_namespace(xhtml_files, build_dir):
    """Add epub namespace to XHTML files for EPUB3 footnote support.

    Args:
        xhtml_files: List of XHTML filenames to process.
        build_dir: Path to the OEBPS directory containing the files.
    """
    for filename in xhtml_files:
        filepath = os.path.join(build_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        if 'xmlns:epub=' not in content:
            content = content.replace(
                'xmlns="http://www.w3.org/1999/xhtml"',
                'xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"'
            )
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  Added epub namespace to {filename}")


def update_manifest_and_spine(opf_path, before_spine_idref=None):
    """Add endnotes.xhtml to the OPF manifest and spine.

    Args:
        opf_path: Path to content.opf file.
        before_spine_idref: Optional idref to insert endnotes before in the spine
            (e.g., "pg-footer"). If None, inserts before </spine>.
    """
    with open(opf_path, "r", encoding="utf-8") as f:
        opf = f.read()

    if 'endnotes.xhtml' not in opf:
        # Add to manifest (before </manifest>)
        opf = opf.replace(
            '</manifest>',
            '    <item href="endnotes.xhtml" id="endnotes" media-type="application/xhtml+xml"/>\n  </manifest>'
        )
        # Add to spine
        if before_spine_idref:
            target = f'<itemref idref="{before_spine_idref}"/>'
            if target in opf:
                opf = opf.replace(
                    target,
                    f'<itemref idref="endnotes"/>\n    {target}'
                )
            else:
                # Fallback: before </spine>
                opf = opf.replace(
                    '</spine>',
                    '    <itemref idref="endnotes"/>\n  </spine>'
                )
        else:
            opf = opf.replace(
                '</spine>',
                '    <itemref idref="endnotes"/>\n  </spine>'
            )

    with open(opf_path, "w", encoding="utf-8") as f:
        f.write(opf)
    print(f"Added endnotes.xhtml to manifest and spine")


def update_toc(ncx_path):
    """Add Notes entry to the NCX table of contents.

    Args:
        ncx_path: Path to toc.ncx file.
    """
    with open(ncx_path, "r", encoding="utf-8") as f:
        ncx = f.read()

    if 'endnotes.xhtml' not in ncx:
        # Find the last navPoint's playOrder to increment
        play_orders = re.findall(r'playOrder="(\d+)"', ncx)
        next_order = max(int(p) for p in play_orders) + 1 if play_orders else 100

        nav_ids = re.findall(r'id="(navPoint-\d+)"', ncx)
        next_nav_id = max(int(n.split('-')[1]) for n in nav_ids) + 1 if nav_ids else 100

        notes_nav = f'''    <navPoint id="navPoint-{next_nav_id}" playOrder="{next_order}">
      <navLabel><text>Notes</text></navLabel>
      <content src="endnotes.xhtml"/>
    </navPoint>'''

        ncx = ncx.replace('</navMap>', notes_nav + '\n  </navMap>')

    with open(ncx_path, "w", encoding="utf-8") as f:
        f.write(ncx)
    print(f"Added Notes to toc.ncx")


def update_title(opf_path, ncx_path, suffix=" (rewritten)"):
    """Append a suffix to the title in content.opf and toc.ncx.

    Args:
        opf_path: Path to content.opf file.
        ncx_path: Path to toc.ncx file.
        suffix: String to append to the title. Default: " (rewritten)".
    """
    with open(opf_path, "r", encoding="utf-8") as f:
        opf = f.read()

    opf = re.sub(
        r'(<dc:title>)(.*?)(</dc:title>)',
        rf'\1\2{re.escape(suffix)}\3',
        opf
    )
    with open(opf_path, "w", encoding="utf-8") as f:
        f.write(opf)
    print(f"Updated title in {opf_path}")

    with open(ncx_path, "r", encoding="utf-8") as f:
        ncx = f.read()

    ncx = re.sub(
        r'(<docTitle>\s*<text>)(.*?)(</text>\s*</docTitle>)',
        rf'\1\2{re.escape(suffix)}\3',
        ncx,
        flags=re.DOTALL
    )
    with open(ncx_path, "w", encoding="utf-8") as f:
        f.write(ncx)
    print(f"Updated title in {ncx_path}")


def validate_chapter_map(build_subdir="epub-build"):
    """Validate chapter-map.json schema and file references.

    Checks that chapter-map.json has correct structure, required fields,
    and that all referenced files exist on disk. Designed to catch issues
    early — call in Phase 0 against extracted/ and in Phase 6 before build.

    Args:
        build_subdir: Path to the EPUB directory containing source files.
            Defaults to "epub-build" (relative to cwd, for Phase 6).
            Pass an absolute path to validate against extracted/ (Phase 0).

    Returns:
        Dict with keys: valid (bool), errors (list), warnings (list).
    """
    errors = []
    warnings = []

    # Load chapter-map.json
    if not os.path.exists("chapter-map.json"):
        return {"valid": False, "errors": ["chapter-map.json not found in current directory"], "warnings": []}

    with open("chapter-map.json", "r", encoding="utf-8") as f:
        chapter_map = json.load(f)

    # Check _metadata
    meta = chapter_map.get("_metadata")
    if not meta:
        errors.append("Missing _metadata key")
    else:
        required_meta = ["content_dir", "heading_tag", "opf_file", "ncx_file"]
        for field in required_meta:
            if field not in meta:
                errors.append(f"_metadata missing required field: {field}")

    # Collect chapters
    chapters = {k: v for k, v in chapter_map.items() if k.startswith("ch")}
    if not chapters:
        errors.append("No chapter entries found (keys starting with 'ch')")
        return {"valid": False, "errors": errors, "warnings": warnings}

    # Determine base directory for file checks
    if meta:
        content_dir = meta.get("content_dir", "OEBPS")
        if os.path.isabs(build_subdir):
            base_dir = os.path.join(build_subdir, content_dir)
        else:
            base_dir = os.path.join(build_subdir, content_dir)
    else:
        base_dir = None

    # Validate per-chapter entries
    chapter_numbers = []
    for ch_key in sorted(chapters.keys()):
        info = chapters[ch_key]

        # Required fields
        if "source_file" not in info:
            errors.append(f"{ch_key}: missing source_file")
        if "chapter_number" not in info:
            errors.append(f"{ch_key}: missing chapter_number")
        else:
            chapter_numbers.append(info["chapter_number"])

        if not info.get("heading_id") and not info.get("anchor_id"):
            errors.append(f"{ch_key}: must have at least one of heading_id or anchor_id")

        # Check source_file exists on disk
        if base_dir and "source_file" in info:
            src_path = os.path.join(base_dir, info["source_file"])
            if not os.path.exists(src_path):
                errors.append(f"{ch_key}: source_file not found: {src_path}")

    # Check chapter number sequence (no gaps, no dupes)
    if chapter_numbers:
        chapter_numbers.sort()
        expected = list(range(chapter_numbers[0], chapter_numbers[0] + len(chapter_numbers)))
        if chapter_numbers != expected:
            dupes = [n for n in set(chapter_numbers) if chapter_numbers.count(n) > 1]
            if dupes:
                errors.append(f"Duplicate chapter numbers: {dupes}")
            gaps = set(expected) - set(chapter_numbers)
            if gaps:
                errors.append(f"Missing chapter numbers (gaps): {sorted(gaps)}")

    # Check OPF and NCX exist
    if meta and base_dir:
        opf_path = os.path.join(base_dir, meta.get("opf_file", "content.opf"))
        ncx_path = os.path.join(base_dir, meta.get("ncx_file", "toc.ncx"))
        if not os.path.exists(opf_path):
            errors.append(f"OPF file not found: {opf_path}")
        if not os.path.exists(ncx_path):
            errors.append(f"NCX file not found: {ncx_path}")

    # Validate spillover references
    if meta:
        spillover = meta.get("spillover", {})
        for filename, ch_ref in spillover.items():
            if ch_ref not in chapters:
                errors.append(f"Spillover references unknown chapter: {filename} -> {ch_ref}")
            if base_dir:
                spill_path = os.path.join(base_dir, filename)
                if not os.path.exists(spill_path):
                    warnings.append(f"Spillover file not found: {spill_path}")

    valid = len(errors) == 0
    return {"valid": valid, "errors": errors, "warnings": warnings}


# XHTML (application/xhtml+xml) predefines only the five XML entities, so a
# raw front-matter.html using named typographic entities makes strict readers
# (Kobo) fail to parse the page. Map the common ones to literal characters.
_FM_ENTITY_MAP = {
    "&mdash;": "—", "&ndash;": "–", "&hellip;": "…",
    "&nbsp;": " ", "&rsquo;": "’", "&lsquo;": "‘",
    "&ldquo;": "“", "&rdquo;": "”", "&amp;mdash;": "—",
}


def _find_pg_element_span(content, elem_id):
    """Return (start, end) of the <section>/<div> whose id == elem_id.

    PG's ebookmaker emits the header/footer as either a <section> or a <div>,
    and the block nests same-name tags, so this walks tag depth rather than
    using a naive non-greedy regex (which would stop at the first inner close).
    Returns None if no element with that exact id is found.
    """
    open_re = re.compile(
        rf'<(section|div)\b[^>]*\bid="{re.escape(elem_id)}"[^>]*?(/?)>',
        re.IGNORECASE,
    )
    m = open_re.search(content)
    if not m:
        return None
    if m.group(2) == "/":            # self-closing opening tag, no body
        return (m.start(), m.end())
    tag = m.group(1)
    tok = re.compile(rf'<(/?){tag}\b[^>]*?(/?)>', re.IGNORECASE)
    depth = 1
    for t in tok.finditer(content, m.end()):
        if t.group(1) == "/":        # closing tag
            depth -= 1
        elif t.group(2) != "/":      # opening (non-self-closing) tag
            depth += 1
        if depth == 0:
            return (m.start(), t.end())
    return None


def replace_pg_boilerplate(build_dir, front_matter_path, opf_path,
                           pg_header_id="pg-header",
                           pg_footer_idref="pg-footer"):
    """Replace Project Gutenberg boilerplate with custom front matter.

    Scans content files in build_dir for the element with the given
    pg_header_id, replaces it with custom front matter, and removes the PG
    footer from the OPF spine.

    Handles the two PG ebookmaker layouts seen in the wild: the header as a
    <section id="pg-header"> in *.xhtml files, OR as a <div id="pg-header">
    in *.html/*.htm files (newer ebookmaker). Both are matched.

    Supports two front matter formats:
    - .html: inserted as raw XHTML fragment (named entities are normalized)
    - .txt: paragraphs separated by blank lines, auto-wrapped in <section>/<p> tags

    Args:
        build_dir: Path to the OEBPS directory.
        front_matter_path: Path to front-matter.html or front-matter.txt.
        opf_path: Path to content.opf file.
        pg_header_id: ID of the PG header section to replace. Default "pg-header".
        pg_footer_idref: idref of the PG footer in the spine. Default "pg-footer".
            Set to None to skip footer removal.
    """
    with open(front_matter_path, "r", encoding="utf-8") as f:
        raw = f.read().strip()

    # Build front matter HTML
    if front_matter_path.endswith(".html"):
        fm_html = raw
        for ent, ch in _FM_ENTITY_MAP.items():
            fm_html = fm_html.replace(ent, ch)
    else:
        paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]
        parts = ['<section id="about-this-edition">', '<h2>About This Edition</h2>']
        for p in paragraphs:
            escaped = html.escape(p).replace("\n", " ")
            parts.append(f'<p>{escaped}</p>')
        parts.append('</section>')
        fm_html = "\n".join(parts)

    # Find and replace the PG header block across .xhtml/.html/.htm files
    replaced = False
    files = []
    for ext in ("*.xhtml", "*.html", "*.htm"):
        files.extend(glob.glob(os.path.join(build_dir, ext)))
    for xhtml_file in sorted(set(files)):
        with open(xhtml_file, "r", encoding="utf-8") as f:
            content = f.read()

        span = _find_pg_element_span(content, pg_header_id)
        if span:
            start, end = span
            trail = re.match(r'\s*<pre\s*/>', content[end:])  # PG sometimes leaves this
            if trail:
                end += trail.end()
            content = content[:start] + fm_html + "\n" + content[end:]

            # Remove Redactor's Note if present (PG-specific boilerplate)
            content = re.sub(
                r'<p[^>]*>\s*<b>\[\s*Redactor.{0,20}s Note:.*?</p>\s*',
                '',
                content,
                flags=re.DOTALL
            )

            with open(xhtml_file, "w", encoding="utf-8") as f:
                f.write(content)
            replaced = True
            print(f"Replaced PG header in {os.path.basename(xhtml_file)}")
            break

    if not replaced:
        print(f"WARNING: Could not find element with id=\"{pg_header_id}\" in any content file")

    # Remove PG footer from OPF spine
    if pg_footer_idref:
        with open(opf_path, "r", encoding="utf-8") as f:
            opf = f.read()

        footer_pattern = re.compile(
            rf'\s*<itemref\s+idref="{re.escape(pg_footer_idref)}"\s*/>'
        )
        new_opf = footer_pattern.sub('', opf)
        if new_opf != opf:
            with open(opf_path, "w", encoding="utf-8") as f:
                f.write(new_opf)
            print(f"Removed {pg_footer_idref} from spine")


def build_rewritten_epub(rewrite_dir, dry_run=False):
    """Build a rewritten EPUB from chapter rewrites and footnotes.

    Reads chapter-map.json (with _metadata section) to determine EPUB structure
    and replace chapter content with rewrites + footnotes. Handles both
    one-file-per-chapter and multi-chapter-per-file layouts.

    Expected directory structure:
        rewrite_dir/
            chapter-map.json       (with _metadata key — see rewrite-book skill docs)
            epub_utils.py          (this file, copied here by Phase 6)
            chapters/chNN/rewrite.txt
            chapters/chNN/footnotes.json
            epub-build/            (copy of original extracted EPUB)

    Args:
        rewrite_dir: Path to the rewrite/ directory.
        dry_run: If True, tests heading detection for all chapters without
            modifying any files. Returns detection results instead of build stats.

    Returns:
        If dry_run=False: Dict with build stats (chapters_replaced, chapters_total,
            footnotes_matched, footnotes_expected, errors).
        If dry_run=True: Dict with detection results (chapters_found, chapters_missing,
            details list of per-chapter results).
    """
    chapter_map_path = os.path.join(rewrite_dir, "chapter-map.json")
    with open(chapter_map_path, "r", encoding="utf-8") as f:
        chapter_map = json.load(f)

    meta = chapter_map.get("_metadata", {})
    chapters = {k: v for k, v in chapter_map.items() if k.startswith("ch")}
    chapters_dir = os.path.join(rewrite_dir, "chapters")

    content_dir_name = meta.get("content_dir", "OEBPS")
    build_dir = os.path.join(rewrite_dir, "epub-build", content_dir_name)
    heading_tag = meta.get("heading_tag", "h2")
    subtitle_tag = meta.get("subtitle_tag")
    boundary_pattern = meta.get("boundary_pattern")
    spillover = meta.get("spillover", {})

    if dry_run:
        print("=" * 60)
        print(f"DRY RUN: Testing heading detection ({len(chapters)} chapters)")
        print("=" * 60)
    else:
        print("=" * 60)
        print(f"Building rewritten EPUB ({len(chapters)} chapters)")
        print("=" * 60)

    # Group chapters by source file, preserving chapter order
    chapters_by_file = {}
    for ch_key in sorted(chapters.keys(), key=lambda k: chapters[k]["chapter_number"]):
        info = chapters[ch_key]
        src = info["source_file"]
        if src not in chapters_by_file:
            chapters_by_file[src] = []
        chapters_by_file[src].append((ch_key, info))

    # --- Dry run: test heading detection only ---
    if dry_run:
        details = []
        chapters_found = 0
        chapters_missing = 0

        for filename, file_chapters in chapters_by_file.items():
            filepath = os.path.join(build_dir, filename)
            if not os.path.exists(filepath):
                for ch_key, info in file_chapters:
                    details.append({"chapter": ch_key, "found": False, "strategy": None,
                                    "error": f"Source file not found: {filepath}"})
                    chapters_missing += len(file_chapters)
                continue

            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            for ch_key, info in file_chapters:
                heading_id = info.get("heading_id", "")
                anchor_id = info.get("anchor_id", "")
                matched_strategy = None

                # Strategy 1: id attribute on the heading tag
                if heading_id:
                    pat = rf"<{heading_tag}[^>]*\bid=\"{re.escape(heading_id)}\"[^>]*>"
                    if re.search(pat, content):
                        matched_strategy = "heading_id"

                # Strategy 2: <a> anchor with id inside the heading
                if not matched_strategy and anchor_id:
                    pat = rf"<{heading_tag}[^>]*>\s*<a[^>]*\bid=\"{re.escape(anchor_id)}\""
                    if re.search(pat, content, re.DOTALL):
                        matched_strategy = "anchor_id"

                # Strategy 3: title text match
                if not matched_strategy and info.get("title"):
                    title_escaped = re.escape(info["title"])
                    pat = rf"<{heading_tag}[^>]*\bid=\"[^\"]*\"[^>]*>.*?{title_escaped}"
                    if re.search(pat, content, re.DOTALL):
                        matched_strategy = "title_text"

                if matched_strategy:
                    chapters_found += 1
                    print(f"  {ch_key}: FOUND (strategy: {matched_strategy})")
                else:
                    chapters_missing += 1
                    print(f"  {ch_key}: MISSING (heading_id={heading_id}, anchor_id={anchor_id})")

                details.append({"chapter": ch_key, "found": matched_strategy is not None,
                                "strategy": matched_strategy,
                                "heading_id": heading_id, "anchor_id": anchor_id})

        print(f"\nDry run complete: {chapters_found} found, {chapters_missing} missing")
        return {"chapters_found": chapters_found, "chapters_missing": chapters_missing, "details": details}

    # --- Normal build ---
    all_footnotes = []
    errors = []
    total_replaced = 0
    total_fn_matched = 0
    total_fn_expected = 0

    for filename, file_chapters in chapters_by_file.items():
        filepath = os.path.join(build_dir, filename)
        if not os.path.exists(filepath):
            msg = f"Source file not found: {filepath}"
            print(f"\nERROR: {msg}")
            errors.append(msg)
            continue

        print(f"\nProcessing {filename} ({len(file_chapters)} chapter(s))")

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Handle spillover content at top of continuation files
        spillover_ch = spillover.get(filename)
        if spillover_ch and boundary_pattern:
            spill_pat = re.compile(
                r"(<body[^>]*>)(.*?)(" + boundary_pattern + ")",
                re.DOTALL,
            )
            spill_match = spill_pat.search(content)
            if spill_match:
                content = (
                    content[: spill_match.start()]
                    + spill_match.group(1)
                    + "\n"
                    + spill_match.group(3)
                    + content[spill_match.end() :]
                )
                print(f"  Removed spillover content from {spillover_ch}")

        for ch_key, info in file_chapters:
            ch_num = info["chapter_number"]
            heading_id = info.get("heading_id", "")
            anchor_id = info.get("anchor_id", "")
            subtitle = info.get("subtitle", "")

            # --- Locate chapter heading ---
            h_match = None

            # Strategy 1: id attribute on the heading tag itself
            if heading_id:
                pat = rf"<{heading_tag}[^>]*\bid=\"{re.escape(heading_id)}\"[^>]*>"
                h_match = re.search(pat, content)

            # Strategy 2: <a> anchor with id inside the heading
            if not h_match and anchor_id:
                pat = rf"<{heading_tag}[^>]*>\s*<a[^>]*\bid=\"{re.escape(anchor_id)}\""
                h_match = re.search(pat, content, re.DOTALL)

            # Strategy 3: id on heading, match by title text
            if not h_match and info.get("title"):
                title_escaped = re.escape(info["title"])
                pat = rf"<{heading_tag}[^>]*\bid=\"[^\"]*\"[^>]*>.*?{title_escaped}"
                h_match = re.search(pat, content, re.DOTALL)

            if not h_match:
                msg = f"Could not find heading for {ch_key} (heading_id={heading_id}, anchor_id={anchor_id})"
                print(f"  ERROR: {msg}")
                errors.append(msg)
                continue

            # Find end of heading tag
            heading_close = f"</{heading_tag}>"
            close_pos = content.find(heading_close, h_match.start())
            if close_pos == -1:
                msg = f"Could not find closing {heading_tag} for {ch_key}"
                print(f"  ERROR: {msg}")
                errors.append(msg)
                continue
            content_start = close_pos + len(heading_close)

            # Skip past subtitle tag if configured
            if subtitle_tag:
                sub_pat = re.compile(
                    rf"\s*<{subtitle_tag}[^>]*>.*?</{subtitle_tag}>", re.DOTALL
                )
                sub_match = sub_pat.match(content[content_start:])
                if sub_match:
                    content_start += sub_match.end()

            # --- Find end boundary ---
            search_from = content_start

            # Look for next chapter heading in this file
            next_h_pos = None
            for pat in [
                rf"<{heading_tag}[^>]*\bid=\"[^\"]*\"",
                rf"<{heading_tag}[^>]*>\s*<a[^>]*\bid=\"",
            ]:
                m = re.search(pat, content[search_from:], re.DOTALL)
                if m:
                    pos = search_from + m.start()
                    if next_h_pos is None or pos < next_h_pos:
                        next_h_pos = pos

            end_pos = None
            if next_h_pos is not None:
                if boundary_pattern:
                    # Look for separator before the next heading
                    region = content[search_from:next_h_pos]
                    boundary_matches = list(re.finditer(boundary_pattern, region))
                    if boundary_matches:
                        end_pos = search_from + boundary_matches[-1].start()
                    else:
                        end_pos = next_h_pos
                else:
                    end_pos = next_h_pos
            else:
                # Last chapter in file — end at </body> or Gutenberg footer
                pre_body = re.search(r"<pre\s*/>\s*</body>", content[search_from:])
                if pre_body:
                    end_pos = search_from + pre_body.start()
                else:
                    body_end = content.find("</body>", search_from)
                    end_pos = body_end if body_end != -1 else len(content)

            # --- Read rewrite and footnotes ---
            rewrite_path = os.path.join(chapters_dir, ch_key, "rewrite.txt")
            footnotes_path = os.path.join(chapters_dir, ch_key, "footnotes.json")

            if not os.path.exists(rewrite_path):
                msg = f"Missing rewrite for {ch_key}: {rewrite_path}"
                print(f"  ERROR: {msg}")
                errors.append(msg)
                continue

            with open(rewrite_path, "r", encoding="utf-8") as f:
                rewrite_text = f.read().strip()

            footnotes = []
            if os.path.exists(footnotes_path):
                with open(footnotes_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        footnotes = data

            xhtml_content, matched_fns = text_to_xhtml_paragraphs(
                rewrite_text, ch_num, footnotes, filename
            )

            if matched_fns:
                all_footnotes.append(
                    (ch_num, info.get("title", ""), subtitle, matched_fns)
                )

            # --- Replace content ---
            old_len = end_pos - content_start
            content = (
                content[:content_start]
                + "\n"
                + xhtml_content
                + "\n"
                + content[end_pos:]
            )

            total_replaced += 1
            total_fn_matched += len(matched_fns)
            total_fn_expected += len(footnotes)

            print(
                f"  {ch_key}: {old_len} -> {len(xhtml_content)} chars, "
                f"{len(matched_fns)}/{len(footnotes)} footnotes"
            )

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    # --- Post-processing: namespace, endnotes, manifest, toc, title ---
    xhtml_files = list(chapters_by_file.keys())
    add_epub_namespace(xhtml_files, build_dir)

    write_endnotes_file(all_footnotes, build_dir)

    opf_file = meta.get("opf_file", "content.opf")
    ncx_file = meta.get("ncx_file", "toc.ncx")
    opf_path = os.path.join(build_dir, opf_file)
    ncx_path = os.path.join(build_dir, ncx_file)

    before_spine = meta.get("before_spine_idref")
    update_manifest_and_spine(opf_path, before_spine_idref=before_spine)
    update_toc(ncx_path)
    update_title(opf_path, ncx_path)

    # Replace PG boilerplate with custom front matter if provided
    front_matter_path = None
    for ext in (".html", ".txt"):
        candidate = os.path.join(rewrite_dir, f"front-matter{ext}")
        if os.path.exists(candidate):
            front_matter_path = candidate
            break

    if front_matter_path:
        replace_pg_boilerplate(
            build_dir, front_matter_path, opf_path,
            pg_footer_idref=before_spine
        )

    print("\n" + "=" * 60)
    print(
        f"EPUB build complete: {total_replaced}/{len(chapters)} chapters replaced, "
        f"{total_fn_matched}/{total_fn_expected} footnotes matched"
    )
    if errors:
        print(f"ERRORS ({len(errors)}):")
        for err in errors:
            print(f"  - {err}")
    print("=" * 60)

    return {
        "chapters_replaced": total_replaced,
        "chapters_total": len(chapters),
        "footnotes_matched": total_fn_matched,
        "footnotes_expected": total_fn_expected,
        "errors": errors,
    }
