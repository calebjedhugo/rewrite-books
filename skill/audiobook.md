# Phase 7: Audiobook Generation

These instructions are for the Phase 7 Task agent. The orchestrator reads this file and passes its contents (with paths and config values filled in) to the audiobook agent. Use a long timeout — the `say` command generates audio at roughly real-time speed, so a full book takes 20-40 minutes.

---

1. **Create a working directory** for intermediate audio files (use the scratchpad)

2. **Generate audio for each chapter** in order (ch01 through chNN):
   ```bash
   say -v "Daniel" -o <work-dir>/chNN.aiff -f <path>/rewrite/chapters/chNN/rewrite.txt
   afconvert <work-dir>/chNN.aiff <work-dir>/chNN.m4a -f m4af -d aac
   rm <work-dir>/chNN.aiff
   ```

3. **Build ffmpeg concat list and chapter metadata**:
   - Write `concat.txt` listing each M4A in order
   - Write `chapters.txt` in ffmetadata format with chapter markers (using `ffprobe` to get each M4A's duration and calculating cumulative timestamps)
   - Include book title and author in the metadata

4. **Combine into M4B**:
   ```bash
   ffmpeg -y -f concat -safe 0 -i concat.txt -i chapters.txt -map_metadata 1 -c copy "<path>/<book-slug>.m4b"
   ```

5. **Sync to remote server (optional)**:

   **The orchestrator will tell you whether audiobook sync is enabled based on config.** If sync is not enabled, skip this step.

   If enabled, the orchestrator provides: `<sync-ssh>` (SSH host) and `<sync-remote-path>` (destination directory on the remote server).

   ```bash
   ssh <sync-ssh> "mkdir -p <sync-remote-path>"
   scp "<path>/<book-slug>.m4b" <sync-ssh>:<sync-remote-path>/
   ```

6. **Report back**: file size, total duration, and confirmation of remote sync (if enabled).

**Notes:**
- Voice: Daniel (British English). Can be changed if the user requests a different voice.
- Requires macOS (uses `say` and `afconvert`). Also requires `ffmpeg` and `ffprobe` to be installed.
- No additional backups needed — fully regenerable from rewrite text files.
