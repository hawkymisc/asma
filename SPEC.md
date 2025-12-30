# Agent Skills Manager (asma) - Technical Specification

**Version**: 1.0.0-MVP
**Date**: 2025-12-20
**Status**: Draft

---

## 1. Overview

### 1.1 Purpose
Agent Skills Manager (asma) is a declarative package manager for Claude Agent Skills, inspired by vim-plug and Vundle. It enables teams to version-control skill dependencies and reproduce skill environments across machines.

### 1.2 Goals
- **Declarative Configuration**: Define skills in `skillset.yaml`
- **Reproducibility**: Lock file ensures consistent installations
- **Multi-Scope Support**: Global (`~/.claude/skills/`) and project (`.claude/skills/`) scopes
- **Simple CLI**: Intuitive commands for install/update/list operations
- **Validation**: Verify SKILL.md structure and metadata

### 1.3 Non-Goals (Post-MVP)
- Dependency resolution between skills
- Central skill registry/marketplace
- Skill search and discovery
- Automatic conflict resolution
- Plugin hooks (pre/post install)

---

## 2. Core Concepts

### 2.1 Skill Sources
Skills can be installed from:

1. **GitHub Repositories**
   - Format: `github:user/repo/path/to/skill`
   - Supports tags, branches, commits

2. **Local Filesystem**
   - Format: `local:/path/to/skill`
   - Creates symlinks to avoid duplication

3. **Git URLs** (Optional MVP)
   - Format: `git:https://example.com/skills.git/path`

### 2.2 Installation Scopes

| Scope | Path | Use Case |
|-------|------|----------|
| **Global** | `~/.claude/skills/` | Personal skills across all projects |
| **Project** | `.claude/skills/` | Team-shared, version-controlled skills |

### 2.3 Skill Structure Requirements

Valid skills must contain:
```
skill-name/
├── SKILL.md           # Required: metadata + instructions
├── scripts/           # Optional: executables
├── references/        # Optional: docs
└── assets/            # Optional: templates
```

**SKILL.md Requirements**:
- YAML frontmatter with `name` and `description`
- `name`: lowercase, numbers, hyphens only (max 64 chars)
- `description`: explains purpose and use cases

---

## 3. Configuration File Format

### 3.1 skillset.yaml

**Location**: Project root or specified via `--file` flag

**Basic Structure**:
```yaml
# Global skills (installed to ~/.claude/skills/)
global:
  - name: document-analyzer
    source: github:anthropics/skills/document-analyzer
    version: v1.0.0

  - name: python-expert
    source: github:travisvn/awesome-claude-skills/python-expert
    ref: main

# Project skills (installed to .claude/skills/)
project:
  - name: api-tester
    source: local:~/company/skills/api-tester

  - name: test-runner
    source: github:anthropics/skills/test-runner
    version: v2.1.0
```

### 3.2 Detailed Field Definitions

#### Skill Entry Fields

| Field | Type | Required | Description | Examples |
|-------|------|----------|-------------|----------|
| `name` | string | **Yes** | Unique identifier for the skill | `document-analyzer` |
| `source` | string | **Yes** | Source location (see formats below) | `github:user/repo/path` |
| `version` | string | No | Git tag for versioning | `v1.0.0`, `1.2.3` |
| `ref` | string | No | Git branch or commit SHA | `main`, `develop`, `abc123` |
| `enabled` | boolean | No | Skip installation if `false` (default: `true`) | `true`, `false` |
| `alias` | string | No | Install under different name | `my-custom-name` |

**Source Formats**:

```yaml
# GitHub repository
source: github:user/repo                      # Root of repo
source: github:user/repo/subdir/skill-name    # Nested path

# Local filesystem
source: local:/absolute/path/to/skill
source: local:~/relative/to/home/skill

# Git URL (future)
source: git:https://gitlab.com/user/repo.git/path
```

**Version Resolution Priority**:
1. `version` (git tag) - highest priority
2. `ref` (branch/commit) - if version not specified
3. Default branch (usually `main`) - if neither specified

#### Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `global` | array | No | List of global-scope skills |
| `project` | array | No | List of project-scope skills |
| `config` | object | No | Global configuration (see below) |

