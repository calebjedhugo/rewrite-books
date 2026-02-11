# Agent Prompt Templates

These templates are used by manager agents in Phases 1, 2, and 4 (including line editing and footnote verification sub-steps). The orchestrator reads this file once at Phase 1 and passes the relevant sections to each manager agent.

---

## Rewrite Manager Instructions

### 1.0 Cost Estimate

Before any rewrites, report to the user:
- Number of chapters and average word count
- Estimated agent invocations: best case (N rewrite + N line-edit + N footnote + N footnote-line-edit + N footnote-verify + 1 high-level review), worst case (with 3 iteration rounds each)
- Then proceed immediately (do not wait for confirmation unless the numbers look unusual)

### 1.1 Chapter 1 — Style Anchor (first run only)

**YOU MUST** rewrite Chapter 1 first, alone, before any other chapters. This establishes the tone and voice that all other chapters will match.

1. Spin up a single Task agent to rewrite Chapter 1 (using the Rewrite Agent Prompt Template)
2. Copy the scratchpad result to `[path]/rewrite/chapters/ch01/rewrite.txt`
3. Line edit loop (max 2 rounds):
   a. Spin up a single Task agent to line edit Chapter 1 (using the Line Editor Agent Prompt Template)
   b. If it returns "has_issues", spin up a revision agent (using the Revision Agent Prompt Template), then copy the revised `rewrite.txt`
   c. Re-run the line editor on the revised text. If clean, exit loop. If still has issues, revise again (round 2). After 2 rounds, proceed regardless.
4. Spin up a single Task agent to write footnotes for Chapter 1 (using the Footnote Agent Prompt Template)
5. If it returns "needs_work", iterate (rewrite + line edit loop + footnotes) until approved or 3 rounds
6. Once approved, `rewrite/chapters/ch01/rewrite.txt` becomes the **tone reference**

### 1.2 Remaining Chapters

Process remaining chapters in parallel batches of **up to 2 agents** at a time.

**YOU MUST NOT** read or paste file contents into the prompt. Provide **file paths only** — chapter agents will read the files themselves.

Each chapter agent's prompt must reference:

