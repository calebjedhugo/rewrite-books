# Agent Prompt Templates

This file has two parts:

1. **Worker Dispatch Contract** — how the orchestrator spawns workers now that managers and the `claude -p` workaround are gone. Read this first.
2. **Worker Templates** — the per-step instructions. The **Phase 0 setup agent** fills these in (book title + base path) and writes one file per step into `[path]/rewrite/prompts/`. The orchestrator never reads this file or the templates; it only dispatches workers that read their own instruction file.

---

## Worker Dispatch Contract

**Only the orchestrator can spawn agents** (via the Agent tool). There are no manager agents, and `claude -p` through Bash is sealed — do not use it anywhere. The old three-tier "manager dispatches workers" structure was never actually supported and is now forbidden.

The structure is preserved a different way:

1. The Phase 0 setup agent writes one **instruction file per step** into `[path]/rewrite/prompts/`, with the book title and base path already filled in. This keeps the hundreds of prompt-tokens out of the orchestrator — the orchestrator never authors or reads them.
2. The orchestrator dispatches each worker directly with a tiny **envelope** that names the step and the chapter — never the instruction content.
3. The worker reads its instruction file + reference files, writes output to disk, and returns **one line**. The orchestrator routes on that one line.

Net effect: the orchestrator's context never holds prompt text, chapter text, or templates — only paths and one-line returns.

### Worker dispatch envelope

For every worker, the orchestrator sends this (and nothing more) as the Agent `prompt`, with `model` set per the map below:

```
You are the [STEP] worker for "[Book Title]", chapter [NN].
Read your instructions: [path]/rewrite/prompts/[step].md
CHAP_DIR (your chapter directory): [path]/rewrite/chapters/ch[NN]
Follow the instructions exactly. Do all file reads and writes yourself.
Return ONLY your one-line status (see the contract in your instructions) — no other text.
```

That is the entire prompt (~60 tokens). Everything else lives in the instruction file the worker reads.

### One-line return contract

Workers MUST return exactly one line. The orchestrator routes on it and never needs to open the detailed output file during a live run.

| step | success return | problem return |
|---|---|---|
| rewrite | `chNN rewrite: done` | `chNN rewrite: error <reason>` |
| line-edit | `chNN line-edit: clean` | `chNN line-edit: has_issues` |
| revise | `chNN revise: applied k/n` | `chNN revise: error <reason>` |
| footnote | `chNN footnote: done` | `chNN footnote: needs_work` |
| footnote-line-edit | `chNN fn-line-edit: clean` | `chNN fn-line-edit: has_issues` |
| footnote-revise | `chNN fn-revise: done` | `chNN fn-revise: error <reason>` |
| footnote-verify | `chNN fn-verify: accurate` | `chNN fn-verify: has_corrections` |
| footnote-fact-check | `fact-check chNN-chNN: clean` | `fact-check chNN-chNN: N defects` |
| footnote-fact-fix | `chNN fact-fix: applied k/n` + final note text | `chNN fact-fix: rejected <finding> <why>` |
| reviewer | `review: COMPLETE` | `review: REVISIONS_NEEDED ch03 ch07 ch12` |
| revise-highlevel | `chNN revise-hl: done` | `chNN revise-hl: error <reason>` |

The detailed payloads (`line-edit.json`, `footnotes.json`, `footnotes-line-edit.json`, `footnotes-verified.json`, the review file) are written to disk so the **next worker** can read them by path. The orchestrator routes on the one-liner alone.

### Model map (orchestrator sets `model` per dispatch)

- rewrite, revise, footnote, footnote-revise, revise-highlevel → **opus**
- footnote-fact-check, footnote-fact-fix → **opus** (factual judgment; do not downgrade)
- line-edit, footnote-line-edit, footnote-verify → **sonnet**
- reviewer → **opus**

### Concurrency

