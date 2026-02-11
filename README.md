# rewrite-books

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill that rewrites public domain books for modern audiences. It extracts chapters from an EPUB, rewrites them in parallel using multiple AI agents, adds editorial footnotes, performs holistic review, and reassembles a new EPUB with Kobo-compatible popup footnotes.

## What it does

1. **Extracts** chapters from a source EPUB (local file or remote calibre library)
2. **Rewrites** each chapter for modern readers — modernized language, tighter pacing, natural dialogue
3. **Line-edits** each rewrite with an adversarial "misreading" pass to catch ambiguous prose
4. **Annotates** with editorial footnotes comparing the adaptation to the original
5. **Reviews** the full manuscript holistically for consistency, pacing, and narrative arc
6. **Reassembles** a valid EPUB with Kobo-compatible popup footnotes and endnotes
7. Optionally **uploads** to a calibre server and converts to KEPUB
8. Optionally **generates an audiobook** (M4B with chapter markers) using macOS TTS

The entire pipeline is orchestrated by Claude Code, spawning 100-200+ sub-agents depending on book length. A typical novel takes 30-60 minutes.

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- Python 3 (for EPUB extraction and assembly scripts)
- `zip`/`unzip` (for EPUB packaging)
- Optional: `ffmpeg` + `ffprobe` (for audiobook generation)
- Optional: SSH access to a calibre server (for remote EPUB fetch/upload)

## Install

```bash
git clone https://github.com/calebjedhugo/rewrite-books.git
cd rewrite-books
./install.sh
```

This copies the skill files to `~/.claude/commands/` and creates a config file at `~/.claude/commands/rewrite-book/config.json`.

### Configuration

Edit `~/.claude/commands/rewrite-book/config.json` to configure:

- **`working_dir`**: Where book projects are created (default: `~/Documents`)
- **`epub_source.type`**: `"local"` (you provide an EPUB path) or `"calibre"` (fetch from a remote calibre library via SSH)
- **`upload`**: Auto-upload finished EPUBs to a calibre server, with optional KEPUB conversion
- **`audiobook_sync`**: Sync generated M4B audiobooks to a remote server

The defaults work out of the box — you'll just be asked to provide a local EPUB path.

### Permissions

The pipeline generates hundreds of tool calls. To avoid being prompted for each one, add these to your `~/.claude/settings.local.json` under `allowedTools`:

**Always needed:**
- `Bash(cp *)`, `Bash(cp -r *)` — file copying
- `Bash(unzip:*)`, `Bash(zip *)` — EPUB handling
- `Bash(python *)`, `Bash(python -c:*)` — extraction/build scripts
- `Bash(wc:*)`, `Bash(mkdir:*)`, `Bash(rm:*)` — filesystem ops
- `Write(~/Documents/**)`, `Edit(~/Documents/**)` — project file writes (adjust to match your `working_dir`)

**Only if using remote calibre:**
- `Bash(ssh:*)`, `Bash(scp:*)` — remote operations

**Only for audiobook generation:**
- `Bash(say:*)`, `Bash(afconvert:*)`, `Bash(ffmpeg:*)`, `Bash(ffprobe:*)` — TTS and audio conversion

## Usage

In Claude Code:

```
/rewrite-book journey to the center of the earth
```

Or just `/rewrite-book` and it will ask you which book to rewrite.

The skill is resumable — if interrupted, re-invoke it and it picks up where it left off.

## How it works

The pipeline runs in 8 phases:

| Phase | What happens |
|-------|-------------|
| 0 | Fetch EPUB, extract chapters, create style guide + chapter bible |
| 0.9 | Checkpoint — user reviews setup before committing to 100+ agents |
| 1 | Rewrite all chapters (parallel, batches of 2) with line-edit passes |
| 2 | Write editorial footnotes for each chapter (parallel, batches of 2) |
| 3 | Iteration loop — re-rewrite any chapters that failed quality gate |
| 4 | High-level holistic review of full manuscript |
| 5 | Iteration loop — revise flagged chapters, re-review |
| 6 | Reassemble EPUB with footnotes, optional calibre upload |
| 7 | Optional audiobook generation (macOS TTS) |
| 8 | Final report |

Books over 35 chapters are automatically split across multiple manager agents to avoid context exhaustion.

## Project structure

```
rewrite-books/
  skill/                    # Claude Code skill files (copied to ~/.claude/commands/ by install.sh)
    rewrite-book.md         # Main orchestrator instructions
    setup.md                # Phase 0: extraction and setup
    agent-templates.md      # Rewrite, line-edit, footnote, and review agent prompts
    assembly.md             # Phase 6: EPUB rebuild and upload
    audiobook.md            # Phase 7: audiobook generation
  epub-utils/               # Shared EPUB utilities (stdlib-only Python)
    epub_utils.py           # Build, footnote insertion, endnotes, Kobo quirks
    CLAUDE.md               # API documentation for the utilities
  config.example.json       # Template config (install.sh creates the real one)
  install.sh                # Installer script
```

Each book project gets its own directory under `working_dir`:

```
~/Documents/journey-to-the-center-of-the-earth/
  original.epub
  extracted/                # Raw EPUB contents
  rewrite/
    style-guide.md          # Voice and tone rules for this book
    chapter-bible.md        # Characters, locations, terms, timeline
    chapter-map.json        # EPUB structure mapping for reassembly
    chapters/
      ch01/
        original.txt        # Extracted chapter text
        rewrite.txt         # Rewritten chapter
        footnotes.json      # Editorial footnotes
        status.txt          # "pending" / "approved" / "needs_work"
      ch02/ ...
    high-level/
      review-round-01.md    # Holistic review notes
    Book Title (rewritten).epub
```

## Example output

The `examples/` directory contains sample output from a completed run on *Twenty Thousand Leagues Under the Sea*. It includes:

- **Global files**: style guide, chapter bible, chapter map, progress tracker, front matter, high-level reviews
- **Chapter 1**: the full set of per-chapter artifacts (original text, rewrite, footnotes, line-edit feedback, footnote verification, status)
- **Final EPUB**: the reassembled book with all 46 chapters rewritten and 214 editorial footnotes

This gives you a concrete picture of what the pipeline produces before running it yourself.

## epub-utils

The `epub-utils/` directory contains a standalone Python library (stdlib only, no dependencies) that handles EPUB assembly. Key features:

- Replaces chapter content in existing EPUB structure
- Inserts Kobo-compatible popup footnote markers using 6 quote-matching strategies
- Generates endnotes page with proper EPUB3 semantic markup
- Handles namespace declarations, manifest/spine/toc updates
- Validates chapter-map.json against the extracted EPUB

See `epub-utils/CLAUDE.md` for the full API.

## License

The skill code and epub-utils are provided as-is. This tool is intended for use with public domain works (e.g., Project Gutenberg texts).
