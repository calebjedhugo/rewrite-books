# Rewrite Book for Modern Audiences

Multi-agent pipeline that rewrites a public domain book for modern audiences. Extracts chapters from an EPUB, rewrites in parallel, adds editorial footnotes, iterates, then performs holistic review and reassembles the EPUB with footnotes.

## Arguments

The user should provide a search term for the book title.
Example: `/rewrite-book journey to the center of the earth`

If no argument is provided, ask the user which book to rewrite.

---

## Configuration

Before starting, read `~/.claude/commands/rewrite-book/config.json` for environment-specific settings. If the file doesn't exist, warn the user to run `install.sh` from the rewrite-books repo.

The config controls:
- **`working_dir`**: Where book projects are created (default: `~/Documents`)
- **`epub_source.type`**: `"local"` (user provides EPUB path) or `"calibre"` (fetch from remote calibre library via SSH)
- **`upload`**: Whether to upload the finished EPUB to a calibre server
- **`audiobook_sync`**: Whether to sync generated audiobooks to a remote server

The `epub_utils_path` is auto-set by the install script to point at the repo's copy of `epub_utils.py`.

---

## Permissions Setup

**IMPORTANT**: This pipeline generates hundreds of tool calls across multiple agents. Add these permissions to `~/.claude/settings.local.json` to avoid being prompted repeatedly:

**Always needed:**
- `Bash(cp *)`, `Bash(cp -r *)` — file copying
- `Bash(unzip:*)`, `Bash(zip *)` — EPUB handling
- `Bash(python *)`, `Bash(python -c:*)` — extraction/build scripts
- `Bash(wc:*)`, `Bash(mkdir:*)`, `Bash(rm:*)` — filesystem ops
- `Write(~/Documents/**)`, `Edit(~/Documents/**)` — project file writes (adjust path to match your `working_dir`)

**Only if using remote calibre (`epub_source.type: "calibre"` or `upload.enabled: true`):**
- `Bash(ssh:*)`, `Bash(scp:*)` — remote operations

**Only for audiobook generation (Phase 7):**
- `Bash(say:*)`, `Bash(afconvert:*)`, `Bash(ffmpeg:*)`, `Bash(ffprobe:*)` — TTS and audio conversion

