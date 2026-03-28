#!/usr/bin/env python3
"""
note_manager.py — CRUD operations on per-note files in a remote GitHub repo.

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
NOTES_DIR = REPO_DIR / "notes"

NOTE_HEADER_RE = re.compile(r"^## \[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\] (.+)$", re.MULTILINE)


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


def commit_and_push(filepath: str, message: str, remove: bool = False):
    if remove:
        git("rm", filepath)
    else:
        git("add", filepath)
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
# Note file helpers
# ---------------------------------------------------------------------------

def slugify(title: str) -> str:
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "note"


def make_filename(title: str) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = slugify(title)
    return f"{ts}-{slug}.md"


def ensure_notes_dir():
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    if not any(NOTES_DIR.iterdir()):
        gitkeep = NOTES_DIR / ".gitkeep"
        gitkeep.touch()
        git("add", "notes/.gitkeep")
        status = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=str(REPO_DIR)
        )
        if status.returncode != 0:
            git("commit", "-m", "note: initialise notes directory")
            git("push")


def get_note_files() -> list[Path]:
    if not NOTES_DIR.exists():
        return []
    return sorted(p for p in NOTES_DIR.glob("*.md") if p.name != ".gitkeep")


def read_note(path: Path) -> str:
    with open(path) as f:
        return f.read()


def write_note(path: Path, content: str):
    with open(path, "w") as f:
        f.write(content)


def parse_header(content: str):
    """Return (timestamp, title) or (None, None)."""
    m = NOTE_HEADER_RE.search(content)
    if m:
        return m.group(1), m.group(2)
    return None, None


def note_file_matches(path: Path, identifier: str) -> bool:
    """Return True if identifier matches note title, timestamp, or filename stem."""
    content = read_note(path)
    timestamp, title = parse_header(content)
    ident_lower = identifier.lower()
    if title and ident_lower in title.lower():
        return True
    if timestamp and ident_lower in timestamp:
        return True
    if ident_lower in path.stem.lower():
        return True
    return False


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

    ensure_notes_dir()
    print("Setup complete.")


def cmd_add(title: str, content: str):
    pull()
    ensure_notes_dir()

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    filename = make_filename(title)
    note_path = NOTES_DIR / filename
    write_note(note_path, f"## [{now}] {title}\n\n{content}\n")

    commit_and_push(f"notes/{filename}", f"note: add '{title}'")
    print(f"Added note: [{now}] {title} ({filename})")


def cmd_search(query: str):
    files = get_note_files()
    if not files:
        print("No notes yet.")
        return

    matches = [(p, read_note(p)) for p in files if query.lower() in read_note(p).lower()]

    if not matches:
        print(f"No notes found matching '{query}'.")
        return

    print(f"Found {len(matches)} note(s) matching '{query}':\n")
    for i, (path, content) in enumerate(matches, 1):
        print(f"--- [{i}] ---")
        print(content)
        print()


def cmd_list():
    files = get_note_files()
    if not files:
        print("No notes yet.")
        return

    print(f"{len(files)} note(s):\n")
    for i, path in enumerate(files, 1):
        content = read_note(path)
        timestamp, title = parse_header(content)
        if timestamp and title:
            print(f"  {i:>3}. [{timestamp}] {title}")
        else:
            print(f"  {i:>3}. {path.name}")


def cmd_delete(identifier: str):
    pull()
    files = get_note_files()

    matches = [p for p in files if note_file_matches(p, identifier)]
    if not matches:
        print(f"No note found matching '{identifier}'.")
        sys.exit(1)

    if len(matches) > 1:
        print(f"Multiple notes match '{identifier}':")
        for p in matches:
            ts, title = parse_header(read_note(p))
            print(f"  [{ts}] {title}" if ts and title else f"  {p.name}")
        print("Please use a more specific identifier.")
        sys.exit(1)

    target = matches[0]
    ts, title = parse_header(read_note(target))
    label = f"[{ts}] {title}" if ts and title else target.name

    commit_and_push(f"notes/{target.name}", f"note: delete '{label}'", remove=True)
    print(f"Deleted note: {label}")


def cmd_update(identifier: str, new_content: str):
    pull()
    files = get_note_files()

    matches = [p for p in files if note_file_matches(p, identifier)]
    if not matches:
        print(f"No note found matching '{identifier}'.")
        sys.exit(1)

    if len(matches) > 1:
        print(f"Multiple notes match '{identifier}':")
        for p in matches:
            ts, title = parse_header(read_note(p))
            print(f"  [{ts}] {title}" if ts and title else f"  {p.name}")
        print("Please use a more specific identifier.")
        sys.exit(1)

    target = matches[0]
    orig_ts, title = parse_header(read_note(target))
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    write_note(target, f"## [{now}] {title}\n\n{new_content}\n\n*(Updated — originally [{orig_ts}])*\n")

    commit_and_push(f"notes/{target.name}", f"note: update '{title}'")
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
