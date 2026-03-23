---
name: yannick-todo
description: Manage a personal todo list persisted in a remote GitHub repository. Use this skill whenever the user runs /yannick-todo, says "add a todo", "add to my todo list", "remind me to", "I need to", "mark X as done", "complete X", "what's on my todo list", "show my todos", "delete todo", or any phrase suggesting they want to capture, review, complete, or remove a personal task. Always use this skill for task/todo-related requests — even if the user doesn't say "todo" explicitly but clearly wants to track something they need to do.
---

# yannick-todo

Manage a personal todo list in a `TODOS.md` file stored in a remote GitHub repository. Todos are sorted by priority (high → medium → low) then by due date.

## First-time setup

Before any operation, check if the repo is configured:

```bash
python <skill-dir>/scripts/todo_manager.py config
```

If not configured (exit code 1 or "not configured" output), ask the user for their GitHub repo URL, then run:

```bash
python <skill-dir>/scripts/todo_manager.py setup <GITHUB_REPO_URL>
```

This clones the repo to `~/.yannick-notes/repo/` and saves the URL to `~/.yannick-notes/config.json`. The same repo is shared with `yannick-note` — no separate setup needed if the user already configured that skill.

## Operations

### Add a todo
When the user says "add a todo", "add to my list", "remind me to", "I need to ...":
- Extract a **title** (concise description of the task)
- **priority** is optional — infer from context or omit to default to `medium` (`high`, `medium`, `low`)
- **due date** is optional — infer from context or omit to default to `none` (`YYYY-MM-DD`)

```bash
python <skill-dir>/scripts/todo_manager.py add "<title>" [priority] [due]
```

Examples:
```bash
python <skill-dir>/scripts/todo_manager.py add "Review PR for auth module" "high" "2026-03-25"
python <skill-dir>/scripts/todo_manager.py add "Update README" "low"
python <skill-dir>/scripts/todo_manager.py add "Buy coffee"
```

### List todos
When the user says "what's on my todo list", "show my todos", "list todos":

```bash
python <skill-dir>/scripts/todo_manager.py list
```

To include completed todos:

```bash
python <skill-dir>/scripts/todo_manager.py list all
```

Todos are displayed sorted by priority (high first) then by due date (earliest first). Todos with no due date appear last.

### Complete a todo
When the user says "mark X as done", "complete X", "I finished X", "done with X":
- Identify the todo by title keyword

```bash
python <skill-dir>/scripts/todo_manager.py complete "<identifier>"
```

Completed todos are archived (kept in the file with `[x]` status) and visible with `list all`.

### Delete a todo
When the user says "delete todo about X", "remove X from my list":
- Confirm with the user before deleting if there's ambiguity

```bash
python <skill-dir>/scripts/todo_manager.py delete "<identifier>"
```

## Todo format in TODOS.md

Each todo looks like this:

```markdown
## [ ] [high] [2026-03-25] Review PR for auth module

---

## [x] [low] [none] Update README
```

- `[ ]` = open, `[x]` = completed
- Priority: `high`, `medium`, `low`
- Due date: `YYYY-MM-DD` or `none`

The script handles all formatting — don't write to TODOS.md directly.

## After every write operation

The script automatically:
1. Pulls latest from the remote repo (to avoid conflicts)
2. Appends/modifies `TODOS.md`
3. Commits with a descriptive message
4. Pushes to the remote repo

Confirm success to the user after each operation and summarize what was done.

## Error handling

- **Clone fails**: Check if the URL is correct and the user has push access. They may need to `gh auth login` or configure SSH keys.
- **Push fails**: A pull conflict may have occurred — inform the user and suggest resolving manually.
- **Todo not found**: Tell the user no match was found and offer to list all todos so they can identify the right one.
- **Multiple matches**: Show all matching todos and ask the user to be more specific.