**Config Object** (Optional):
```yaml
config:
  auto_update: false          # Auto-update on `asma install`
  verify_signatures: false    # GPG signature verification (future)
  parallel_downloads: 4       # Concurrent download limit
  github_token_env: GITHUB_TOKEN  # Environment variable for auth
```

### 3.3 skillset.lock

**Purpose**: Lock installed versions for reproducibility

**Auto-generated** - do not edit manually

**Format**:
```yaml
version: 1
generated_at: "2025-12-20T14:30:00Z"
skills:
  global:
    document-analyzer:
      source: github:anthropics/skills/document-analyzer
      resolved_version: v1.0.0
      resolved_commit: abc123def456
      installed_at: "2025-12-20T14:25:00Z"
      checksum: sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08

  project:
    api-tester:
      source: local:/home/user/company/skills/api-tester
      resolved_path: /home/user/company/skills/api-tester
      installed_at: "2025-12-20T14:25:05Z"
      symlink: true
```

**Lock File Fields**:
- `resolved_version`: Actual tag/version installed
- `resolved_commit`: Git commit SHA for reproducibility
- `checksum`: SHA256 of SKILL.md for integrity verification
- `symlink`: Boolean indicating if skill is symlinked (local sources)

---

## 4. Command Line Interface

### 4.1 Command Overview

```bash
asma <command> [options] [arguments]
```

### 4.2 Command Specifications

#### `asma init`
**Purpose**: Initialize a new skillset.yaml file

**Usage**:
```bash
asma init [--global]
```

**Options**:
- `--global`: Create global skillset at `~/.asma/skillset.yaml`

**Behavior**:
- Creates `skillset.yaml` template in current directory
- Fails if file already exists (use `--force` to overwrite)
- Template includes commented examples

**Example Output**:
```
✓ Created skillset.yaml
  Edit this file to add your skills, then run: asma install
```

---

#### `asma install`
**Purpose**: Install skills from skillset.yaml

**Usage**:
```bash
asma install [skill-name] [options]
```

**Arguments**:
- `skill-name`: Optional. Install specific skill instead of all

**Options**:
- `--file <path>`: Use alternative skillset file (default: `./skillset.yaml`)
- `--scope <global|project>`: Install only global or project skills
- `--dry-run`: Show what would be installed without installing
- `--force`: Reinstall even if already installed
- `--no-lock`: Skip updating skillset.lock

**Behavior**:
1. Parse skillset.yaml
2. Validate skill definitions
3. Check existing installations
4. Download/copy skills to appropriate directories
5. Validate SKILL.md structure
6. Update skillset.lock
7. Display installation summary

**Example**:
```bash
# Install all skills
asma install

# Install specific skill
asma install document-analyzer

# Dry run
asma install --dry-run

# Install only global skills
asma install --scope global
```

**Output**:
```
Installing skills...
✓ document-analyzer (global) - v1.0.0
✓ python-expert (global) - main@abc123
✓ api-tester (project) - symlink from ~/company/skills
✗ test-runner (project) - validation failed: missing description

Installed: 3/4 skills
Failed: 1 skill (see errors above)
```

---

#### `asma uninstall`
**Purpose**: Remove installed skills

**Usage**:
```bash
asma uninstall <skill-name> [options]
```

**Arguments**:
- `skill-name`: Required. Name of skill to uninstall

**Options**:
- `--scope <global|project>`: Specify which scope to remove from
- `--keep-in-skillset`: Remove files but keep in skillset.yaml
- `--purge`: Remove all data including caches

**Behavior**:
1. Locate skill in specified scope
2. Remove directory (or symlink for local sources)
3. Update skillset.lock
4. Optionally remove from skillset.yaml

**Example**:
```bash
# Uninstall from both scopes
asma uninstall document-analyzer

# Uninstall only from global
asma uninstall document-analyzer --scope global

# Keep in skillset.yaml for later reinstall
asma uninstall api-tester --keep-in-skillset
```

---

#### `asma update`
**Purpose**: Update skills to latest versions

**Usage**:
```bash
asma update [skill-name] [options]
```

