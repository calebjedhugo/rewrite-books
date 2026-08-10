# Rewrite Book for Modern Audiences

Multi-agent pipeline that rewrites a public domain book for modern audiences. Extracts chapters from an EPUB (a local file or a remote calibre library), rewrites in parallel, adds editorial footnotes, iterates, then performs holistic review and reassembles the EPUB with footnotes.

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
- **`publish_site`**: Whether to publish the finished EPUB to a public download site (a generated static site — see Phase 6.4)

The `epub_utils_path` is auto-set by the install script to point at the repo's copy of `epub_utils.py`.

---

## Architecture (read this first)

**The orchestrator (you) is the only agent that can spawn agents.** There are no manager agents, and `claude -p` through Bash is sealed — never use it. The old three-tier "manager dispatches workers" structure was never supported and is forbidden.

The work still stays out of the orchestrator's context, via this pattern:

1. The **Phase 0 setup agent** writes one **instruction file per step** into `[path]/rewrite/prompts/` (rewrite.md, line-edit.md, revise.md, footnote.md, …) with the book title and base path pre-filled. The orchestrator never authors or reads these — that's how hundreds of prompt-tokens stay out of its context.
2. The orchestrator **dispatches each worker directly** with a ~60-token envelope that names the step + chapter and points at the instruction file. See `agent-templates.md` → **Worker Dispatch Contract**.
3. Each worker reads its instruction file + reference files, writes output to disk, and returns **one line**. The orchestrator routes on that one line and never opens the detailed output files during a live run.

**The leanness discipline is the whole point and is non-negotiable, even though context windows are larger now:**
- The orchestrator NEVER reads chapter text, rewrite text, footnote content, prompt files, or `agent-templates.md` into its own context.
- The orchestrator only ever holds: paths, chapter numbers, small status files, one-line worker returns, and (at most once per high-level round) a review file.
- Workers communicate forward by writing files; the orchestrator routes on one-liners. Do not "simplify" by piping file contents through the orchestrator.

You drive the per-chapter loops yourself, as **waves** across the book (described in each phase). Concurrency: dispatch up to **4 workers in parallel** by placing multiple Agent calls in one message.

---

## Permissions Setup

This pipeline generates many Agent dispatches and Bash/file calls. Add these to `~/.claude/settings.local.json` to avoid being prompted repeatedly:

**Always needed:**
- `Bash(cp *)`, `Bash(cp -r *)` — file copying
- `Bash(unzip:*)`, `Bash(zip *)` — EPUB handling
- `Bash(python *)`, `Bash(python -c:*)` — extraction/build/gate scripts
- `Bash(wc:*)`, `Bash(mkdir:*)`, `Bash(rm:*)` — filesystem ops
- `Write(<working_dir>/**)`, `Edit(<working_dir>/**)` — project file writes (match your `working_dir`, e.g. `~/Documents/**`)

**Only if using remote calibre (`epub_source.type: "calibre"` or `upload.enabled: true`):**
- `Bash(ssh:*)`, `Bash(scp:*)` — remote operations

**Only if publishing to a download site (`publish_site.enabled: true`):**
- `Bash(rsync:*)` — deploy the generated site to the web host

**Only for audiobook generation (Phase 7):**
- `Bash(say:*)`, `Bash(afconvert:*)`, `Bash(ffmpeg:*)`, `Bash(ffprobe:*)` — TTS and audio conversion

