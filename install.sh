#!/bin/bash
# Install the rewrite-book skill for Claude Code
#
# This script:
# 1. Copies skill files to ~/.claude/commands/
# 2. Creates a config.json from the example template
# 3. Auto-fills the epub-utils path

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMMANDS_DIR="$HOME/.claude/commands"
SKILL_DIR="$COMMANDS_DIR/rewrite-book"

echo "Installing rewrite-book skill..."
echo "  Source: $SCRIPT_DIR/skill/"
echo "  Target: $COMMANDS_DIR/"
echo ""

# Create target directories
mkdir -p "$SKILL_DIR"

# Copy skill files
cp "$SCRIPT_DIR/skill/rewrite-book.md" "$COMMANDS_DIR/rewrite-book.md"
cp "$SCRIPT_DIR/skill/setup.md" "$SKILL_DIR/"
cp "$SCRIPT_DIR/skill/agent-templates.md" "$SKILL_DIR/"
cp "$SCRIPT_DIR/skill/assembly.md" "$SKILL_DIR/"
cp "$SCRIPT_DIR/skill/audiobook.md" "$SKILL_DIR/"

echo "Skill files installed."

# Create config if it doesn't exist
CONFIG="$SKILL_DIR/config.json"
if [ -f "$CONFIG" ]; then
  echo "Config already exists at $CONFIG — skipping."
else
  # Copy example and fill in epub-utils path
  sed "s|EPUB_UTILS_PATH_PLACEHOLDER|$SCRIPT_DIR/epub-utils/epub_utils.py|" \
    "$SCRIPT_DIR/config.example.json" > "$CONFIG"
  echo "Config created at $CONFIG"
  echo ""
  echo "Edit $CONFIG to configure:"
  echo "  - epub_source: set type to \"calibre\" and fill in SSH details to fetch from a remote calibre library"
  echo "  - upload: enable to auto-upload finished EPUBs to a calibre server"
  echo "  - audiobook_sync: enable to sync generated M4B files to a remote server"
  echo ""
  echo "Defaults work out of the box — you'll just be asked to provide a local EPUB path."
fi

echo ""
echo "Done. Run /rewrite-book <title> in Claude Code to get started."
