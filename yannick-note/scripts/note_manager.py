#!/usr/bin/env python3
"""
note_manager.py — CRUD operations on NOTES.md in a remote GitHub repo.

Usage:
  note_manager.py config              Check if repo is configured
  note_manager.py setup <url>         Clone repo and save config
  note_manager.py add <title> <body>  Add a new note
  note_manager.py search <query>      Search notes by keyword
  note_manager.py list                List all note titles
  note_manager.py delete <id>         Delete note matching title/timestamp
  note_manager.py update <id> <body>  Update note matching title/timestamp
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

CONFIG_DIR = Path.home() / ".yannick-notes"
CONFIG_FILE = CONFIG_DIR / "config.json"
REPO_DIR = CONFIG_DIR / "repo"
NOTES_FILE = REPO_DIR / "NOTES.md"

NOTE_HEADER_RE = re.compile(r"^## \[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\] (.+)$", re.MULTILINE)
SEPARATOR = "\n\n---\n\n"


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def save_config(config: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def git(*args, cwd=None):
    cwd = str(cwd or REPO_DIR)
    result = subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"git error: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def pull():
    git("pull", "--rebase", "origin", "HEAD")


def commit_and_push(message: str):
    git("add", "NOTES.md")
    # Only commit if there are staged changes
    status = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=str(REPO_DIR)
    )
    if status.returncode == 0:
        print("Nothing to commit.")
        return
    git("commit", "-m", message)
    git("push")


# ---------------------------------------------------------------------------
# Notes file helpers
# ---------------------------------------------------------------------------

def read_raw() -> str:
    if not NOTES_FILE.exists():
        return ""
    with open(NOTES_FILE) as f:
        return f.read()


def write_raw(content: str):
    with open(NOTES_FILE, "w") as f:
        f.write(content)


def split_notes(raw: str) -> list[str]:
    """Split raw NOTES.md content into individual note blocks."""
    return [n.strip() for n in re.split(r"\n\n---\n\n|\n---\n", raw) if n.strip()]


def join_notes(notes: list[str]) -> str:
    if not notes:
        return ""
    return SEPARATOR.join(notes) + "\n"


def note_matches(note: str, identifier: str) -> bool:
    """Return True if the identifier matches the note's timestamp or title (case-insensitive)."""
    m = NOTE_HEADER_RE.search(note)
    if not m:
        return False
    timestamp, title = m.groups()
    ident_lower = identifier.lower()
    return ident_lower in title.lower() or ident_lower in timestamp


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_config():
    config = load_config()
    if config.get("repo_url") and REPO_DIR.exists():
        print(f"configured: {config['repo_url']}")
        sys.exit(0)
    else:
        print("not configured")
        sys.exit(1)


def cmd_setup(repo_url: str):
    config = load_config()
    config["repo_url"] = repo_url
    save_config(config)

    if REPO_DIR.exists():
        git("remote", "set-url", "origin", repo_url)
        print(f"Updated remote URL to: {repo_url}")
    else:
        subprocess.run(["git", "clone", repo_url, str(REPO_DIR)], check=True)
        print(f"Cloned repo to: {REPO_DIR}")

    # Ensure NOTES.md exists
    if not NOTES_FILE.exists():
        write_raw("# Notes\n\n")
        commit_and_push("note: initialise NOTES.md")

    print("Setup complete.")


def cmd_add(title: str, content: str):
    pull()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_note = f"## [{now}] {title}\n\n{content}"

    raw = read_raw()
    if raw.strip():
        write_raw(raw.rstrip() + SEPARATOR + new_note + "\n")
    else:
        write_raw(new_note + "\n")

    commit_and_push(f"note: add '{title}'")
    print(f"Added note: [{now}] {title}")


def cmd_search(query: str):
    raw = read_raw()
    if not raw.strip():
        print("No notes yet.")
        return

    notes = split_notes(raw)
    matches = [n for n in notes if query.lower() in n.lower()]

    if not matches:
        print(f"No notes found matching '{query}'.")
        return

    print(f"Found {len(matches)} note(s) matching '{query}':\n")
    for i, note in enumerate(matches, 1):
        print(f"--- [{i}] ---")
        print(note)
        print()


def cmd_list():
    raw = read_raw()
    if not raw.strip():
        print("No notes yet.")
        return

    headers = NOTE_HEADER_RE.findall(raw)
    if not headers:
        print("No structured notes found.")
        return

    print(f"{len(headers)} note(s):\n")
    for i, (timestamp, title) in enumerate(headers, 1):
        print(f"  {i:>3}. [{timestamp}] {title}")


def cmd_delete(identifier: str):
    pull()
    raw = read_raw()
    notes = split_notes(raw)

    to_delete = [n for n in notes if note_matches(n, identifier)]
    if not to_delete:
        print(f"No note found matching '{identifier}'.")
        sys.exit(1)

    if len(to_delete) > 1:
        print(f"Multiple notes match '{identifier}':")
        for n in to_delete:
            m = NOTE_HEADER_RE.search(n)
            if m:
                print(f"  [{m.group(1)}] {m.group(2)}")
        print("Please use a more specific identifier.")
        sys.exit(1)

    kept = [n for n in notes if not note_matches(n, identifier)]
    write_raw(join_notes(kept))

    target = NOTE_HEADER_RE.search(to_delete[0])
    label = f"[{target.group(1)}] {target.group(2)}" if target else identifier
    commit_and_push(f"note: delete '{label}'")
    print(f"Deleted note: {label}")


def cmd_update(identifier: str, new_content: str):
    pull()
    raw = read_raw()
    notes = split_notes(raw)

    matches = [n for n in notes if note_matches(n, identifier)]
    if not matches:
        print(f"No note found matching '{identifier}'.")
        sys.exit(1)

    if len(matches) > 1:
        print(f"Multiple notes match '{identifier}':")
        for n in matches:
            m = NOTE_HEADER_RE.search(n)
            if m:
                print(f"  [{m.group(1)}] {m.group(2)}")
        print("Please use a more specific identifier.")
        sys.exit(1)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    original = NOTE_HEADER_RE.search(matches[0])
    orig_ts = original.group(1) if original else "unknown"
    title = original.group(2) if original else identifier

    updated_note = f"## [{now}] {title}\n\n{new_content}\n\n*(Updated — originally [{orig_ts}])*"
    new_notes = [updated_note if note_matches(n, identifier) else n for n in notes]
    write_raw(join_notes(new_notes))

    commit_and_push(f"note: update '{title}'")
    print(f"Updated note: [{now}] {title}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    cmd = args[0]

    if cmd == "config":
        cmd_config()
    elif cmd == "setup":
        if len(args) < 2:
            print("Usage: note_manager.py setup <repo_url>", file=sys.stderr)
            sys.exit(1)
        cmd_setup(args[1])
    elif cmd == "add":
        if len(args) < 3:
            print("Usage: note_manager.py add <title> <content>", file=sys.stderr)
            sys.exit(1)
        cmd_add(args[1], args[2])
    elif cmd == "search":
        if len(args) < 2:
            print("Usage: note_manager.py search <query>", file=sys.stderr)
            sys.exit(1)
        cmd_search(args[1])
    elif cmd == "list":
        cmd_list()
    elif cmd == "delete":
        if len(args) < 2:
            print("Usage: note_manager.py delete <identifier>", file=sys.stderr)
            sys.exit(1)
        cmd_delete(args[1])
    elif cmd == "update":
        if len(args) < 3:
            print("Usage: note_manager.py update <identifier> <new_content>", file=sys.stderr)
            sys.exit(1)
        cmd_update(args[1], args[2])
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
