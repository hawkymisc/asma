# asma - Agent Skills Manager

A declarative package manager for Claude Agent Skills, inspired by vim-plug and Vundle.

## Features

- 📦 **Declarative Configuration**: Define skills in `skillset.yaml`
- 🔒 **Reproducible Installs**: Lock file ensures consistent installations
- 🌍 **Multi-Scope Support**: Global (`~/.claude/skills/`) and project (`.claude/skills/`) scopes
- ⚡ **Simple CLI**: Intuitive commands for install/update/list operations
- ✅ **Validation**: Verify SKILL.md structure and metadata

## Quick Start

```bash
# Initialize a new skillset
asma init

# Edit skillset.yaml to add your skills
# Then install
asma install

# List installed skills
asma list
```

## Installation

```bash
pip install -e .
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=asma
```

## Documentation

- [SPEC.md](SPEC.md) - Technical specification
- [DESIGN.md](DESIGN.md) - Detailed design document

## License

MIT