**Arguments**:
- `skill-name`: Optional. Update specific skill instead of all

**Options**:
- `--scope <global|project>`: Update only specified scope
- `--dry-run`: Show available updates without applying
- `--major`: Allow major version updates (breaking changes)

**Behavior**:
1. Check current versions from skillset.lock
2. Fetch latest versions from sources
3. Compare and identify updates
4. Download and replace skill directories
5. Re-validate SKILL.md
6. Update skillset.lock

**Version Update Rules**:
- If `version: v1.0.0` specified → update to latest patch (v1.0.x)
- If `ref: main` specified → update to latest commit on main
- If `version` starts with `^` → allow minor updates (^1.0.0 → 1.x.x)
- Use `--major` to update across major versions

**Example**:
```bash
# Update all skills
asma update

# Check for updates without applying
asma update --dry-run

# Update specific skill
asma update document-analyzer
```

**Output**:
```
Checking for updates...
✓ document-analyzer: v1.0.0 → v1.0.2
✓ python-expert: main@abc123 → main@def456
- api-tester: up to date (local)
! test-runner: v2.1.0 → v3.0.0 (major, use --major to update)

Updated: 2 skills
```

---

#### `asma list`
**Purpose**: List installed skills

**Usage**:
```bash
asma list [options]
```

**Options**:
- `--scope <global|project>`: Show only specified scope
- `--format <table|json|yaml>`: Output format (default: table)
- `--verbose`: Show detailed information (paths, commits, etc.)

**Behavior**:
- Read skillset.lock
- Display installed skills with metadata
- Group by scope

**Example**:
```bash
# List all skills
asma list

# List only global skills
asma list --scope global

# JSON output for scripting
asma list --format json
```

**Output**:
```
Global Skills (~/.claude/skills/):
  document-analyzer  v1.0.0    anthropics/skills
  python-expert      main      travisvn/awesome-claude-skills

Project Skills (.claude/skills/):
  api-tester         local     ~/company/skills (symlink)
  test-runner        v2.1.0    anthropics/skills

Total: 4 skills (3 global, 1 project)
```

---

#### `asma validate`
**Purpose**: Validate skillset.yaml and installed skills

**Usage**:
```bash
asma validate [options]
```

**Options**:
- `--file <path>`: Validate specific skillset file
- `--strict`: Enable strict validation (fail on warnings)

**Behavior**:
1. Parse skillset.yaml syntax
2. Validate field types and formats
3. Check for duplicate skill names
4. Validate installed SKILL.md files
5. Verify frontmatter requirements

**Validation Checks**:
- ✓ YAML syntax valid
- ✓ Required fields present (name, source)
- ✓ Source format correct
- ✓ SKILL.md exists
- ✓ SKILL.md has valid frontmatter
- ✓ `name` field matches pattern `^[a-z0-9-]+$`
- ✓ `description` field present and non-empty

**Example**:
```bash
asma validate
```

**Output**:
```
Validating skillset.yaml...
✓ Syntax valid
✓ 4 skills defined
✓ No duplicate names

Validating installed skills...
✓ document-analyzer: valid
✓ python-expert: valid
✗ api-tester: SKILL.md missing 'description' field
✓ test-runner: valid

Validation: 3/4 passed
```

---

#### `asma verify`
**Purpose**: Verify that installed skills actually exist on the filesystem

**Usage**:
```bash
asma verify [options]
```

**Options**:
- `--scope <global|project>`: Verify only specified scope
- `--checksum`: Also verify SKILL.md checksum matches lock file
- `--quiet`: Only show errors (for CI/scripts)

**Behavior**:
1. Load skillset.lock
2. For each skill entry:
   - Check if install directory exists
   - For symlinks: verify target exists
   - With `--checksum`: verify SKILL.md SHA256 matches recorded checksum
3. Display verification summary
4. Exit with non-zero code if any skills are missing/broken

**Exit Codes**:
- `0`: All skills verified successfully
- `1`: One or more skills failed verification
- `2`: skillset.lock not found

**Example**:
```bash
# Verify all skills
asma verify

# Verify with checksum validation
asma verify --checksum

# CI-friendly quiet mode
asma verify --quiet || echo "Skills missing!"

# Verify only global scope
asma verify --scope global
```

