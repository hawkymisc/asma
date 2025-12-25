# asma - Agent Skills Manager

A declarative package manager for Claude Agent Skills, inspired by vim-plug and Vundle.

## Status

**MVP Core Features Complete** ✅
- ✅ `asma init` - Initialize skillset.yaml
- ✅ `asma install` - Install skills from skillset
- ✅ `asma version` - Show version
- ✅ Local filesystem sources (`local:`)
- ✅ SKILL.md validation
- ✅ Global and project scopes
- 🚧 GitHub sources (`github:`) - Coming soon
- 🚧 Lock file management - Coming soon

## Features

- 📦 **Declarative Configuration**: Define skills in `skillset.yaml`
- 🌍 **Multi-Scope Support**: Global (`~/.claude/skills/`) and project (`.claude/skills/`) scopes
- ⚡ **Simple CLI**: Intuitive commands for skill management
- ✅ **Validation**: Verify SKILL.md structure and metadata
- 🔗 **Symlink Support**: Local skills are symlinked for easy development
- 🎨 **Colored Output**: Clear progress indicators and error messages

## Quick Start

### 1. Installation

#### Option A: pipx (Recommended)

```bash
# Install pipx if not already installed
pip install pipx
pipx ensurepath

# Install asma globally
pipx install git+https://github.com/hawkymisc/asma.git

# Or from local clone
git clone https://github.com/hawkymisc/asma.git
cd asma
pipx install .
```

#### Option B: pip (Development)

```bash
# Clone the repository
git clone https://github.com/hawkymisc/asma.git
cd asma

# Install with pip (editable mode for development)
pip install -e .
```

#### Uninstall

```bash
# If installed with pipx
pipx uninstall asma

# If installed with pip
pip uninstall asma
```

### 2. Initialize Project

```bash
# Create skillset.yaml template
asma init
```

### 3. Define Your Skills

Edit `skillset.yaml`:

```yaml
# Global skills (installed to ~/.claude/skills/)
global:
  - name: my-skill
    source: local:~/my-skills/my-skill

# Project skills (installed to .claude/skills/)
project:
  - name: team-skill
    source: local:./skills/team-skill
```

### 4. Install Skills

```bash
# Install all skills
asma install

# Install only global skills
asma install --scope global

# Force reinstall
asma install --force
```

## skillset.yaml Format

```yaml
# Optional global configuration
config:
  auto_update: false
  parallel_downloads: 4
  github_token_env: GITHUB_TOKEN

# Global skills (personal, across all projects)
global:
  - name: document-analyzer
    source: local:~/skills/document-analyzer
    # Optional fields:
    # version: v1.0.0         # For git sources
    # ref: main               # For git sources
    # enabled: true           # Skip if false
    # alias: custom-name      # Install under different name

# Project skills (team-shared, version-controlled)
project:
  - name: test-runner
    source: local:./local-skills/test-runner
```

## Commands

### `asma init`
Initialize a new skillset.yaml file with template.

**Options**:
- `--force` - Overwrite existing file

**Example**:
```bash
asma init
asma init --force
```

### `asma install`
Install skills from skillset.yaml.

**Options**:
- `--file <path>` - Use alternative skillset file (default: `./skillset.yaml`)
- `--scope <global|project>` - Install only specified scope
- `--force` - Reinstall even if already installed

**Examples**:
```bash
# Install all skills
asma install

# Install only global skills
asma install --scope global

# Use custom file
asma install --file custom-skills.yaml

# Force reinstall
asma install --force
```

### `asma version`
Show asma version.

**Example**:
```bash
asma version
# Output: asma version 0.1.0
```

## Skill Structure

A valid skill must contain `SKILL.md` with frontmatter:

```markdown
---
name: my-skill
description: A helpful skill for doing X
---

# My Skill

## Instructions
Detailed instructions for Claude...

## Examples
- Example 1
- Example 2

## Guidelines
- Guideline 1
- Guideline 2
```

**Requirements**:
- `name`: lowercase letters, numbers, and hyphens only (e.g., `my-skill-123`)
- `description`: non-empty string describing the skill's purpose

## Development

### Setup

```bash
# Install with dev dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=asma

# Run specific test file
pytest tests/test_validator.py -v
```

### Test Coverage

**Current**: 43 tests, 87% coverage

| Module | Coverage | Tests |
|--------|----------|-------|
| validator | 89% | 6 |
| models/skill | 88% | 7 |
| core/config | 96% | 9 |
| cli/main | 86% | 9 |
| sources/local | 91% | 6 |
| core/installer | 94% | 6 |

### TDD Approach

This project follows Kent Beck's Test-Driven Development methodology:
1. 🔴 **RED**: Write failing test first
2. 🟢 **GREEN**: Implement minimum code to pass
3. 🔵 **REFACTOR**: Clean up implementation

## Documentation

- [SPEC.md](SPEC.md) - Complete technical specification (MVP requirements, commands, formats)
- [DESIGN.md](DESIGN.md) - Detailed design document (architecture, algorithms, data models)

## Roadmap

### ✅ MVP (Complete)
- [x] Project structure and build system
- [x] SKILL.md validator
- [x] Skill and Skillset models
- [x] Local source handler
- [x] Skill installer
- [x] CLI commands (init, version, install)

### 🚧 Next Steps
- [ ] GitHub source handler (`github:user/repo`)
- [ ] Lock file management (`skillset.lock`)
- [ ] `asma list` command
- [ ] `asma update` command
- [ ] `asma uninstall` command
- [ ] Git source handler (`git:https://...`)

### 🔮 Future
- [ ] Dependency resolution
- [ ] Central skill registry
- [ ] Skill search and discovery
- [ ] Parallel installation
- [ ] Installation hooks

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Write tests (TDD approach)
4. Ensure all tests pass (`pytest`)
5. Submit a pull request

## License

MIT
