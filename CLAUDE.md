# CLAUDE.md — rewrite-books

This repo is the **source of truth** for the `/rewrite-book` Claude Code skill. The skill that runs from `~/.claude/commands/rewrite-book*` is **deployed from here** by `install.sh`.

## Editing rules (IMPORTANT)

- **Edit `skill/` in this repo, NOT the deployed `~/.claude/commands/` copies.** Deployed edits get clobbered on the next `install.sh`, and the repo silently drifts behind.
- **Keep it generic — this repo is shared publicly.** NEVER commit personal/environment-specific values (SSH hosts like `user@host`, home directories, server mount paths). Environment specifics come from `config.json` (`epub_source` Mode A/B, `upload`, `audiobook_sync`); the deployed personal install fills those in. Do not revert this `config.json` genericization.
- `gates.py` and `rewrite/prompts/*` are **generated per-book at runtime** — `gates.py` is embedded as a code block in `skill/setup.md` §0.7; the prompt files are compiled by the setup agent in §0.6. Don't add standalone copies to the repo. Don't commit per-book run artifacts beyond the curated `examples/` sample.

## "Sync up the skill changes with the repo"

During use, the latest tested skill edits land on the **deployed** copies (because that's where the running skill lives). This procedure ports them back here.

1. **Port logic, not personal paths.** For each file below, diff the deployed copy against its repo counterpart and bring over the *logic/architecture* changes — never personal paths, and without reverting the repo's `config.json` abstraction:

   | deployed | repo |
   |---|---|
   | `~/.claude/commands/rewrite-book.md` | `skill/rewrite-book.md` |
   | `~/.claude/commands/rewrite-book/setup.md` | `skill/setup.md` |
   | `~/.claude/commands/rewrite-book/agent-templates.md` | `skill/agent-templates.md` |
   | `~/.claude/commands/rewrite-book/assembly.md` | `skill/assembly.md` |
   | `~/.claude/commands/rewrite-book/audiobook.md` | `skill/audiobook.md` |

   Note `agent-templates.md` has no environment-specific content (clean copy is usually fine); `setup.md` / `assembly.md` / `audiobook.md` / `rewrite-book.md` mix logic with config-driven sections — merge carefully.

2. **Verify before committing:**
   - No personal paths leaked: `grep -rniE 'ssh +[a-z]+@|scp +[a-z]+@|/Users/|/home/|/media/' skill/` → should be empty.
   - The `gates.py` embedded in `skill/setup.md` §0.7 still parses as Python (extract the ```python block and `python3 -c 'import ast; ast.parse(...)'`).
   - Phase numbering in `skill/rewrite-book.md` is consistent (no duplicate/missing phase headers).

3. **Commit + push** to `main` with a message describing the logic change.

> The deployed copies are hardcoded to a personal calibre/Pi setup; the repo versions are `config.json`-driven. They are **architecturally identical** — only the environment binding differs. Keep it that way.

## Layout

```
skill/                 # the deployed skill (install.sh copies to ~/.claude/commands/)
  rewrite-book.md      # orchestrator playbook
  setup.md             # Phase 0 (incl. §0.6 prompts, §0.7 gates.py)
  agent-templates.md   # worker dispatch contract + per-step worker templates
  assembly.md          # Phase 6 EPUB rebuild/upload
  audiobook.md         # Phase 7 audiobook
epub-utils/            # shared stdlib EPUB library + its CLAUDE.md
examples/              # one curated sample run
config.example.json    # template; install.sh creates the real config.json
install.sh             # deploys skill/ -> ~/.claude/commands/, writes config.json
```