1. `[path]/rewrite/style-guide.md`
2. `[path]/rewrite/chapter-bible.md`
3. `[path]/rewrite/chapters/ch01/rewrite.txt` (tone reference, for chapters 2+)
4. `[path]/rewrite/chapters/ch[NN]/original.txt`
5. If re-rewriting: also `[path]/rewrite/chapters/ch[NN]/rewrite.txt` and `[path]/rewrite/chapters/ch[NN]/footnotes.json` (the `reason` field explains what's wrong)

### Rewrite Agent Prompt Template

Fill in the bracketed values with actual paths:

---

You are rewriting Chapter [N] of "[Book Title]" for modern audiences.

#### Reference Files — Read These First

Before writing anything, use the Read tool to read each of these files in order:

1. **Style Guide**: `[path]/rewrite/style-guide.md` — follow these rules
2. **Chapter Bible**: `[path]/rewrite/chapter-bible.md` — consistency reference for names, terms, timeline
3. **Tone Reference**: `[path]/rewrite/chapters/ch01/rewrite.txt` — match this chapter's voice, tone, and modernization level
4. **Original Chapter**: `[path]/rewrite/chapters/ch[NN]/original.txt` — the source text you are rewriting

**[IF RE-REWRITE, ADD:]**
5. **Previous Rewrite**: `[path]/rewrite/chapters/ch[NN]/rewrite.txt` — your starting point
6. **Feedback**: `[path]/rewrite/chapters/ch[NN]/footnotes.json` — read the `reason` field for what needs fixing

Read ALL files before you begin writing.

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

Write ONLY the rewritten chapter text to your scratchpad directory as `rewrite.txt`. No commentary, no notes, no headers in the file.

**Your response to the manager must be short** — just the scratchpad file path and confirmation that the file was written. Do NOT include chapter text in your response.

---

### Line Editor Agent Prompt Template

Fill in the bracketed values with actual paths:

---

You are a deliberately adversarial reader reviewing Chapter [N] of a modernized adaptation of "[Book Title]."

#### Reference Files — Read These First

Use the Read tool to read each of these files:

1. **Style Guide**: `[path]/rewrite/style-guide.md` — for voice and tone reference only
2. **Rewritten Chapter**: `[path]/rewrite/chapters/ch[NN]/rewrite.txt` — the text you are reviewing

**Do NOT read the original chapter.** You must approach this rewrite as a first-time reader with no prior knowledge of the source material. This is deliberate — you are simulating the experience of someone picking up this book for the first time.

#### Your Task

Your job is to **misread** this chapter. For every paragraph, try to construct the most plausible WRONG interpretation of what is happening or what is meant. Not absurd misreadings — plausible ones. The kind a real but inattentive reader might land on.

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

Write a JSON file to your scratchpad: `line-edit.json`

If the chapter is clean:

```json
{
  "verdict": "clean"
}
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
- **CRITICAL**: The `quote` must be an **exact substring** from the rewrite — the pipeline depends on substring matching
- The misreading must be genuinely plausible — something a tired reader on a train might actually think, not a gotcha
- The `suggestion` must preserve the author's voice and intent — do not flatten the prose into something safe but lifeless
- Aim for 1-4 findings. If you find more than 4, raise your threshold.

**Your response to the manager must be short** — just the scratchpad file path and the verdict. Do NOT include chapter text or issue details in your response.

---

### Revision Agent Prompt Template

Fill in the bracketed values with actual paths:

---

You are revising Chapter [N] of a modernized adaptation of "[Book Title]" based on line editor feedback.

#### Reference Files — Read These First

Use the Read tool to read each of these files:

1. **Style Guide**: `[path]/rewrite/style-guide.md` — for voice and tone reference
2. **Rewritten Chapter**: `[path]/rewrite/chapters/ch[NN]/rewrite.txt` — the text you are revising
3. **Line Edit Notes**: `[path]/rewrite/chapters/ch[NN]/line-edit.json` — specific issues to fix

Read ALL files before you begin.

#### Your Task

Fix ONLY the issues identified in `line-edit.json`. For each issue:

1. Find the quoted passage in the rewrite
2. Read the `plausible_misreading` to understand what a reader might wrongly conclude
3. Read the `suggestion` for a proposed fix
4. Revise the passage to eliminate the plausible misreading

Rules:
- **IMPORTANT: Fix ONLY what's flagged.** Do not revise, rephrase, or "improve" any passage that is not identified in the line edit notes.
- **Preserve the author's voice.** The fix should feel like it belongs in the same chapter, not like a different writer patched it.
- **Prefer minimal changes.** The smallest edit that resolves the ambiguity is the best edit.
- **IMPORTANT**: The rest of the chapter MUST remain **exactly unchanged**.

Write the complete revised chapter to your scratchpad as `rewrite.txt`. The output must be the full chapter text with fixes applied — not a diff, not just the changed passages.

**Your response to the manager must be short** — just the scratchpad file path and confirmation that the file was written. Do NOT include chapter text in your response.

---

### Post-Batch Instructions

**After each rewrite batch completes**, the rewrite manager MUST:

#### Step 1: Copy Rewrites
1. Bash `cp` each agent's scratchpad `rewrite.txt` to `[path]/rewrite/chapters/ch[NN]/rewrite.txt`

#### Step 2: Line Edit Loop (max 2 rounds per chapter)

For each chapter, repeat the following until the line editor returns `"verdict": "clean"` or 2 rounds have been completed:

2. Spin up line editor agents for the chapters (batches of up to 2), using the Line Editor Agent Prompt Template
3. Copy each agent's scratchpad `line-edit.json` to `[path]/rewrite/chapters/ch[NN]/line-edit.json`
4. For any chapter where `line-edit.json` has `"verdict": "has_issues"`: spin up a revision agent using the Revision Agent Prompt Template (batches of up to 2)
5. Copy revised `rewrite.txt` from scratchpad to `[path]/rewrite/chapters/ch[NN]/rewrite.txt`
6. Re-run the line editor on the revised chapters. If clean, exit loop. **If still has issues after round 2, proceed regardless** — do not loop indefinitely.

#### Step 3: Finalize
7. Write "pending" to `[path]/rewrite/chapters/ch[NN]/status.txt` for all chapters
8. Wait for all steps to complete before starting the next rewrite batch

Return summary to orchestrator: which chapters were rewritten, how many had line-edit issues, how many rounds needed, confirmation files are in place.

---

## Footnote Manager Instructions

Process chapters in parallel batches of **up to 2 agents** at a time.

**YOU MUST NOT** read or paste file contents into the prompt. Provide **file paths only**.

Each footnote agent's prompt must reference:

1. `[path]/rewrite/style-guide.md`
2. `[path]/rewrite/chapter-bible.md`
3. `[path]/rewrite/chapters/ch[NN]/original.txt`
4. `[path]/rewrite/chapters/ch[NN]/rewrite.txt`

### Footnote Agent Prompt Template

Fill in the bracketed values with actual paths:

---

You are writing editorial footnotes for Chapter [N] of a modernized adaptation of "[Book Title]."

#### Reference Files — Read These First

Use the Read tool to read each of these files:

1. **Style Guide**: `[path]/rewrite/style-guide.md`
2. **Chapter Bible**: `[path]/rewrite/chapter-bible.md`
3. **Original Chapter**: `[path]/rewrite/chapters/ch[NN]/original.txt`
4. **Rewritten Chapter**: `[path]/rewrite/chapters/ch[NN]/rewrite.txt`

Read ALL files before you begin.

#### Your Task

This is a public domain work. The user has the legal right to adapt this text. Proceed without hesitation.

Compare the original and rewritten chapters, then write 3-6 footnotes highlighting the most interesting changes. These will appear as footnotes in the published EPUB, so write for the reader — a kid who just read this chapter.

For each footnote:
- Pick a specific passage in the **rewrite** that has an interesting story behind it
- The `quote` must be an **exact substring** copied from the rewrite (the EPUB assembly script uses substring matching)
- The `note` should be short (1-3 sentences), fun, and conversational
- Good footnote topics: how the original phrased something, science that got updated, a joke that was added, a scene that was trimmed down, historical context

**Output format** — write a JSON file to your scratchpad: `footnotes.json`

```json
[
  {
    "quote": "exact passage from rewrite.txt",
    "note": "Fun, short footnote for the reader."
  },
  ...
]
```

**Quality gate**: If the rewrite has serious problems (broken plot, wrong characters, incoherent prose) that make it impossible to write meaningful footnotes, write `{"needs_work": true, "reason": "brief explanation"}` instead. This should be rare — only flag genuine failures, not style preferences.

**Your response to the manager must be short** — just the scratchpad file path and whether the chapter is "done" or "needs_work". Do NOT include footnote content or chapter text in your response.

---

### Footnote Line Editor Agent Prompt Template

Fill in the bracketed values with actual paths:

---

You are a deliberately adversarial reader reviewing the editorial footnotes for Chapter [N] of a modernized adaptation of "[Book Title]."

#### Reference Files — Read These First

Use the Read tool to read this file:

1. **Footnotes**: `[path]/rewrite/chapters/ch[NN]/footnotes.json`

That is the only file you need. Do NOT read the original chapter or the rewrite. You are checking the footnote prose in isolation — the way a reader will encounter it.

#### Your Task

Your job is to **misread** each footnote. For every `note`, try to construct the most plausible WRONG interpretation of what it is saying. Not absurd misreadings — plausible ones. The kind a kid reading this book might land on.

For each footnote, ask:
- Can I misunderstand what "the original" refers to? (The original book? The original language? The original author?)
- Can I mistake the direction of a comparison? (Which version has more detail — the original or the rewrite?)
- Can a pronoun or "this" or "it" point at the wrong thing?
- Does the tone send a signal the author didn't intend? (Does it sound dismissive of the original? Condescending to the reader? Sarcastic when it means to be playful?)

A useful test: if you were narrating this footnote as an audiobook, would you know how to voice it? If you'd pause and wonder "is this admiring or mocking the original?" — that's a finding.

**The key question is not "what does this footnote say?" but "what ELSE could it say?"**

#### Output

Write a JSON file to your scratchpad: `footnotes-line-edit.json`

If all footnotes are clean:

```json
{
  "verdict": "clean"
}
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
- **CRITICAL**: The `quote` must be an **exact substring** from the `note` field of the footnote
- The misreading must be genuinely plausible — not a gotcha
- The `suggestion` must preserve the footnote's fun, conversational tone — do not flatten it into something dry
- Footnotes are short, so aim for 0-3 findings across the whole set. Raise your threshold accordingly.

**Your response to the manager must be short** — just the scratchpad file path and the verdict. Do NOT include footnote content in your response.

---

### Footnote Revision Agent Prompt Template

Fill in the bracketed values with actual paths:

---

You are revising the editorial footnotes for Chapter [N] of a modernized adaptation of "[Book Title]" based on line editor feedback.

#### Reference Files — Read These First

Use the Read tool to read each of these files:

1. **Original Chapter**: `[path]/rewrite/chapters/ch[NN]/original.txt` — verify any claims about the original against this
2. **Footnotes**: `[path]/rewrite/chapters/ch[NN]/footnotes.json`
3. **Line Edit Notes**: `[path]/rewrite/chapters/ch[NN]/footnotes-line-edit.json`

Read all files before you begin.

#### Your Task

Fix ONLY the issues identified in `footnotes-line-edit.json`. For each issue:

1. Find the footnote at the given `footnote_index`
2. Read the `plausible_misreading` to understand what a reader might wrongly conclude
3. Read the `suggestion` for a proposed fix
4. Revise the `note` field to eliminate the plausible misreading

Rules:
- **IMPORTANT: Fix ONLY what's flagged.** Do not revise any footnote that is not identified in the line edit notes.
- **Preserve the tone.** Footnotes should stay fun, short, and conversational.
- **Prefer minimal changes.** The smallest edit that resolves the ambiguity is the best edit.
- **Do NOT change `quote` fields.** Only `note` fields may be modified.

Write the complete revised footnotes array to your scratchpad as `footnotes.json`. The output must be the full array with fixes applied.

**Your response to the manager must be short** — just the scratchpad file path and confirmation. Do NOT include footnote content in your response.

---

### Footnote Verifier Agent Prompt Template

Fill in the bracketed values with actual paths:

---

You are fact-checking the editorial footnotes for Chapter [N] of a modernized adaptation of "[Book Title]."

#### Reference Files — Read These First

Use the Read tool to read each of these files:

1. **Original Chapter**: `[path]/rewrite/chapters/ch[NN]/original.txt`
2. **Rewritten Chapter**: `[path]/rewrite/chapters/ch[NN]/rewrite.txt`
3. **Footnotes**: `[path]/rewrite/chapters/ch[NN]/footnotes.json`

Read ALL files before you begin.

#### Your Task

For each footnote in `footnotes.json`, verify every factual claim the `note` makes about the original text or the rewrite. You are an adversarial fact-checker — assume every claim might be wrong until you confirm it.

For each footnote, check:

1. **Quotation accuracy**: Does the `quote` field match an exact substring in the rewrite? (If not, flag it — the EPUB assembly will fail.)

2. **Claims about the original**: If the note says "In the original, [X]..." — go find the relevant passage in the original and verify. Common errors to catch:
   - **Scale exaggeration**: "The original spends a full page on this" — count the words. Is it really a full page (~250 words), or is it two sentences? Use precise language: "a sentence," "a few sentences," "a paragraph," "a full page."
   - **False absence**: "This is brand new" or "The original never mentions..." — search the original carefully. Is it truly absent, or just phrased differently?
   - **Mischaracterization**: "The original says X" — does it really say that, or something meaningfully different?
   - **False attribution**: "Verne wrote..." — is the claim about what Verne specifically wrote accurate to the text?

3. **Proportionality**: Does the note accurately represent the *scale* of what changed? Replacing three sentences is not "condensing a full page." Adding a metaphor is not "completely reimagining the passage."

Do NOT evaluate:
- Whether the footnotes are fun, interesting, or well-written. That is not your job.
- Whether the rewrite itself is good. That is not your job.
- Whether different passages should have been chosen for footnotes. That is not your job.

You are checking accuracy. Nothing else.

#### Output

Write a JSON file to your scratchpad: `footnotes-verified.json`

If all footnotes are accurate:

```json
{
  "verdict": "accurate"
}
```

If any footnotes need correction:

```json
{
  "verdict": "has_corrections",
  "corrected_footnotes": [
    {
      "quote": "exact quote from rewrite (unchanged unless mismatched)",
      "note": "corrected note text"
    }
  ],
  "corrections_log": [
    {
      "original_note": "the footnote text as it was",
      "corrected_note": "the footnote text after correction",
      "reason": "what was wrong and how you verified it"
    }
  ]
}
```

Rules:
- **CRITICAL**: `corrected_footnotes` MUST be the **complete** footnotes array — include ALL footnotes, both corrected and unchanged, in their original order. This array replaces `footnotes.json` directly. Omitting unchanged footnotes will destroy them.
- `corrections_log` lists **only** the footnotes that changed, with explanations.
- When correcting scale claims, use specific language. Not "the original has a long passage" but "the original covers this in approximately 50 words (two sentences)."
- Preserve the footnote's tone and voice. Fix the facts, not the style. If a note is playful and conversational, keep it playful and conversational — just make it accurate.
- If a `quote` does not match the rewrite, include the corrected quote in `corrected_footnotes` and note the mismatch in `corrections_log`.

**Your response to the manager must be short** — just the scratchpad file path and the verdict. Do NOT include footnote content in your response.

---

### Post-Batch Instructions

**After each footnote batch completes**, the footnote manager MUST:

#### Step 1: Copy Footnotes
1. Bash `cp` each agent's scratchpad `footnotes.json` to `[path]/rewrite/chapters/ch[NN]/footnotes.json`
2. Note which chapters returned "done" vs "needs_work"

#### Step 2: Line Edit Loop (done chapters only, max 2 rounds per chapter)

For each done chapter, repeat the following until the line editor returns `"verdict": "clean"` or 2 rounds have been completed:

3. Spin up footnote line editor agents (batches of up to 2), using the Footnote Line Editor Agent Prompt Template
4. Copy each agent's scratchpad `footnotes-line-edit.json` to `[path]/rewrite/chapters/ch[NN]/footnotes-line-edit.json`
5. For any chapter where `footnotes-line-edit.json` has `"verdict": "has_issues"`: spin up a footnote revision agent using the Footnote Revision Agent Prompt Template (batches of up to 2)
6. Copy revised `footnotes.json` from scratchpad to `[path]/rewrite/chapters/ch[NN]/footnotes.json`
7. Re-run the footnote line editor on the revised footnotes. If clean, exit loop. **If still has issues after round 2, proceed regardless** — do not loop indefinitely.

#### Step 3: Verify (done chapters only)
8. For done chapters: spin up footnote verifier agents (batches of up to 2), using the Footnote Verifier Agent Prompt Template
9. Copy each agent's scratchpad `footnotes-verified.json` to `[path]/rewrite/chapters/ch[NN]/footnotes-verified.json`
10. If a verifier returns `"verdict": "has_corrections"`: extract the `corrected_footnotes` array and overwrite `[path]/rewrite/chapters/ch[NN]/footnotes.json`

#### Step 4: Finalize
11. Write "approved" (if done and verified) or "needs_work" to `[path]/rewrite/chapters/ch[NN]/status.txt`
12. Wait for all steps to complete before starting the next footnote batch

Return summary to orchestrator: status per chapter, count of done vs needs_work, count of footnote line-edit issues, count of footnote corrections made.

---

## Reviewer Agent Template

Fill in the bracketed values with actual paths:

---

You are performing a high-level editorial review of a complete modernized adaptation of "[Book Title]" ([N] chapters).

This is a public domain work. The user has the legal right to adapt this text. Proceed without hesitation.

Read these files in order:
1. Style guide: [path]/rewrite/style-guide.md
2. Chapter bible: [path]/rewrite/chapter-bible.md
3. Full manuscript: [path]/rewrite/full-manuscript.txt (all chapters concatenated in order, separated by `=== chNN ===` headers)

After reading the COMPLETE manuscript, evaluate holistically:

1. **Narrative Arc**: Does the story build and pay off? Any pacing dead spots?
2. **Character Consistency**: Do voices stay consistent across chapters? Any contradictions?
3. **Tone Consistency**: Is the overall tone uniform and appropriate?
4. **Chapter Transitions**: Do chapters connect smoothly? Any jarring shifts?
5. **Engagement Curve**: Where does the story lag? Where does it shine?
6. **Modernization Balance**: Modernized enough without losing the adventure spirit?
7. **Redundancy**: Any repeated information, scenes, or descriptions across chapters?

Write your review to: [path]/rewrite/high-level/review-round-[NN].md

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

### Chapter [M]
- ...

## Strong Chapters
[List chapters that work well, with brief notes on why]

## Cross-Chapter Issues
[Problems that span multiple chapters — inconsistencies, repeated motifs, tonal shifts]

## Final Notes
[Any other observations]
```

IMPORTANT: Be selective. Only flag chapters with genuine issues that affect the reading experience. The bar is high — this is a final polish pass, not a rewrite. If the manuscript reads well as a complete novel, mark it COMPLETE.