**Output**:
```
Verifying installed skills...
✓ document-analyzer (global) - OK
✓ python-expert (global) - OK
✗ api-tester (project) - not found
✗ test-runner (project) - symlink broken

Verified: 2/4 skills
Missing: 2 skills (run 'asma install' to fix)
```

**With --checksum**:
```
Verifying installed skills (with checksum)...
✓ document-analyzer (global) - OK
! python-expert (global) - checksum mismatch
✗ api-tester (project) - not found

Verified: 1/4 skills
Modified: 1 skill (reinstall with 'asma install --force')
Missing: 1 skill (run 'asma install' to fix)
```

---

#### `asma context`
**Purpose**: Display context (SKILL.md frontmatter) of installed skills

**Usage**:
```bash
asma context [skill-name] [options]
```

**Arguments**:
- `skill-name`: Optional. Show context for specific skill only

**Options**:
- `--scope <global|project>`: Filter by scope
- `--format <text|yaml|json>`: Output format (default: text)

**Behavior**:
1. Load skillset.lock
2. For each installed skill:
   - Read SKILL.md from installed location
   - Parse YAML frontmatter
   - Collect all metadata fields
3. Display in specified format

**Example**:
```bash
# Show all skill contexts
asma context

# Show specific skill
asma context document-analyzer

# JSON output for scripting
asma context --format json

# YAML output
asma context --format yaml

# Only project skills
asma context --scope project
```

**Output (text format)**:
```
Installed Skills Context:

Global Skills:
  document-analyzer:
    name: document-analyzer
    description: Analyzes documents for key information and summaries
    author: Anthropic
    version: 1.0.0

  python-expert:
    name: python-expert
    description: Expert Python programmer with best practices

Project Skills:
  test-runner:
    name: test-runner
    description: Runs tests and reports results
    requires: pytest
```

**Output (yaml format)**:
```yaml
global:
  document-analyzer:
    name: document-analyzer
    description: Analyzes documents for key information and summaries
    author: Anthropic
    version: 1.0.0
  python-expert:
    name: python-expert
    description: Expert Python programmer with best practices
project:
  test-runner:
    name: test-runner
    description: Runs tests and reports results
    requires: pytest
```

**Output (json format)**:
```json
{
  "global": {
    "document-analyzer": {
      "name": "document-analyzer",
      "description": "Analyzes documents for key information and summaries",
      "author": "Anthropic",
      "version": "1.0.0"
    }
  },
  "project": {
    "test-runner": {
      "name": "test-runner",
      "description": "Runs tests and reports results"
    }
  }
}
```

---

#### `asma info`
**Purpose**: Show detailed information about a skill

**Usage**:
```bash
asma info <skill-name>
```

**Arguments**:
- `skill-name`: Required. Name of skill to inspect

**Behavior**:
- Display SKILL.md metadata
- Show installation details
- List included files (scripts/, references/, assets/)
- Display source and version info

**Example**:
```bash
asma info document-analyzer
```

**Output**:
```
Skill: document-analyzer
Description: Analyzes documents for key information and summaries
Source: github:anthropics/skills/document-analyzer
Version: v1.0.0 (commit: abc123def)
Installed: 2025-12-20 14:25:00 (global)
Location: ~/.claude/skills/document-analyzer

Structure:
├── SKILL.md (2.3 KB)
├── scripts/
│   └── extract.py (1.1 KB)
└── references/
    └── examples.md (0.8 KB)

Last updated: 2025-12-20 14:25:00
```

---

#### `asma clean`
**Purpose**: Remove unused skills and caches

**Usage**:
```bash
asma clean [options]
```

**Options**:
- `--cache`: Clean download cache only
- `--orphaned`: Remove skills not in skillset.yaml
- `--all`: Remove cache and orphaned skills
- `--dry-run`: Show what would be removed

**Behavior**:
- Identify skills in `.claude/skills/` not listed in skillset.yaml
- Remove temporary download files
- Clean up broken symlinks

