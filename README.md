# asma - Claude Code Skills Manager

A declarative package manager for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills, inspired by vim-plug and Vundle.

> **Note**: This tool is specifically designed for Claude Code's skill system. It manages skills installed to `~/.claude/skills/` (global) and `.claude/skills/` (project).

## Disclaimer

> **This is an alpha version of a personal project.**
>
> - Experimental software - expect bugs and breaking changes
> - While this tool is designed to be non-destructive (it only creates symlinks and copies files), **use at your own risk**
> - No warranty is provided - always review changes before committing

## Features

- **Declarative Configuration** - Define skills in `skillset.yaml`
- **Lock File Management** - Reproducible installs with `skillset.lock`
- **Multi-Scope Support** - Global (`~/.claude/skills/`) and project (`.claude/skills/`) scopes
- **Multiple Sources** - Install from local filesystem or GitHub
- **Validation** - Verify SKILL.md structure and metadata
- **Symlink Support** - Local skills are symlinked for easy development

## Quick Start

### Installation

```bash
# Using pipx (recommended)
pipx install git+https://github.com/hawkymisc/asma.git

# Or using pip
pip install git+https://github.com/hawkymisc/asma.git
```

### Basic Usage

```bash
# 1. Initialize skillset.yaml
asma init

# 2. Edit skillset.yaml to add your skills

# 3. Install skills
asma install

# 4. Verify installation
asma list
asma check
```

## Configuration

Create a `skillset.yaml` in your project root:

```yaml
# Global skills (installed to ~/.claude/skills/)
global:
  - name: my-skill
    source: local:~/my-skills/my-skill

  - name: github-skill
    source: github:owner/repo
    version: v1.0.0

# Project skills (installed to .claude/skills/)
project:
  - name: team-skill
    source: local:./skills/team-skill
```

### Source Types

**Local filesystem:**
```yaml
- name: my-skill
  source: local:~/skills/my-skill      # Absolute path
  source: local:./skills/my-skill      # Relative path
```

**GitHub:**
```yaml
- name: skill-name
  source: github:owner/repo            # Repository root
  source: github:owner/repo/subdir     # Subdirectory
  version: v1.0.0                      # Tag or "latest"
  ref: main                            # Branch or commit SHA
```

Set `GITHUB_TOKEN` environment variable for private repositories.

## Commands

| Command | Description |
|---------|-------------|
| `asma init` | Create skillset.yaml template |
| `asma add` | Add a skill from source to skillset.yaml |
| `asma install` | Install skills from skillset.yaml |
| `asma list` | List installed skills |
| `asma check` | Verify installed skills exist |
| `asma context` | Show skill metadata (SKILL.md frontmatter) |
| `asma version` | Show asma version |

### Command Options

**asma add**
```bash
asma add github:owner/repo/path   # Add skill from GitHub
asma add local:~/my-skills/skill  # Add skill from local path
asma add github:owner/repo --global       # Add to global scope
asma add github:owner/repo --name custom  # Use custom name
asma add github:owner/repo --force        # Overwrite existing
```

**asma install**
```bash
asma install                      # Install all skills
asma install --scope global       # Install only global skills
asma install --force              # Force reinstall
asma install --file custom.yaml   # Use alternative config file
```

**asma list**
```bash
asma list                    # List all installed skills
asma list --scope project    # Filter by scope
```

**asma check**
```bash
asma check                   # Check all skills
asma check --checksum        # Also verify checksums
asma check --quiet           # Only show errors
```

**asma context**
```bash
asma context                       # Show all skill metadata
asma context my-skill              # Show specific skill
asma context --format yaml         # Output as YAML
asma context --format json         # Output as JSON
```

## Skill Structure

A valid skill must contain `SKILL.md` with frontmatter:

```markdown
---
name: my-skill
description: A helpful skill for doing X
---

# My Skill

Instructions for Claude Code...
```

Requirements:
- `name`: lowercase letters, numbers, and hyphens only
- `description`: non-empty string

## Lock File

`skillset.lock` is auto-generated when you run `asma install`. It records exact versions and checksums for reproducible installations.

**Best Practices:**
- Commit `skillset.lock` to version control
- Run `asma install` after pulling changes
- Don't edit manually

## Development

```bash
# Clone and install in development mode
git clone https://github.com/hawkymisc/asma.git
cd asma
pip install -e ".[dev]"

# Run tests
pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

MIT