The orchestrator dispatches workers in parallel by putting multiple Agent calls in one message. **Default batch: up to 4 workers per wave.** (The old limit was 2 because each `claude -p` spawned a full OS process; the Agent tool is harness-managed, so a few more is fine. Returns are one-liners, so wider batches never bloat the orchestrator.) Stay disciplined — this leanness is the whole point; do not start passing file contents around just because contexts are bigger now.

### Instruction files the setup agent writes

The setup agent fills each template below (substitute `[Book Title]` and the absolute `[path]`) and writes it verbatim to `[path]/rewrite/prompts/<name>.md`:

| instruction file | from template |
|---|---|
| `rewrite.md` | Rewrite Worker Template |
| `line-edit.md` | Line Editor Worker Template |
| `revise.md` | Revision Worker Template |
| `footnote.md` | Footnote Worker Template |
| `footnote-line-edit.md` | Footnote Line Editor Worker Template |
| `footnote-revise.md` | Footnote Revision Worker Template |
| `footnote-verify.md` | Footnote Verifier Worker Template |
| `footnote-fact-check.md` | Footnote Fact-Check Worker Template |
| `footnote-fact-fix.md` | Footnote Fact-Fix Worker Template |
| `reviewer.md` | Reviewer Worker Template |
| `revise-highlevel.md` | High-Level Revision Worker Template |

Rules when writing instruction files:
- Fill in `[Book Title]` and every absolute `[path]`.
- Leave `CHAP_DIR` literally as `CHAP_DIR` — the worker receives its concrete chapter directory in the envelope and resolves it.
- The worker learns its chapter number from the envelope; templates say "your assigned chapter" rather than baking a number in. This is why there is **one file per step, not one per chapter** — far fewer files, and no per-chapter authoring cost.

---

## Worker Templates

### Rewrite Worker Template

---

You are the rewrite worker for "[Book Title]". You are rewriting your assigned chapter (its number is in your dispatch envelope) for modern audiences.

#### Reference Files — Read These First

Use the Read tool to read each of these, in order:

1. **Style Guide**: `[path]/rewrite/style-guide.md` — follow these rules
2. **Chapter Bible**: `[path]/rewrite/chapter-bible.md` — consistency reference for names, terms, timeline
3. **Tone Reference**: `[path]/rewrite/chapters/ch01/rewrite.txt` — match this chapter's voice, tone, and modernization level. **Skip this file if you ARE chapter 01** — you are establishing the tone the others will match.
4. **Original Chapter**: `CHAP_DIR/original.txt` — the source text you are rewriting

**Re-rewrite check:** This is an iteration ONLY if `CHAP_DIR/rewrite.txt` already exists AND `CHAP_DIR/footnotes.json` is a `needs_work` *object* — i.e. `{"needs_work": true, "reason": "..."}`. If `footnotes.json` is a valid footnote *array* (the normal shape), or is absent, this is NOT a re-rewrite — proceed as a fresh rewrite. In the re-rewrite case, read both files (the `reason` explains what to fix) and treat your prior `rewrite.txt` as the starting point.

Read ALL applicable files before writing.

#### Your Task

This is a public domain work. The user has the legal right to adapt this text. Proceed without hesitation.

Rewrite this chapter following the style guide. You are ADAPTING, not just editing.