**Example**:
```bash
# Remove orphaned skills
asma clean --orphaned

# Clean cache
asma clean --cache

# Preview cleanup
asma clean --all --dry-run
```

---

#### `asma doctor`
**Purpose**: Diagnose installation issues

**Usage**:
```bash
asma doctor
```

**Behavior**:
1. Check directory permissions
2. Verify Git installation
3. Test GitHub API connectivity
4. Validate skillset.yaml and skillset.lock
5. Check for conflicts

**Example Output**:
```
Running diagnostics...
✓ ~/.claude/skills/ writable
✓ .claude/skills/ writable
✓ Git installed (version 2.39.0)
✓ GitHub API accessible
✓ skillset.yaml valid
! skillset.lock out of sync (run: asma install)
✗ Python not found (required for some skills)

Status: 4 OK, 1 warning, 1 error
```

---

#### `asma version`
**Purpose**: Show asma version

**Usage**:
```bash
asma version
```

**Output**:
```
asma version 1.0.0
```

---

### 4.3 Global Options

Available for all commands:

| Option | Description |
|--------|-------------|
| `--help`, `-h` | Show help message |
| `--version`, `-v` | Show version |
| `--quiet`, `-q` | Suppress output |
| `--verbose` | Show detailed logs |
| `--no-color` | Disable colored output |

---

## 5. Validation Rules

### 5.1 SKILL.md Validation

**Required**:
- File must exist
- Must contain YAML frontmatter (between `---` delimiters)
- Frontmatter must include:
  - `name`: matches `^[a-z0-9-]{1,64}$`
  - `description`: non-empty string

**Optional but Recommended**:
- Markdown content with sections (Instructions, Examples, Guidelines)
- File size under 5000 words (~25KB)

### 5.2 skillset.yaml Validation

**Schema Enforcement**:
```yaml
# JSON Schema (simplified)
{
  "type": "object",
  "properties": {
    "global": {
      "type": "array",
      "items": { "$ref": "#/definitions/skill" }
    },
    "project": {
      "type": "array",
      "items": { "$ref": "#/definitions/skill" }
    },
    "config": {
      "type": "object",
      "properties": {
        "auto_update": { "type": "boolean" },
        "parallel_downloads": { "type": "integer", "minimum": 1, "maximum": 10 }
      }
    }
  },
  "definitions": {
    "skill": {
      "type": "object",
      "required": ["name", "source"],
      "properties": {
        "name": {
          "type": "string",
          "pattern": "^[a-z0-9-]+$"
        },
        "source": {
          "type": "string",
          "pattern": "^(github:|local:|git:)"
        },
        "version": { "type": "string" },
        "ref": { "type": "string" },
        "enabled": { "type": "boolean" },
        "alias": { "type": "string" }
      }
    }
  }
}
```

### 5.3 Error Handling

**Fail Fast**:
- Invalid YAML syntax → abort immediately
- Missing required fields → abort before installation
- Network errors → retry 3 times with exponential backoff

**Graceful Degradation**:
- Single skill validation failure → skip skill, continue with others
- Partial installation → update lock file for successful skills only

---

## 6. Architecture

### 6.1 Technology Stack

**Language**: Python 3.8+

**Core Libraries**:
- `click`: CLI framework
- `pyyaml`: YAML parsing
- `requests`: HTTP client for GitHub API
- `gitpython`: Git operations
- `jsonschema`: Schema validation
- `rich`: Terminal formatting

**Optional**:
- `pytest`: Testing framework
- `mypy`: Type checking

### 6.2 Module Structure

```
asma/
├── __init__.py
├── __main__.py         # Entry point
├── cli/
│   ├── __init__.py
│   ├── commands/       # Command implementations
│   │   ├── install.py
│   │   ├── uninstall.py
│   │   ├── update.py
│   │   ├── list.py
│   │   └── ...
│   └── utils.py        # CLI helpers
├── core/
│   ├── __init__.py
│   ├── config.py       # skillset.yaml parsing
│   ├── installer.py    # Installation logic
│   ├── validator.py    # SKILL.md validation
│   ├── lock.py         # skillset.lock management
│   └── sources/        # Source handlers
│       ├── github.py
│       ├── local.py
│       └── base.py
├── models/
│   ├── __init__.py
│   ├── skill.py        # Skill data models
│   └── skillset.py     # Skillset config models
└── utils/
    ├── __init__.py
    ├── git.py          # Git utilities
    ├── filesystem.py   # File operations
    └── logger.py       # Logging
```

