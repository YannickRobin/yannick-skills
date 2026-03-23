# yannick-skills

Personal productivity skills for Claude Code.

## Installation

### 1. Register the marketplace

Add `yannick-skills` to your `~/.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "yannick-skills": {
      "source": {
        "source": "git",
        "url": "https://github.tools.sap/I303937/yannick-skills.git"
      }
    }
  }
}
```

### 2. Enable a skill

In the same `settings.json`, add the skill to `enabledPlugins`:

```json
{
  "enabledPlugins": {
    "yannick-note@yannick-skills": true
  }
}
```

### 3. Restart Claude Code

The skill will be available in your next session.

---

## Available Skills

| Skill | Description |
|-------|-------------|
| `yannick-note` | Manage personal notes persisted in a remote GitHub repository |
