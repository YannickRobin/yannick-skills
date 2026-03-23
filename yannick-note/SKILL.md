---
name: yannick-note
description: Manage personal notes persisted in a remote GitHub repository. Use this skill whenever the user runs /yannick-note, says "take a note", "add a note", "note that", "search my notes", "find note", "delete note", "update note", "list notes", or any phrase suggesting they want to store, retrieve, modify, or remove a personal note. Always use this skill for note-related requests — even if the user doesn't say "note" explicitly but clearly wants to record or recall personal information.
---

# yannick-note

Manage personal notes in a `NOTES.md` file stored in a remote GitHub repository.

## First-time setup

Before any operation, check if the repo is configured:

```bash
python <skill-dir>/scripts/note_manager.py config
```

If not configured (exit code 1 or "not configured" output), ask the user for their GitHub repo URL, then run:

```bash
python <skill-dir>/scripts/note_manager.py setup <GITHUB_REPO_URL>
```

This clones the repo to `~/.yannick-notes/repo/` and saves the URL to `~/.yannick-notes/config.json`. This only needs to happen once.

## Operations

### Add a note
When the user says "take a note: ...", "add a note: ...", "note that ...", extract:
- **title**: a concise title summarizing the note (generate one if not given)
- **content**: the full note content

```bash
python <skill-dir>/scripts/note_manager.py add "<title>" "<content>"
```

### Search notes
When the user says "search notes for ...", "find note about ...", "do I have a note on ...":

```bash
python <skill-dir>/scripts/note_manager.py search "<query>"
```

### List all notes
When the user says "list my notes", "show all notes", "what notes do I have":

```bash
python <skill-dir>/scripts/note_manager.py list
```

### Delete a note
When the user says "delete note about ...", "remove note ...":
- Use title keywords or timestamp as identifier

```bash
python <skill-dir>/scripts/note_manager.py delete "<identifier>"
```

Show the user what will be deleted and confirm before running if there's ambiguity.

### Update a note
When the user says "update note about ...", "change note ...":
- Identify the note, then ask for the new content if not provided

```bash
python <skill-dir>/scripts/note_manager.py update "<identifier>" "<new_content>"
```

## Note format in NOTES.md

Each note looks like this:

```markdown
## [2026-03-23 14:30] Your note title

Note content goes here.
```

Notes are separated by `---`. The script handles all formatting — don't write to NOTES.md directly.

## After every write operation

The script automatically:
1. Pulls latest from the remote repo (to avoid conflicts)
2. Appends/modifies `NOTES.md`
3. Commits with a descriptive message
4. Pushes to the remote repo

Confirm success to the user after each operation and summarize what was done.

## Error handling

- **Clone fails**: Check if the URL is correct and the user has push access. They may need to `gh auth login` or configure SSH keys.
- **Push fails**: A pull conflict may have occurred — inform the user and suggest resolving manually.
- **Note not found for delete/update**: Tell the user no match was found and offer to list all notes so they can identify the right one.