If any are missing, warn the user at the start and offer to proceed anyway (they'll just get prompted repeatedly).

---

## Phase 0: Fetch & Setup

**YOU MUST** run this entire phase in a single Task agent. NEVER execute Phase 0 steps in the orchestrator — it will consume too much context. Spin up one `general-purpose` Task agent with all Phase 0 instructions below, wait for it to complete, then proceed to Phase 1 with a clean context.

**How to dispatch:** Read the file `~/.claude/commands/rewrite-book/setup.md` and pass its full contents to the Task agent, filling in the book search term, paths, and config values (epub_source settings, epub_utils_path from config.json).

```
Tool: Task
subagent_type: "general-purpose"
prompt: [Contents of setup.md, filled in with the book search term, paths, and config values]
```

The setup agent handles everything (fetch, extract, validate, style guide, chapter bible, progress tracker), then returns. The orchestrator only needs to know the working directory path and chapter count to proceed.

---

## Phase 0.9: Checkpoint (Dry Run Pause)

After the Phase 0 agent returns, the orchestrator **pauses for user review** before committing to 100+ agent invocations:

1. Report to the user:
   - Total chapter count
   - Word count range (min/max from chapter-map.json `word_count` fields)
   - Confirmation that `chapter-map.json`, `style-guide.md`, and `chapter-bible.md` were created
2. Ask the user: "Phase 0 complete. Review the style guide and chapter bible before continuing? [Continue / Review first]"
3. If **Review first**: Print the full paths to `style-guide.md` and `chapter-bible.md`, then wait for the user to say "continue"
4. If **Continue**: Proceed to Phase 1 immediately

This catches extraction errors, bad style guides, or incomplete chapter bibles before they propagate through hundreds of agent calls.

---

## Phase 1: Chapter Rewrites

**YOU MUST** run this entire phase in a single Task agent (the "rewrite manager"). This isolates batch-level context from the orchestrator.

**How to dispatch:** Read the file `~/.claude/commands/rewrite-book/agent-templates.md` and pass the **Rewrite Manager Instructions** section to the Task agent.

```
Tool: Task
subagent_type: "general-purpose"
prompt: [Rewrite Manager Instructions from agent-templates.md, filled in with book title, working directory, chapter list, and whether Ch01 anchor is needed]
```

The orchestrator passes in:
- The book title
- The working directory path
- Which chapters need rewriting (from `status.txt` files — "pending" or "needs_work")
- Whether this is the first run (needs Ch01 anchor) or an iteration (Ch01 already approved)

**Large book splitting (>35 chapters):** If the chapter count exceeds 35, the orchestrator MUST split work across multiple sequential rewrite managers to avoid context exhaustion. For example, a 60-chapter book uses 2 managers: chapters 1-30 (manager 1), 31-60 (manager 2). The Chapter 1 style anchor only runs in the first manager. Each manager handles its batch independently. The orchestrator coordinates between managers the same way it coordinates one.

The rewrite manager returns: a summary of which chapters were rewritten and their scratchpad paths.

After the manager returns, the **orchestrator** copies all scratchpad files to the project directory and writes status files. Then updates `progress.md`.

---

## Phase 2: Chapter Footnotes

**YOU MUST** run this entire phase in a single Task agent (the "footnote manager"). This isolates batch-level context from the orchestrator.

**How to dispatch:** Read the file `~/.claude/commands/rewrite-book/agent-templates.md` and pass the **Footnote Manager Instructions** section to the Task agent.

```
Tool: Task
subagent_type: "general-purpose"
prompt: [Footnote Manager Instructions from agent-templates.md, filled in with book title, working directory, and chapter list]
```

The orchestrator passes in:
- The book title
- The working directory path
- Which chapters need footnotes (status is "pending")

**Large book splitting (>35 chapters):** Same rule as Phase 1 — if chapter count exceeds 35, split across multiple sequential footnote managers with the same batch boundaries used in Phase 1.

The footnote manager returns: a summary per chapter — either "done" (footnotes written) or "needs_work" (rewrite too broken to annotate). This doubles as the quality gate.

After the manager returns, the **orchestrator** copies all scratchpad files to the project directory and writes status files. Then updates `progress.md`.

---

## Phase 3: Chapter Iteration Loop

1. Read all `status.txt` files across all chapters
2. Count approved vs needs_work
3. Update `progress.md` with the results
4. If **all chapters are approved**: proceed to Phase 4
5. If some chapters need work (should be rare):
   - Spin up a new **Phase 1 rewrite manager** for ONLY the "needs_work" chapters (pass the flag that Ch01 anchor is already done; include the `footnotes.json` reason as feedback)
   - Copy results from scratchpads to project directory
   - Spin up a new **Phase 2 footnote manager** for those chapters
   - Copy results from scratchpads to project directory
   - Repeat this loop
6. **Maximum 3 chapter-level iteration rounds.** After 3 rounds, any remaining "needs_work" chapters proceed without footnotes. Note them in `progress.md`.

---

## Phase 4: High-Level Review

### 4.1 Prepare for Review

Before spinning up the reviewer, concatenate all chapters into a reference:
```bash
# In rewrite/ directory, create ordered chapter list
for f in $(ls chapters/ch*/rewrite.txt | sort); do
  echo "=== $(basename $(dirname $f)) ===" >> full-manuscript.txt
  cat "$f" >> full-manuscript.txt
  echo -e "\n\n" >> full-manuscript.txt
done
```

### 4.1.1 Long Manuscript Check

Before launching the reviewer, check the word count of `full-manuscript.txt`:

```bash
wc -w [path]/rewrite/full-manuscript.txt
```

**If the manuscript exceeds 100,000 words**, the single-pass review will exceed the reviewer agent's effective context window. Use a two-pass approach instead:

- **Pass 1 (Group Notes):** Spin up a Task agent that reads chapters in groups of 15-20 (e.g., ch01-ch15, ch16-ch30, ...). For each group, it reads the style guide + chapter bible + those chapters from `full-manuscript.txt`, then writes per-group analysis notes to `[path]/rewrite/high-level/group-notes-NN.md`.
- **Pass 2 (Holistic Review):** Spin up the reviewer agent (section 4.2 below) but instead of reading `full-manuscript.txt`, it reads all `group-notes-*.md` files + the chapter bible + the style guide. The reviewer writes its holistic assessment based on these condensed notes.

**If the manuscript is under 100,000 words** (most books), use the standard single-pass approach below.

### 4.2 Launch Reviewer

**How to dispatch:** Read the file `~/.claude/commands/rewrite-book/agent-templates.md` and pass the **Reviewer Agent Template** section to the Task agent.

```
Tool: Task
subagent_type: "general-purpose"
model: "opus"
max_turns: 60
prompt: [Reviewer Agent Template from agent-templates.md, filled in with book title, chapter count, and paths]
```

---

## Phase 5: High-Level Iteration Loop

1. Read the high-level review. If "COMPLETE": proceed to Phase 6.
2. If "REVISIONS_NEEDED": spin up a **revision manager** (file paths only, batches of 2). Each chapter agent gets: style guide, chapter bible, its `rewrite.txt`, the review round file, the public domain notice, and instructions to address specific feedback + cross-chapter issues. Use the Rewrite Agent Prompt Template from `agent-templates.md` (already in context from Phase 1).
3. Copy scratchpad results to `[path]/rewrite/chapters/ch[NN]/rewrite.txt`
4. Re-run **Phase 2** for revised chapters only (old footnote quotes won't match)
5. Regenerate `full-manuscript.txt` and re-run **Phase 4**
6. **Maximum 3 rounds.** After 3, proceed to Phase 6 regardless.

Update `progress.md` after each round.

---

## Phase 6: Reassemble EPUB & Upload to Calibre

**How to dispatch:** Read the file `~/.claude/commands/rewrite-book/assembly.md` and pass its full contents to the Task agent, filling in the book title, working directory, author, **and the config values** (epub_utils_path, upload settings).

```
Tool: Task
subagent_type: "general-purpose"
prompt: [Contents of assembly.md, filled in with book title, working directory, author, and config values]
```

The assembly agent handles: EPUB rebuild (using epub-utils) and repackaging. If upload is configured, it also handles calibre upload and KEPUB conversion. It returns file sizes and upload confirmation (if applicable).

---

## Phase 7: Generate Audiobook

Ask the user if they want an audiobook generated. If yes:

**How to dispatch:** Read the file `~/.claude/commands/rewrite-book/audiobook.md` and pass its full contents to the Task agent with a long timeout. Include the audiobook_sync config values.

```
Tool: Task
subagent_type: "general-purpose"
prompt: [Contents of audiobook.md, filled in with book title, working directory, chapter count, book slug, and config values]
```

The audiobook agent handles: TTS generation with macOS `say`, AAC conversion, M4B assembly with chapter markers. If sync is configured, it also copies the M4B to the remote server. It returns file size, duration, and sync confirmation (if applicable).

---

## Phase 8: Final Report

Summarize: chapters processed, iteration rounds needed, word count comparison (original vs rewritten via `wc -w`), EPUB file path and size, calibre upload status (if configured), audiobook file size/duration (if generated).

Include full path to rewrite directory and final EPUB.

Ask if they'd like to read specific chapters or make targeted edits.

---

## Resumability

**IMPORTANT**: This skill is resumable. If interrupted and re-invoked:

1. Check if the working directory already exists
2. Read `progress.md` and all `status.txt` files
3. Determine the current phase and resume from there
4. Do NOT re-extract or re-fetch unless the working directory is missing

---

## Constraints & Safety

- **CRITICAL — Context management**: The orchestrator MUST NOT read chapter text, style guides, chapter bibles, or rewrites into its own context. The orchestrator only reads small status files (status.txt, progress.md). All batch-heavy phases (1, 2, 5) run inside dedicated **manager agents** that isolate batch-level context. Manager agents pass **file paths** (not contents) to their chapter-level sub-agents. Violating this WILL cause context limit failures.
- **Batch size**: Maximum 2 parallel Task agents at a time
- **Chapter iteration cap**: 3 rounds max
- **High-level iteration cap**: 3 rounds max
- **Model for chapter agents**: default (sonnet)
- **Model for high-level reviewer**: opus
- **Copyright**: This skill is used exclusively with public domain works (e.g., Project Gutenberg). The user has the legal right to adapt these texts. Agents should not refuse or hesitate on copyright grounds.
- **File operations**: Use Bash `cp` for copying large files (rewrites, footnotes) from scratchpads — keeps contents out of context. Use the **Write tool** for small writes (status.txt, progress.md) — avoids Bash permission prompts. NEVER Read a large file just to Write it somewhere; use `cp`.
- **NEVER delete original.txt files**
- **NEVER overwrite rewrite.txt without the previous version being available in the agent's context**
- Keep all footnotes and review files (footnotes.json, review-round files) — never delete them