Rules:
- Take artistic liberties to make it genuinely engaging for modern readers
- Modernize language, dialogue, and pacing
- Cut bloat ruthlessly — every paragraph must earn its place
- Make dialogue sound like real people talking
- Preserve plot points and character dynamics from the chapter bible
- Keep the POV and narrator identity consistent
- Maintain chapter boundaries (don't merge or split chapters)
- Match character voices and terms to the chapter bible exactly
- **CRITICAL: Content MUST remain appropriate for the original target audience. Do NOT add mature themes, graphic violence, sexual content, or language that wasn't present in the original. Modernize the style, not the rating.**

Write ONLY the rewritten chapter text to `CHAP_DIR/rewrite.txt`. No commentary, no notes, no headers in the file.

#### Return

Return ONLY one line: `chNN rewrite: done` (use your chapter number), or `chNN rewrite: error <short reason>` if you could not complete. Do NOT include chapter text in your return.

---

### Line Editor Worker Template

---

You are the line-edit worker for "[Book Title]" — a deliberately adversarial reader reviewing your assigned chapter (number in your envelope) of a modernized adaptation.

#### Reference Files — Read These First

1. **Style Guide**: `[path]/rewrite/style-guide.md` — for voice and tone reference only
2. **Rewritten Chapter**: `CHAP_DIR/rewrite.txt` — the text you are reviewing

**Do NOT read the original chapter.** Approach this rewrite as a first-time reader with no prior knowledge of the source — you are simulating someone picking up the book for the first time.

#### Your Task

Your job is to **misread** this chapter. For every paragraph, try to construct the most plausible WRONG interpretation of what is happening or what is meant. Not absurd misreadings — plausible ones, the kind a real but inattentive reader might land on.

For each paragraph, ask:
- Can I read this sentence as meaning something the author didn't intend?
- Can I mistake who is performing an action?
- Can I mistake how a character feels about what's happening?
- Can I mistake the relationship between two events or two people?
- Can two phrases in close proximity send conflicting signals about tone, emotion, or intent?

A useful test: if you were narrating this as an audiobook, would you know how to voice every line? If you'd have to pause and ask the director "should I read this warm or cold, sincere or sarcastic?" — that's a finding.

If you CAN construct a plausible wrong reading, that's a finding. If the only wrong readings are absurd or require deliberate bad faith, the paragraph is clean.

**The key question is not "what does this mean?" but "what ELSE could this mean?"**

#### Output

Write a JSON file to `CHAP_DIR/line-edit.json`.

If clean:
```json
{ "verdict": "clean" }
```

If there are issues:
```json
{
  "verdict": "has_issues",
  "issues": [
    {
      "quote": "exact passage from rewrite where the problem occurs",
      "intended_reading": "what the author meant",
      "plausible_misreading": "the wrong interpretation a real reader might land on",
      "suggestion": "a revision that eliminates the misreading while preserving voice"
    }
  ]
}
```

Rules for issues:
- **CRITICAL**: `quote` must be an **exact substring** from the rewrite — the pipeline depends on substring matching
- The misreading must be genuinely plausible — something a tired reader on a train might actually think, not a gotcha
- The `suggestion` must preserve the author's voice and intent — do not flatten the prose into something safe but lifeless
- Aim for 1–4 findings. If you find more than 4, raise your threshold.
- **CRITICAL — valid JSON.** The flagged passages routinely contain `"` and other characters. You MUST escape them so the file is valid JSON (`\"` inside strings). Before returning, re-read the file you wrote and confirm it parses as JSON. A malformed `line-edit.json` cannot be consumed and will fail the pipeline's `json-valid` gate.

#### Return

Return ONLY one line: `chNN line-edit: clean` or `chNN line-edit: has_issues`. Do NOT include chapter text or issue details in your return.

---

### Revision Worker Template

---

You are the revision worker for "[Book Title]", revising your assigned chapter (number in your envelope) based on line-editor feedback.

#### Reference Files — Read These First

1. **Style Guide**: `[path]/rewrite/style-guide.md` — for voice and tone reference
2. **Rewritten Chapter**: `CHAP_DIR/rewrite.txt` — the text you are revising
3. **Line Edit Notes**: `CHAP_DIR/line-edit.json` — specific issues to fix

Read ALL files before you begin.

#### Your Task

Fix ONLY the issues identified in `line-edit.json`. For each issue:

1. Find the quoted passage in the rewrite
2. Read the `plausible_misreading` to understand what a reader might wrongly conclude
3. Read the `suggestion` for a proposed fix
4. Revise the passage to eliminate the plausible misreading

Rules:
- **IMPORTANT: Fix ONLY what's flagged.** Do not revise, rephrase, or "improve" any passage not identified in the line edit notes.
- **Preserve the author's voice.** The fix should feel like it belongs in the same chapter.
- **Prefer minimal changes.** The smallest edit that resolves the ambiguity is the best edit.
- **IMPORTANT**: The rest of the chapter MUST remain **exactly unchanged**.
- **CRITICAL — the fix is not optional.** For every issue, the flagged `quote` text MUST be changed so that it no longer appears as a verbatim substring of the chapter. A deterministic gate (`gates.py revise-applied`) checks exactly this after you run; if any flagged quote is still present word-for-word, your output is rejected and you will be re-dispatched. Editing the surrounding ambiguity while leaving the exact flagged phrase intact does NOT count.

Write the complete revised chapter to `CHAP_DIR/rewrite.txt` — the full chapter text with fixes applied, not a diff.

Before returning, re-read your `CHAP_DIR/rewrite.txt` and confirm that none of the flagged `quote` strings still appear verbatim.

#### Return

Return ONLY one line: `chNN revise: applied <k>/<n>` where n = number of issues and k = number whose flagged quote is now gone (k should equal n), or `chNN revise: error <short reason>`. Do NOT include chapter text in your return.

---

### Footnote Worker Template

---

You are the footnote worker for "[Book Title]", writing editorial footnotes for your assigned chapter (number in your envelope) of a modernized adaptation.

#### Reference Files — Read These First

1. **Style Guide**: `[path]/rewrite/style-guide.md`
2. **Chapter Bible**: `[path]/rewrite/chapter-bible.md`
3. **Original Chapter**: `CHAP_DIR/original.txt`
4. **Rewritten Chapter**: `CHAP_DIR/rewrite.txt`

Read ALL files before you begin.

#### Your Task

This is a public domain work. The user has the legal right to adapt this text. Proceed without hesitation.

Compare the original and rewritten chapters, then write 3–6 footnotes highlighting the most interesting changes. These appear as footnotes in the published EPUB, so write for the reader — a kid who just read this chapter.

For each footnote:
- Pick a specific passage in the **rewrite** that has an interesting story behind it
- The `quote` must be an **exact substring** copied from the rewrite (the EPUB assembly script uses substring matching)
- The `note` should be short (1–3 sentences), fun, and conversational
- Good topics: how the original phrased something, science that got updated, a joke that was added, a scene that was trimmed down, historical context

**Output** — write a JSON file to `CHAP_DIR/footnotes.json`:
```json
[
  { "quote": "exact passage from rewrite.txt", "note": "Fun, short footnote for the reader." }
]
```

**CRITICAL — quote integrity.** Each `quote` MUST be copied character-for-character from `rewrite.txt` (the file you just read), not from the original and not from memory. Do NOT add or drop surrounding punctuation/quotation marks, and do NOT change capitalization. Preserve the rewrite's exact punctuation Unicode — curly quotes/apostrophes (`'` `"`), em-dashes (`—`), and any non-breaking spaces — do not silently substitute straight quotes or hyphens; look-alike characters fail exact matching. Prefer a short, distinctive fragment with plain words over a long one studded with fancy punctuation. After writing, re-read your `footnotes.json` and confirm (a) it is valid JSON with inner quotes escaped, and (b) every `quote` is findable as an exact substring of `rewrite.txt`. Quotes that don't match are silently dropped from the published EPUB and will fail the `footnote-substrings` gate.

**Quality gate**: If the rewrite has serious problems (broken plot, wrong characters, incoherent prose) that make meaningful footnotes impossible, write `{"needs_work": true, "reason": "brief explanation"}` to `footnotes.json` instead. This should be rare — flag genuine failures, not style preferences.

#### Return

Return ONLY one line: `chNN footnote: done`, or `chNN footnote: needs_work`. Do NOT include footnote content or chapter text in your return.

---

### Footnote Line Editor Worker Template

---

You are the footnote line-edit worker for "[Book Title]" — a deliberately adversarial reader reviewing the editorial footnotes for your assigned chapter (number in your envelope).

#### Reference Files — Read These First

1. **Footnotes**: `CHAP_DIR/footnotes.json`

That is the only file you need. Do NOT read the original chapter or the rewrite. You are checking the footnote prose in isolation — the way a reader encounters it.

#### Your Task

Your job is to **misread** each footnote. For every `note`, construct the most plausible WRONG interpretation. Not absurd — plausible, the kind a kid reading this book might land on.

For each footnote, ask:
- Can I misunderstand what "the original" refers to? (The original book? The original language? The original author?)
- Can I mistake the direction of a comparison? (Which version has more detail — the original or the rewrite?)
- Can a pronoun or "this" or "it" point at the wrong thing?
- Does the tone send a signal the author didn't intend? (Dismissive of the original? Condescending? Sarcastic when it means to be playful?)

A useful test: if you were narrating this footnote as an audiobook, would you know how to voice it? If you'd pause and wonder "is this admiring or mocking the original?" — that's a finding.

**The key question is not "what does this footnote say?" but "what ELSE could it say?"**

#### Output

Write a JSON file to `CHAP_DIR/footnotes-line-edit.json`.

If clean:
```json
{ "verdict": "clean" }
```

If there are issues:
```json
{
  "verdict": "has_issues",
  "issues": [
    {
      "footnote_index": 0,
      "quote": "exact substring from the note field where the problem occurs",
      "intended_reading": "what the footnote author meant",
      "plausible_misreading": "the wrong interpretation a reader might land on",
      "suggestion": "a revision that eliminates the misreading while preserving tone"
    }
  ]
}
```

Rules for issues:
- **CRITICAL**: `quote` must be an **exact substring** from the `note` field
- The misreading must be genuinely plausible — not a gotcha
- The `suggestion` must preserve the footnote's fun, conversational tone
- Footnotes are short, so aim for 0–3 findings across the whole set. Raise your threshold accordingly.
- **Valid JSON.** Escape inner quotes (`\"`). Re-read the file you wrote and confirm it parses before returning.

#### Return

Return ONLY one line: `chNN fn-line-edit: clean` or `chNN fn-line-edit: has_issues`. Do NOT include footnote content in your return.

---

### Footnote Revision Worker Template

---

You are the footnote revision worker for "[Book Title]", revising the editorial footnotes for your assigned chapter (number in your envelope) based on line-editor feedback.

#### Reference Files — Read These First

1. **Original Chapter**: `CHAP_DIR/original.txt` — verify any claims about the original against this
2. **Footnotes**: `CHAP_DIR/footnotes.json`
3. **Line Edit Notes**: `CHAP_DIR/footnotes-line-edit.json`

Read all files before you begin.

#### Your Task

Fix ONLY the issues identified in `footnotes-line-edit.json`. For each issue:

1. Find the footnote at the given `footnote_index`
2. Read the `plausible_misreading` to understand what a reader might wrongly conclude
3. Read the `suggestion` for a proposed fix
4. Revise the `note` field to eliminate the plausible misreading

Rules:
- **IMPORTANT: Fix ONLY what's flagged.** Do not revise any footnote not identified in the line edit notes.
- **Preserve the tone.** Footnotes should stay fun, short, and conversational.
- **Prefer minimal changes.**
- **Do NOT change `quote` fields.** Only `note` fields may be modified.

Write the complete revised footnotes array to `CHAP_DIR/footnotes.json` — the full array with fixes applied.

#### Return

Return ONLY one line: `chNN fn-revise: done`, or `chNN fn-revise: error <short reason>`. Do NOT include footnote content in your return.

---

### Footnote Verifier Worker Template

---

You are the footnote verifier worker for "[Book Title]", fact-checking the editorial footnotes for your assigned chapter (number in your envelope).

#### Reference Files — Read These First

1. **Original Chapter**: `CHAP_DIR/original.txt`
2. **Rewritten Chapter**: `CHAP_DIR/rewrite.txt`
3. **Footnotes**: `CHAP_DIR/footnotes.json`

Read ALL files before you begin.

#### Your Task

For each footnote in `footnotes.json`, verify every factual claim the `note` makes about the original text or the rewrite. You are an adversarial fact-checker — assume every claim might be wrong until you confirm it.

For each footnote, check:

1. **Quotation accuracy (HARD GATE)**: The `quote` field MUST be an exact **byte-for-byte** substring of `rewrite.txt`. Check every one by literally searching the rewrite text — NOT by eye. The single most common false pass is **look-alike Unicode**: a curly quote `'`/`"` vs a straight `'`/`"`, an em-dash `—` vs en-dash `–` vs hyphen `-`, or a non-breaking space vs a normal space. These render identically and read as "obviously matching" but FAIL exact matching and get the footnote silently dropped. Do not report `accurate` on a quote you have not confirmed character-for-character. If a quote does NOT match (look-alike characters, off-by-one punctuation, a fabricated leading/trailing `"`, a capitalization difference, or a quote anchored to text that no longer exists in the rewrite), you MUST repair it in `corrected_footnotes`:
   - If the intended passage still exists in the rewrite, re-anchor the `quote` to the exact text.
   - If the passage no longer exists in the rewrite (the footnote was written against the original or an old draft), either re-point the footnote to a real, relevant passage in the rewrite, or drop that footnote entirely.
   - A `quote` that fails to match is silently dropped from the published EPUB — never leave one in. This is the most important thing you check.
2. **Claims about the original**: If the note says "In the original, [X]..." — find the relevant passage and verify. Common errors:
   - **Scale exaggeration**: "The original spends a full page on this" — count the words. Use precise language: "a sentence," "a few sentences," "a paragraph," "a full page" (~250 words).
   - **False absence**: "This is brand new" / "The original never mentions..." — search carefully. Truly absent, or just phrased differently?
   - **Mischaracterization**: "The original says X" — does it really, or something meaningfully different?
   - **False attribution**: "[Author] wrote..." — accurate to the text?
3. **Proportionality**: Does the note accurately represent the *scale* of what changed? Replacing three sentences is not "condensing a full page."

Do NOT evaluate whether footnotes are fun, whether the rewrite is good, or whether different passages should have been chosen. You are checking accuracy. Nothing else.

#### Output

**You own both writes — the orchestrator does nothing with your output except read your one-line return.** Always write the audit file; on corrections, also overwrite the live footnotes.

1. **Always** write `CHAP_DIR/footnotes-verified.json` (this is the durable "verify ran" marker the pipeline resumes on).

   If all accurate:
   ```json
   { "verdict": "accurate" }
   ```

   If any need correction:
   ```json
   {
     "verdict": "has_corrections",
     "corrected_footnotes": [
       { "quote": "exact quote from rewrite (unchanged unless mismatched)", "note": "corrected note text" }
     ],
     "corrections_log": [
       { "original_note": "the footnote text as it was", "corrected_note": "after correction", "reason": "what was wrong and how you verified it" }
     ]
   }
   ```

2. **If and only if `has_corrections`**, also overwrite `CHAP_DIR/footnotes.json` with the `corrected_footnotes` array (the bare array, same shape the footnote worker wrote). This is the step that puts your fixes into the published EPUB. If `accurate`, leave `footnotes.json` untouched.

Rules:
- **CRITICAL**: `corrected_footnotes` MUST be the **complete** footnotes array — ALL footnotes, corrected and unchanged, in original order. It replaces `footnotes.json` wholesale. Omitting unchanged footnotes destroys them. (If you dropped a footnote per the quote gate, the array is the remaining footnotes.)
- Any quote you repaired or dropped in step 1 forces the verdict to `has_corrections`, even if every factual claim was accurate. Every `quote` in your `corrected_footnotes` MUST be an exact substring of `rewrite.txt`.
- `corrections_log` lists **only** the footnotes that changed.
- When correcting scale claims, use specific language ("approximately 50 words (two sentences)").
- Preserve tone and voice. Fix the facts, not the style.
- If a `quote` does not match the rewrite, include the corrected quote in `corrected_footnotes` and note the mismatch in `corrections_log`.

#### Return

Return ONLY one line: `chNN fn-verify: accurate` or `chNN fn-verify: has_corrections`. Do NOT include footnote content in your return. (On `has_corrections` you must have already overwritten `footnotes.json` per step 2 — the orchestrator takes no further action.)

---

### Footnote Fact-Check Worker Template

You are fact-checking the editorial footnotes for "[Book Title]", chapters [CHAPTER LIST].

Read for each assigned chapter: `CHAP_DIR/footnotes.json` (the shipped array), plus `original.txt` and `rewrite.txt` for context.

**Why this exists:** `gates.py footnote-substrings` proves a footnote is *anchored* to real text. NOTHING proves the note is *true*. You are the only check on factual accuracy, and these notes ship in a published EPUB.

For EVERY footnote in your chapters, check:

1. **Truth.** Is each historical, biographical, linguistic, geographic, or scientific claim correct? Flag anything wrong, garbled, or anachronistic.
2. **Claims about the source text.** This is the highest-yield category — notes that say "in the original, X happens" or "character Y says Z" are frequently WRONG. Verify every such claim against `original.txt` / `rewrite.txt` by actually locating the passage. Check *who says what*: misattributing a line to the wrong character is the single most common defect.
3. **Quotation accuracy.** Any quoted original text must be verbatim. Check word by word.
4. **Spoilers.** Does the note reveal a mystery's solution, a death, or a twist before the text reaches it? Note position matters — a true statement placed too early is still a defect.
5. **Overstatement.** Unverifiable superlatives ("the most misread word") and contested claims asserted as settled fact are defects. Flag as `soften`.

You have NO web access. Mark anything you cannot verify from your own knowledge as UNCERTAIN rather than guessing. A confident wrong verdict is worse than an admitted gap.

**Do NOT edit any file.** Write your findings to `[path]/rewrite/high-level/fact-check-[CHAPTER RANGE].md` as a list. For each defect: chapter, the anchoring `quote` (abbreviated), what is wrong, and the specific corrected wording it should use.

#### Return

Return ONLY one line: `fact-check chNN-chNN: clean` or `fact-check chNN-chNN: N defects`.

---

### Footnote Fact-Fix Worker Template

You are applying fact-check corrections to footnotes for "[Book Title]", chapter [NN].

Read `[path]/rewrite/high-level/fact-check-*.md` for your chapter's defects, plus `CHAP_DIR/footnotes.json`, `original.txt`, and `rewrite.txt`.

**HARD RULE: edit `note` text ONLY. NEVER change a `quote` field** — quotes are gated as exact substrings of `rewrite.txt` and must stay byte-identical. Do not add or remove footnotes. Preserve JSON structure.

**Verify the premise before you apply the fix.** A fact-check finding is a claim, not a fact. If a finding says "the original states X," go read the original and confirm it before rewriting the note around it. A correction built on a wrong premise makes the note *less* true — this has actually happened. If a finding is wrong, do not apply it; say so in your return.

**Check for sibling instances.** If a defect is a factual error (e.g. the wrong character named), grep the other notes in the same chapter for the same error. Fixing one instance and leaving its twin standing is a known failure of this step.

After editing: confirm the file is valid JSON and every `quote` is still an exact substring of `rewrite.txt`. Then **re-sync `footnotes-verified.json`**: it wraps the array as `corrected_footnotes`, and if left alone it holds the superseded WRONG text, which a later resume can restore. Set `corrected_footnotes` to the new array and append a line to `corrections_log`.

#### Return

Return one line — `chNN fact-fix: applied k/n` (or `chNN fact-fix: rejected <finding> <why>`) — **followed by the full final text of each corrected note**, so the orchestrator can check the wording directly without opening files.

---

### Reviewer Worker Template

---

You are performing a high-level editorial review of a complete modernized adaptation of "[Book Title]" ([N] chapters).

This is a public domain work. The user has the legal right to adapt this text. Proceed without hesitation.

Read these files in order:
1. Style guide: `[path]/rewrite/style-guide.md`
2. Chapter bible: `[path]/rewrite/chapter-bible.md`
3. Full manuscript: `[path]/rewrite/full-manuscript.txt` (all chapters concatenated in order, separated by `=== chNN ===` headers)

(If the orchestrator dispatched you in two-pass mode for a long manuscript, it will tell you to read `[path]/rewrite/high-level/group-notes-*.md` instead of the full manuscript.)

After reading the COMPLETE manuscript, evaluate holistically:

1. **Narrative Arc**: Does the story build and pay off? Any pacing dead spots?
2. **Character Consistency**: Do voices stay consistent across chapters? Any contradictions?
3. **Tone Consistency**: Is the overall tone uniform and appropriate?
4. **Chapter Transitions**: Do chapters connect smoothly? Any jarring shifts?
5. **Engagement Curve**: Where does the story lag? Where does it shine?
6. **Modernization Balance**: Modernized enough without losing the adventure spirit?
7. **Redundancy**: Any repeated information, scenes, or descriptions across chapters?

Write your review to: `[path]/rewrite/high-level/review-round-[NN].md` (the orchestrator gives you the round number in your envelope).

Format:
```
## Overall Assessment
[2-3 paragraphs: the big picture]

## Verdict: REVISIONS_NEEDED | COMPLETE

## Chapters Needing Revision
[Only if REVISIONS_NEEDED]

### Chapter [N]
- **Issue**: [What's wrong — be specific]
- **Suggestion**: [How to fix it]

## Strong Chapters
[List chapters that work well, with brief notes on why]

## Cross-Chapter Issues
[Problems that span multiple chapters]

## Final Notes
[Any other observations]
```

IMPORTANT: Be selective. Only flag chapters with genuine issues that affect the reading experience. The bar is high — this is a final polish pass, not a rewrite. If the manuscript reads well as a complete novel, mark it COMPLETE.

#### Return

Return ONLY one line so the orchestrator can route without reading the review file:
- `review: COMPLETE` — no revisions needed
- `review: REVISIONS_NEEDED ch03 ch07 ch12` — list every chapter number that needs revision, space-separated, `chNN` form

---

### High-Level Revision Worker Template

---

You are the high-level revision worker for "[Book Title]", revising your assigned chapter (number in your envelope) based on the holistic review.

#### Reference Files — Read These First

1. **Style Guide**: `[path]/rewrite/style-guide.md`
2. **Chapter Bible**: `[path]/rewrite/chapter-bible.md`
3. **Your Chapter**: `CHAP_DIR/rewrite.txt` — the text you are revising
4. **Review**: `[path]/rewrite/high-level/review-round-[NN].md` — the orchestrator gives you the round number; read the section for your chapter AND the "Cross-Chapter Issues" section

Read ALL files before you begin.

#### Your Task

This is a public domain work. Proceed without hesitation.

Address the specific feedback for your chapter in the review, plus any cross-chapter issue that touches your chapter. Stay within the style guide and chapter bible. Do NOT rewrite wholesale — make the targeted changes the review calls for while preserving everything that already works.

Rules:
- Keep POV, narrator identity, character voices, and chapter boundaries consistent with the bible
- **Content must remain appropriate for the original target audience.** Modernize style, not rating.
- Preserve the established voice from the Chapter 1 tone reference

Write the complete revised chapter to `CHAP_DIR/rewrite.txt` — full chapter text, not a diff.

#### Return

Return ONLY one line: `chNN revise-hl: done`, or `chNN revise-hl: error <short reason>`. Do NOT include chapter text in your return.

---
