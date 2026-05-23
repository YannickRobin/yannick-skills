#!/usr/bin/env python3
"""
todo_manager.py — CRUD operations on TODOS.md in a remote GitHub repo.

Usage:
  todo_manager.py config                            Check if repo is configured
  todo_manager.py setup <url>                       Clone repo and save config
  todo_manager.py add <title> [priority] [due]       Add a new todo (priority: high|medium|low, default: medium; due: YYYY-MM-DD|none, default: none)
  todo_manager.py list [all]                         List open todos (sorted by priority then due date); 'all' includes completed
  todo_manager.py complete <identifier>             Mark a todo as done
  todo_manager.py delete <identifier>               Permanently delete a todo
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
TODOS_FILE = REPO_DIR / "TODOS.md"

# Format: ## [ ] [high] [2026-03-25] Buy groceries
TODO_HEADER_RE = re.compile(
    r"^## (\[[ x]\]) \[(high|medium|low)\] \[([^\]]+)\] (.+)$",
    re.MULTILINE
)
SEPARATOR = "\n\n---\n\n"
PRIORITY_ORDER = {"high": 1, "medium": 2, "low": 3}


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
    git("add", "TODOS.md")
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
# Todos file helpers
# ---------------------------------------------------------------------------

def read_raw() -> str:
    if not TODOS_FILE.exists():
        return ""
    with open(TODOS_FILE) as f:
        return f.read()


def write_raw(content: str):
    with open(TODOS_FILE, "w") as f:
        f.write(content)


def split_todos(raw: str) -> list[str]:
    return [t.strip() for t in re.split(r"\n\n---\n\n|\n---\n", raw) if t.strip()]


def join_todos(todos: list[str]) -> str:
    if not todos:
        return ""
    return SEPARATOR.join(todos) + "\n"


def parse_header(todo: str):
    """Returns (status, priority, due, title) or None."""
    m = TODO_HEADER_RE.search(todo)
    if not m:
        return None
    status = m.group(1)   # '[ ]' or '[x]'
    priority = m.group(2)
    due = m.group(3)
    title = m.group(4)
    return status, priority, due, title


def sort_key(todo: str):
    parsed = parse_header(todo)
    if not parsed:
        return (99, "9999-99-99", "")
    _, priority, due, title = parsed
    due_sort = due if re.match(r"\d{4}-\d{2}-\d{2}", due) else "9999-99-99"
    return (PRIORITY_ORDER.get(priority, 99), due_sort, title.lower())


def todo_matches(todo: str, identifier: str) -> bool:
    parsed = parse_header(todo)
    if not parsed:
        return False
    _, _, _, title = parsed
    return identifier.lower() in title.lower()


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

    if not TODOS_FILE.exists():
        write_raw("# Todos\n\n")
        commit_and_push("todo: initialise TODOS.md")

    print("Setup complete.")


def cmd_add(title: str, priority: str, due: str):
    priority = priority.lower()
    if priority not in PRIORITY_ORDER:
        print(f"Invalid priority '{priority}'. Use: high, medium, low", file=sys.stderr)
        sys.exit(1)

    # Validate due date format
    if due != "none" and not re.match(r"^\d{4}-\d{2}-\d{2}$", due):
        print(f"Invalid due date '{due}'. Use YYYY-MM-DD or 'none'", file=sys.stderr)
        sys.exit(1)

    pull()
    new_todo = f"## [ ] [{priority}] [{due}] {title}"

    raw = read_raw()
    if raw.strip():
        write_raw(raw.rstrip() + SEPARATOR + new_todo + "\n")
    else:
        write_raw(new_todo + "\n")

    commit_and_push(f"todo: add '{title}'")
    due_str = f" (due {due})" if due != "none" else ""
    print(f"Added todo [{priority}]{due_str}: {title}")


def cmd_list(show_all: bool = False):
    raw = read_raw()
    if not raw.strip():
        print("No todos yet.")
        return

    todos = split_todos(raw)
    open_todos = [t for t in todos if parse_header(t) and parse_header(t)[0] == "[ ]"]
    done_todos = [t for t in todos if parse_header(t) and parse_header(t)[0] == "[x]"]

    open_sorted = sorted(open_todos, key=sort_key)

    if not open_sorted and not (show_all and done_todos):
        print("All done! No open todos.")
        return

    if open_sorted:
        print(f"Open todos ({len(open_sorted)}):\n")
        for i, todo in enumerate(open_sorted, 1):
            parsed = parse_header(todo)
            if parsed:
                _, priority, due, title = parsed
                due_str = f" · due {due}" if due != "none" else ""
                priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "  ")
                print(f"  {i:>3}. {priority_icon} [{priority}]{due_str} — {title}")

    if show_all and done_todos:
        print(f"\nCompleted ({len(done_todos)}):\n")
        for i, todo in enumerate(done_todos, 1):
            parsed = parse_header(todo)
            if parsed:
                _, priority, due, title = parsed
                print(f"  {i:>3}. ✓ [{priority}] — {title}")


def cmd_complete(identifier: str):
    pull()
    raw = read_raw()
    todos = split_todos(raw)

    matches = [t for t in todos if todo_matches(t, identifier) and parse_header(t) and parse_header(t)[0] == "[ ]"]
    if not matches:
        print(f"No open todo found matching '{identifier}'.")
        sys.exit(1)

    if len(matches) > 1:
        print(f"Multiple todos match '{identifier}':")
        for t in matches:
            parsed = parse_header(t)
            if parsed:
                _, priority, due, title = parsed
                print(f"  [{priority}] [{due}] {title}")
        print("Please use a more specific identifier.")
        sys.exit(1)

    target = matches[0]
    completed = target.replace("## [ ]", "## [x]", 1)
    new_todos = [completed if t == target else t for t in todos]
    write_raw(join_todos(new_todos))

    parsed = parse_header(target)
    title = parsed[3] if parsed else identifier
    commit_and_push(f"todo: complete '{title}'")
    print(f"Completed: {title}")


def cmd_delete(identifier: str):
    pull()
    raw = read_raw()
    todos = split_todos(raw)

    to_delete = [t for t in todos if todo_matches(t, identifier)]
    if not to_delete:
        print(f"No todo found matching '{identifier}'.")
        sys.exit(1)

    if len(to_delete) > 1:
        print(f"Multiple todos match '{identifier}':")
        for t in to_delete:
            parsed = parse_header(t)
            if parsed:
                _, priority, due, title = parsed
                print(f"  [{priority}] [{due}] {title}")
        print("Please use a more specific identifier.")
        sys.exit(1)

    kept = [t for t in todos if t not in to_delete]
    write_raw(join_todos(kept))

    parsed = parse_header(to_delete[0])
    title = parsed[3] if parsed else identifier
    commit_and_push(f"todo: delete '{title}'")
    print(f"Deleted: {title}")


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
            print("Usage: todo_manager.py setup <repo_url>", file=sys.stderr)
            sys.exit(1)
        cmd_setup(args[1])
    elif cmd == "add":
        if len(args) < 2:
            print("Usage: todo_manager.py add <title> [priority] [due]", file=sys.stderr)
            sys.exit(1)
        priority = args[2] if len(args) > 2 else "medium"
        due = args[3] if len(args) > 3 else "none"
        cmd_add(args[1], priority, due)
    elif cmd == "list":
        show_all = len(args) > 1 and args[1] == "all"
        cmd_list(show_all)
    elif cmd == "complete":
        if len(args) < 2:
            print("Usage: todo_manager.py complete <identifier>", file=sys.stderr)
            sys.exit(1)
        cmd_complete(args[1])
    elif cmd == "delete":
        if len(args) < 2:
            print("Usage: todo_manager.py delete <identifier>", file=sys.stderr)
            sys.exit(1)
        cmd_delete(args[1])
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