### 6.3 Data Flow

```
User Command
    ↓
CLI Parser (click)
    ↓
Command Handler
    ↓
Config Parser → skillset.yaml
    ↓
Validator → Check definitions
    ↓
Source Handler → Download/Copy
    ↓
Installer → Place in ~/.claude/skills/
    ↓
Lock Manager → Update skillset.lock
    ↓
Output Formatter → Display results
```

---

## 7. Example Workflows

### 7.1 New Project Setup

```bash
# Initialize project
mkdir my-project && cd my-project
git init

# Create skillset
asma init
```

Edit `skillset.yaml`:
```yaml
project:
  - name: test-runner
    source: github:anthropics/skills/test-runner
    version: v2.1.0
```

```bash
# Install skills
asma install

# Commit to version control
git add skillset.yaml skillset.lock .claude/
git commit -m "Add Claude skills configuration"
```

### 7.2 Team Collaboration

**Developer A**:
```bash
# Add new skill
vim skillset.yaml  # Add api-tester
asma install api-tester
git add skillset.yaml skillset.lock .claude/
git commit -m "Add API testing skill"
git push
```

**Developer B**:
```bash
# Pull changes
git pull

# Sync skills
asma install

# Skills now match Developer A's environment
```

### 7.3 Global Skills Management

```bash
# Add personal productivity skills globally
vim ~/.asma/skillset.yaml
```

```yaml
global:
  - name: code-reviewer
    source: github:travisvn/awesome-claude-skills/code-reviewer
    ref: main
```

```bash
asma install --file ~/.asma/skillset.yaml --scope global
```

---

## 8. Future Enhancements (Post-MVP)

### 8.1 Advanced Features
- **Skill Profiles**: Switch between skill sets (`asma profile use work`)
- **Dependency Resolution**: Skills can declare dependencies on other skills
- **Hooks**: Pre/post install scripts
- **Skill Templates**: `asma new <skill-name>` to scaffold new skills
- **Private Registries**: Support private GitHub repos with auth

### 8.2 Integration
- **CI/CD**: GitHub Actions for validating skillset.yaml
- **IDE Extensions**: VSCode plugin for managing skills
- **Web UI**: Browser-based skill browser

### 8.3 Security
- **GPG Signature Verification**: Verify skill authenticity
- **Checksums**: Verify integrity of downloaded skills
- **Sandboxing**: Isolate skill scripts during execution

---

## 9. Success Metrics

### 9.1 MVP Acceptance Criteria
- ✅ Install skills from GitHub and local sources
- ✅ Manage global and project scopes independently
- ✅ Generate and respect skillset.lock for reproducibility
- ✅ Validate SKILL.md structure
- ✅ Support all core commands (install, uninstall, update, list)
- ✅ Handle errors gracefully with helpful messages

### 9.2 Performance Targets
- Install 10 skills in < 30 seconds (network dependent)
- Validate skillset.yaml in < 1 second
- List command completes in < 100ms

---

## 10. Open Questions

1. **Namespace Conflicts**: How to handle same skill name in global and project scopes?
   - Proposed: Project scope takes precedence

2. **Skill Updates**: Should `asma install` auto-update existing skills?
   - Proposed: No, require explicit `asma update`

3. **Lock File**: Should skillset.lock be committed to git?
   - Proposed: Yes, for reproducibility (like package-lock.json)

4. **Symlink vs Copy**: For local sources, always symlink?
   - Proposed: Yes, avoid duplication and ease development

---

## 11. References

- [Claude Agent Skills Documentation](https://code.claude.com/docs/en/skills)
- [anthropics/skills Repository](https://github.com/anthropics/skills)
- [Vim-Plug Plugin Manager](https://github.com/junegunn/vim-plug)
- [NPM package.json Specification](https://docs.npmjs.com/cli/v10/configuring-npm/package-json)