If any are missing, warn the user at the start and offer to proceed anyway (they'll just get prompted repeatedly).

---

## Phase 0: Fetch & Setup

**YOU MUST** run this entire phase in a single Agent. NEVER execute Phase 0 steps in the orchestrator — it consumes too much context. Spin up one Agent with all Phase 0 instructions, wait for it to complete, then proceed with a clean context.

**How to dispatch:** Read `~/.claude/commands/rewrite-book/setup.md` and pass its full contents to the Agent, filling in the book search term, paths, and config values (`epub_source` settings, `working_dir`, `epub_utils_path` from config.json).

```
Tool: Agent
subagent_type: "general-purpose"
model: "opus"
prompt: [Contents of setup.md, filled in with the book search term, paths, and config values]
```

The setup agent handles: fetch, extract, validate, style guide, chapter bible, progress tracker, **and compiling the per-step instruction files into `[path]/rewrite/prompts/` plus the `gates.py` script** (its final steps). It returns only: the working directory path, the chapter count, the word-count range, and confirmation that `chapter-map.json`, `style-guide.md`, `chapter-bible.md`, the `prompts/` files, and `gates.py` were created. That small return is all the orchestrator needs.

---

## Phase 0.9: Checkpoint (Dry Run Pause)

After Phase 0 returns, **pause for user review** before committing to many agent invocations:

1. Report: total chapter count, word-count range, and confirmation that `chapter-map.json`, `style-guide.md`, `chapter-bible.md`, `prompts/`, and `gates.py` were created.
2. Ask: "Phase 0 complete. Review the style guide and chapter bible before continuing? [Continue / Review first]"
3. If **Review first**: print full paths to `style-guide.md` and `chapter-bible.md`, then wait for "continue".
4. If **Continue**: proceed to Phase 1.

This catches extraction errors, bad style guides, or incomplete chapter bibles before they propagate.

---

## Phase 1: Chapter Rewrites (orchestrator-driven waves)

You drive this directly with the Agent tool. Workers read `prompts/rewrite.md`, `prompts/line-edit.md`, `prompts/revise.md`. See the **Worker Dispatch Contract** in `agent-templates.md` for the envelope, the one-line return contract, and the model map. (You do NOT need to read the templates themselves — only the contract section, once, to learn the envelope format. Read just that section if needed.)

### 1.0 Pipeline cost estimate (spans Phases 1–2)

Before starting, report to the user the whole-pipeline estimate: chapter count, average word count, and rough agent count (best case ≈ N rewrite + N line-edit [Phase 1] + N footnote + N footnote-line-edit + N footnote-verify [Phase 2] + 1 review; worst case adds up to 3 iteration rounds). Then proceed.

### The gated revise-cycle (used in 1.1 and 1.2)

**Read this first — it is the heart of the quality loop, and the place the previous design silently failed.** The line-edit worker is *adversarial*: it is told to misread the chapter and will return `has_issues` on almost every pass. That is expected — `has_issues` is the normal state, NOT a failure. The thing that matters is whether the flagged fixes actually land in `rewrite.txt`. You do not get to trust that they did; you **verify it deterministically** with `gates.py`.

One revise-cycle for a set of chapters:

1. **Line-edit:** dispatch line-edit workers (sonnet). Collect returns (`clean` / `has_issues`).
2. **JSON gate:** run `python [path]/rewrite/gates.py json-valid …` on **every** chapter's `line-edit.json` in this cycle — NOT only the `has_issues` ones. A worker can return `clean` while having written a malformed file (this is exactly the ch15-class bug from the prior run); validating only `has_issues` files would miss it. Any `BAD` → re-dispatch that line-edit worker. Repeat until all `OK`.
3. **Revise:** for `has_issues` chapters only, dispatch revise workers (opus). Each returns `revise: applied k/n`.
4. **Apply gate (MANDATORY):** run `python [path]/rewrite/gates.py revise-applied ch{NN} …` for every chapter just revised. Read the tiny table.
   - `APPLIED` → fix landed, chapter advances.
   - `NOT-APPLIED (j/n flagged quotes still present)` → the revise worker did not actually change the flagged text. **Re-dispatch the revise worker for that chapter** (up to 2 retries). If still `NOT-APPLIED` after 2 retries, log it in `progress.md` and move on — do not silently accept it.

**ORDERING INVARIANT (critical):** `gates.py revise-applied` checks the findings in `line-edit.json`, which the *next* line-edit round overwrites. So for any given chapter you MUST complete steps 3–4 (revise + apply-gate + its retries) on the current `line-edit.json` BEFORE you dispatch that chapter's next line-edit round. Run the cycle as a barrier across the batch — all chapters finish step 4 before any chapter starts the next cycle's step 1 — so the gate never checks the wrong round's findings.

A chapter is "cycle-complete" when its last line-edit returned `clean`, OR it has been through **2 revise-cycles** (the cap), each ending in `APPLIED`. Never end Phase 1 for a chapter on a `NOT-APPLIED` gate result without logging it.

Why the gate, not the verdict: the final on-disk `line-edit.json` always tends to say `has_issues` (the adversary keeps finding things), so the verdict can't tell you whether anything was fixed. `gates.py revise-applied` can — it checks that the flagged quotes are gone from the text. Route on the gate.

### 1.1 Chapter 1 — Style Anchor (first run only)

**YOU MUST** fully process Chapter 1 alone, before any other chapter, to establish the tone all others match.

1. Dispatch the rewrite worker for ch01 (`model: opus`). Wait for `ch01 rewrite: done`.
2. Run the **gated revise-cycle** above on `[ch01]` (max 2 cycles).
3. `[path]/rewrite/chapters/ch01/rewrite.txt` is now the tone reference. Proceed to 1.2.

### 1.2 Remaining chapters — wave model

Process ch02…chN as waves across the whole book, batching up to 4 workers per message. Each wave advances every chapter one step; route each chapter by its worker's one-line return and by the gates.

- **Wave A — rewrite:** dispatch rewrite workers (opus) for all pending chapters, 4 at a time. Collect `chNN rewrite: done`.
- **Waves B–… — gated revise-cycles:** run the gated revise-cycle (above) across all rewritten chapters, batching workers 4 at a time within each step. Run up to 2 cycles; the `revise-applied` gate after every revise wave is mandatory and chapters failing it are re-dispatched before you move on.

Track per-chapter state in your own working notes (chapter number → last completed step, last gate result). Do NOT read chapter files to determine state — the one-line returns plus the gate tables are authoritative during a live run.

Workers write their own outputs. After Phase 1, every ch02+ has a `rewrite.txt` whose Phase-1 flagged quotes have been verified gone (or logged as unresolved). (Status.txt is written in Phase 2.)

After Phase 1 completes, **update `progress.md`** with REAL state: per-chapter cycles run and final gate result. Do NOT write "2 rounds each, applied" unless the gate tables actually said so — the prior run's `progress.md` claimed iterations that never happened.

**Large books (>35 chapters):** the wave model already scales — keep batching 4 at a time. If you are worried about your own turn count, process the book in chapter ranges (e.g., ch02–ch35, then ch36–chN), running the full rewrite + gated-cycle set on each range before moving on.

---

## Phase 2: Chapter Footnotes (orchestrator-driven waves)

Same wave model, using `prompts/footnote.md`, `prompts/footnote-line-edit.md`, `prompts/footnote-revise.md`, `prompts/footnote-verify.md`. Run for all chapters that have an approved/complete `rewrite.txt`.

- **Wave E — footnote:** dispatch footnote workers (opus), 4 at a time. Split returns into `done` vs `needs_work`. A `needs_work` chapter means the rewrite is too broken to annotate — set it aside for Phase 3. Then run `python [path]/rewrite/gates.py json-valid …/footnotes.json …` on the `done` chapters; re-dispatch any `BAD`.
- **Wave F — footnote line-edit (round 1):** for `done` chapters, dispatch footnote-line-edit workers (sonnet). Split `clean` vs `has_issues`. (JSON-gate the resulting `footnotes-line-edit.json` files; re-dispatch any `BAD`.)
- **Wave G — footnote revise:** for `has_issues` chapters, dispatch footnote-revise workers (opus).
- **Wave H — footnote line-edit (round 2):** re-run on revised chapters; proceed regardless after this round (max 2 rounds).
- **Wave I — footnote verify:** dispatch footnote-verify workers (sonnet) for all `done` chapters. The verifier validates every `quote` is an exact substring of `rewrite.txt` (repairing or dropping mismatches) and writes the corrected array straight to `footnotes.json` — so a `has_corrections` return needs no orchestrator action beyond noting it.
- **Wave J — substring gate (MANDATORY):** run `python [path]/rewrite/gates.py footnote-substrings`. Every chapter must be `OK` or `SKIP`. Any `MISMATCH` line means a footnote quote will be silently dropped from the EPUB — re-dispatch that chapter's footnote-verify worker until the gate is clean, **max 2 re-dispatches per chapter**; on the 3rd attempt dispatch a footnote-verify pass instructed to DROP the unmatchable footnote(s) rather than re-anchor (the verifier template permits dropping), which guarantees convergence. **Do not proceed to Phase 6 with any MISMATCH outstanding.** (The prior run shipped 5 broken quotes because nothing enforced this.)

Note — accepted asymmetry: the footnote *line-edit/revise* loop (Waves F–H) fixes the footnote *note prose* and is NOT apply-gated the way chapter revises are (only quote integrity is gated, via Wave J). Footnote prose is low-stakes relative to the book text, so this is a deliberate scope choice, not an oversight.

**Finalize status:** after Wave J passes, the orchestrator writes each chapter's `status.txt` itself with the **Write tool** (tiny write: `approved` or `needs_work`) — it already knows every chapter's outcome from the one-line returns and gate tables, so no extra dispatch is needed. `approved` = footnote done + verified + substring-clean; `needs_work` = footnote worker returned `needs_work`.

After Phase 2, **update `progress.md`** with real per-chapter outcomes (verify verdicts + substring-gate result).

---

## Phase 3: Chapter Iteration Loop

1. From your own tracking (and `status.txt` if resuming), count `approved` vs `needs_work`.
2. Update `progress.md`.
3. If **all approved**: proceed to Phase 4.
4. If some are `needs_work` (should be rare):
   - Re-run **Phase 1 waves** for ONLY those chapters (the rewrite worker auto-detects the re-rewrite case from the existing `rewrite.txt` + `footnotes.json` reason). The ch01 anchor is already done — do not redo it.
   - Re-run **Phase 2 waves** for those chapters.
   - Repeat.
5. **Maximum 3 chapter-level rounds.** After 3, any remaining `needs_work` chapters proceed without footnotes. Note them in `progress.md`.

**status.txt semantics:** a chapter is `approved` or `needs_work` only after Phase 2 finalizes it. Any chapter still `pending` (the Phase 0 default) never completed Phase 2 — on resume, treat `pending` as "re-run from Phase 1," not "done."

---

## Phase 4: High-Level Review

### 4.1 Prepare for review

Concatenate all chapters into a single reference via Bash (content goes to a file, never into your context):
```bash
# In rewrite/ directory, create ordered chapter list
for f in $(ls chapters/ch*/rewrite.txt | sort); do
  echo "=== $(basename $(dirname $f)) ===" >> full-manuscript.txt
  cat "$f" >> full-manuscript.txt
  echo -e "\n\n" >> full-manuscript.txt
done
```

### 4.1.1 Long manuscript check

```bash
wc -w [path]/rewrite/full-manuscript.txt
```

**If > 100,000 words**, a single-pass review exceeds the reviewer's effective window. Use two passes:
- **Pass 1 (group notes):** dispatch an Agent (`model: sonnet`) that reads chapters in groups of 15–20, writing per-group analysis to `[path]/rewrite/high-level/group-notes-NN.md`.
- **Pass 2 (holistic):** dispatch the reviewer (4.2) but tell it to read the `group-notes-*.md` files + chapter bible + style guide instead of `full-manuscript.txt`.

**If ≤ 100,000 words** (most books), use the standard single-pass below.

### 4.2 Launch reviewer

Dispatch the reviewer worker directly (it reads `prompts/reviewer.md`). Give it the round number in the envelope so it writes `review-round-[NN].md`.

```
Tool: Agent
subagent_type: "general-purpose"
model: "opus"
prompt: [Worker envelope for the reviewer — step "reviewer", round NN, paths. See Worker Dispatch Contract.]
```

The reviewer returns one line: `review: COMPLETE`, or `review: REVISIONS_NEEDED ch03 ch07 …`. Route on that — you do not need to open the review file (the revision workers read it themselves).

---

## Phase 5: High-Level Iteration Loop

1. If the reviewer returned `review: COMPLETE`: proceed to Phase 6.
2. If `review: REVISIONS_NEEDED ch03 ch07 …`: dispatch high-level revision workers (`model: opus`, `prompts/revise-highlevel.md`) for exactly those chapters, 4 at a time. Each reads its section of the review file + the cross-chapter issues itself.
3. Re-run **Phase 2 waves** for the revised chapters only (old footnote quotes won't match the new text).
4. Regenerate `full-manuscript.txt` and re-run **Phase 4**.
5. **Maximum 3 rounds.** After 3, proceed to Phase 6 regardless.

Update `progress.md` after each round. (Reading the small review file once per round is acceptable if you want a human-readable summary for the user — but routing only needs the one-liner.)

---

## Phase 6: Reassemble EPUB & Upload to Calibre

**Pre-build backstop (MANDATORY):** before dispatching assembly, run `python [path]/rewrite/gates.py footnote-substrings` one more time (Phase 5 may have changed text). If any chapter reports `MISMATCH`, fix it (re-dispatch footnote-verify) before building — a mismatch here means that footnote is silently dropped from the published EPUB. The assembly agent must **report any unmatched footnotes as an error in its return, not drop them silently**; if it reports misses, treat that as a failed build and resolve before finalizing.

**How to dispatch:** Read `~/.claude/commands/rewrite-book/assembly.md` and pass its full contents to the Agent, filling in the book title, working directory, author, **and the config values** (`epub_utils_path`, `upload` settings, and `publish_site` settings if enabled).

```
Tool: Agent
subagent_type: "general-purpose"
model: "sonnet"
prompt: [Contents of assembly.md, filled in with book title, working directory, author, and config values]
```

The assembly agent handles: EPUB rebuild (using epub-utils) and repackaging. If `upload` is configured, it also handles calibre upload and KEPUB conversion. If `publish_site` is configured, it also publishes the finished EPUB to the public download site (Phase 6.4). It returns file sizes, upload confirmation (if applicable), and the published URL (if applicable).

---

## Phase 7: Generate Audiobook

Ask the user if they want an audiobook. If yes:

**How to dispatch:** Read `~/.claude/commands/rewrite-book/audiobook.md` and pass its full contents to the Agent with a long timeout. Include the `audiobook_sync` config values.

```
Tool: Agent
subagent_type: "general-purpose"
model: "sonnet"
prompt: [Contents of audiobook.md, filled in with book title, working directory, chapter count, book slug, and config values]
```

The audiobook agent handles: TTS with macOS `say`, AAC conversion, M4B assembly with chapter markers. If sync is configured, it also copies the M4B to the remote server. It returns file size, duration, and sync confirmation (if applicable).

---

## Phase 8: Final Audit

Before reporting success, confirm the run actually went according to plan. This has two halves: the orchestrator audits the **mechanics** itself (cheap, objective, can't be fudged), and **delegates** the judgment of **quality** to fresh agents. Context budget is generous (a full 22-chapter run used ~16%) — but spend that budget on delegated audit agents, NOT on the orchestrator reading the book. The orchestrator stayed lean precisely because it never read chapter content; reading the whole manuscript now to self-grade would waste that property and amount to self-review.

### 8.1 Deterministic self-audit (orchestrator, MANDATORY)

Run `python [path]/rewrite/gates.py audit`. It sweeps every gate across all chapters plus structural completeness, status-vs-gate consistency, and high-level-review currency, and prints a compact report ending in `AUDIT: ALL-CLEAR` or `AUDIT: FAILURES FOUND`.

- **`ALL-CLEAR`** → mechanics verified; proceed to 8.2.
- **`FAILURES FOUND`** → the run is NOT done, regardless of what `progress.md` says. Each failure line names what to fix, then re-audit:
  - `NOT-APPLIED` / `BAD` → resume the Phase 1 gated revise-cycle for that chapter (regenerate a `BAD` line-edit first).
  - `MISMATCH` → resume Phase 2 Wave I/J (footnote-verify) for that chapter.
  - `MISSING` → that phase never produced the file; resume it.
  - `STALE` → a `rewrite.txt` changed after the last high-level review (e.g. a resume applied line-edit fixes on top of a `COMPLETE` review). The review no longer reflects the shipped text — **re-run Phase 4** against the current manuscript, then re-audit. This catch is deliberate: a late edit silently invalidating a prior review is exactly the kind of judgment call the gates exist to remove.
  - A chapter whose `status.txt` says `approved` but appears under a failure is a status-vs-reality contradiction — the gate is right, the status is wrong; fix the chapter and correct the status.

  Do not write the final report until this is `ALL-CLEAR`.

### 8.2 Delegated quality audit (fresh subagents, standard)

The deterministic gates cannot judge whether the adversarial reviews *genuinely engaged* — a lazy line-editor that returns `clean` everywhere passes `revise-applied` trivially while doing nothing. That judgment needs reading content, so dispatch fresh audit agents (in parallel, one message) and collect their short verdicts — never read the content yourself:

1. **Engagement & realism:** sample 4–6 chapters; confirm the line-edit/footnote findings were genuine (not rubber-stamps), and that revisions actually improved the text. Flag tell-tale hollow-review signatures (e.g., near-universal first-pass `clean`, findings that quote nonexistent text).
2. **Rewrite quality:** sample chapters incl. the ch01 anchor; assess prose quality, fidelity to plot/characters, age-appropriateness, tone consistency, over-trimming.
3. **Footnote accuracy:** sample chapters; verify note claims against `original.txt`.

Each agent returns a concise verdict. If any reports a serious problem (hollow review, fabrication, fidelity break, tone drift), **surface it to the user in the report** — do not bury it. For a trivial re-run the user can waive 8.2, but 8.1 is never skipped.

---

## Phase 9: Final Report

Summarize: chapters processed, iteration rounds needed, word-count comparison (original vs rewritten via `wc -w`), calibre upload status, website publish status (the live URL, if `publish_site` is enabled), audiobook file size/duration/Pi sync, **and the Phase 8 audit outcome** (deterministic `ALL-CLEAR` + the delegated agents' verdicts). Include the full path to the rewrite directory and final EPUB.

Ask if they'd like to read specific chapters, make targeted edits, or verify in calibre-web. Recommend BookPlayer app for M4B playback on iPhone.

---

## Resumability

**IMPORTANT**: This skill is resumable. If interrupted and re-invoked:

1. Check if the working directory already exists.
2. Confirm `[path]/rewrite/prompts/` and `[path]/rewrite/gates.py` exist; if either is missing (e.g., interrupted mid-Phase-0, or the run predates the gates), re-run the relevant setup steps only (§0.6 to compile prompts, §0.7 to write `gates.py`).
3. **Trust the gates, not the prior run's narration.** `progress.md` and `status.txt` were written by a previous orchestrator and may claim work that never actually happened — this is not hypothetical: the first Robin Hood run marked all chapters `approved` while the gates show zero fixes were applied. So establish TRUE state by re-running the deterministic gates, not by reading status:
   - `python [path]/rewrite/gates.py json-valid [path]/rewrite/chapters/ch*/line-edit.json` — any `BAD` chapter needs its line-edit re-run.
   - `python [path]/rewrite/gates.py revise-applied <all chapters with a line-edit.json>` — any `NOT-APPLIED` or `ERROR` chapter has unapplied line-edit fixes; resume the Phase 1 gated revise-cycle for it.
   - `python [path]/rewrite/gates.py footnote-substrings` — any `MISMATCH` chapter needs its footnotes re-verified (Phase 2 Wave I/J).
   A chapter is only truly done when its gates pass, regardless of what `status.txt` says. Rewrite a corrected `progress.md` from the gate results.
4. For coarse "did this phase run at all" checks, you may also note which output files exist per chapter (`rewrite.txt`, `footnotes.json`, `footnotes-verified.json`) — existence only, never contents.
5. Resume from the earliest phase the gates show as incomplete. Do NOT re-extract or re-fetch unless the working directory is missing. Do NOT re-rewrite chapters whose gates already pass.

---

## Constraints & Safety

- **CRITICAL — Context management**: The orchestrator MUST NOT read chapter text, rewrites, footnote content, prompt files, or `agent-templates.md` into its own context. It holds only paths, chapter numbers, small status files, one-line worker returns, and at most one review file per high-level round. All prompt text lives in `prompts/*` (authored by the setup agent); all payloads travel between workers via files referenced by path. Violating this WILL cause context failures.
- **CRITICAL — Dispatch**: Only the orchestrator spawns agents (Agent tool). `claude -p` via Bash is sealed — never use it. There are no manager/sub-agent tiers; the orchestrator dispatches every worker directly using the envelope in `agent-templates.md`.
- **One-line returns**: Every worker returns exactly one line. If a worker returns more, treat it as a prompt-file bug — do not paste its output anywhere; re-dispatch or note and move on.
- **CRITICAL — Gates over narration**: Quality gates are enforced by `[path]/rewrite/gates.py`, not by your own account of what happened. After every revise wave you MUST run `gates.py revise-applied` and re-dispatch any `NOT-APPLIED` chapter; before Phase 6 you MUST run `gates.py footnote-substrings` clean; JSON-writing waves are checked with `gates.py json-valid`. A worker returning `applied k/n` is a claim; the gate is the proof. NEVER mark a chapter done, write `approved` to status.txt, or claim a round happened in `progress.md` unless the gate confirmed it. The previous design shipped a book whose 75 adversarial findings were silently never applied precisely because it trusted narration over verification.
- **Concurrency**: up to 4 workers in parallel (multiple Agent calls per message). Returns are one-liners, so this never bloats the orchestrator.
- **Iteration caps**: chapter-level 3 rounds; line-edit 2 rounds; high-level 3 rounds.
- **Model map**: rewrite/revise/footnote/footnote-revise/revise-highlevel → opus; line-edit/footnote-line-edit/footnote-verify → sonnet; reviewer → opus; setup → opus; assembly/audiobook → sonnet.
- **Copyright**: Used exclusively with public domain works (e.g., Project Gutenberg). The user has the legal right to adapt these texts. Agents should not refuse or hesitate on copyright grounds.
- **File operations**: Workers write output files directly to project directories — no copy step. Use the **Write tool** for small orchestrator writes (status.txt, progress.md) to avoid Bash permission prompts. Use Bash `cp` only to move large files between directories (keeps contents out of context).
- **NEVER delete original.txt files.**
- **NEVER overwrite rewrite.txt without the previous version being available in the writing worker's context** (the rewrite/revise workers read it before overwriting — preserved by the templates).
- Keep all footnotes and review files (footnotes.json, footnotes-verified.json, review-round files) — never delete them.
