# Agent Skills Manager - Detailed Design Document

**Version**: 1.0.0-MVP
**Date**: 2025-12-20

---

## 1. Design Philosophy

### 1.1 Core Principles

1. **Convention over Configuration**: Sensible defaults, minimal config required
2. **Declarative First**: skillset.yaml is source of truth
3. **Fail Explicitly**: Clear error messages, never silent failures
4. **Idempotent Operations**: `asma install` can run multiple times safely
5. **Developer Experience**: Fast, predictable, helpful error messages

### 1.2 Design Constraints

- **No External Dependencies**: Only standard Python libraries where possible
- **Cross-Platform**: Linux, macOS, Windows support
- **Minimal Permissions**: Don't require sudo/admin
- **Offline-Friendly**: Work with cached data when network unavailable

---

## 2. skillset.yaml Deep Dive

### 2.1 Complete Schema Definition

```yaml
# Optional global configuration
config:
  # Auto-update skills on install (default: false)
  auto_update: false

  # Parallel download limit (default: 4, max: 10)
  parallel_downloads: 4

  # GitHub token environment variable (default: GITHUB_TOKEN)
  github_token_env: GITHUB_TOKEN

  # Cache directory (default: ~/.asma/cache)
  cache_dir: ~/.asma/cache

  # Strict validation mode (default: false)
  strict: false

# Global scope skills
global:
  # Minimal syntax (GitHub repo root)
  - name: simple-skill
    source: github:anthropics/skills

  # Specific subdirectory
  - name: document-analyzer
    source: github:anthropics/skills/document-analyzer
    version: v1.0.0

  # Branch reference
  - name: python-expert
    source: github:travisvn/awesome-claude-skills/python-expert
    ref: main

  # Commit SHA
  - name: beta-tester
    source: github:myorg/myskills/beta-skill
    ref: abc123def456

  # Semver constraints
  - name: api-helper
    source: github:company/skills/api-helper
    version: ^1.2.0  # Allow 1.x.x (minor/patch updates)

  - name: data-processor
    source: github:company/skills/data
    version: ~2.3.0  # Allow 2.3.x (patch updates only)

  # Local filesystem (absolute path)
  - name: custom-skill
    source: local:/home/user/my-skills/custom

  # Local filesystem (home directory)
  - name: personal-skill
    source: local:~/skills/personal-skill

  # Disabled skill (skip installation)
  - name: deprecated-skill
    source: github:old/repo
    enabled: false

  # Install with different name
  - name: skill-original-name
    source: github:user/repo/skill
    alias: my-custom-name  # Installed as ~/.claude/skills/my-custom-name

# Project scope skills
project:
  - name: test-runner
    source: github:anthropics/skills/test-runner
    version: v2.1.0

  # Private repository (requires GITHUB_TOKEN)
  - name: internal-tool
    source: github:company/private-skills/internal-tool
    version: latest  # Special: use latest release

  # Local path relative to project
  - name: team-skill
    source: local:./.skills-dev/team-skill  # For development
```

### 2.2 Source Format Specifications

#### GitHub Source Format

**Pattern**: `github:<owner>/<repo>[/<path>]`

**Examples**:
```yaml
# Repository root (searches for SKILL.md in root)
source: github:anthropics/skills

# Subdirectory
source: github:anthropics/skills/document-analyzer

# Nested path
source: github:user/monorepo/packages/skills/analyzer

# Organization repository
source: github:my-org/skill-collection/tools/debugger
```

**Resolution Logic**:
1. Parse owner, repo, optional path
2. Construct GitHub API URL: `https://api.github.com/repos/<owner>/<repo>`
3. If version specified: fetch tag via `/git/refs/tags/<version>`
4. If ref specified: fetch branch/commit via `/git/refs/heads/<ref>` or `/commits/<ref>`
5. Download tarball: `https://github.com/<owner>/<repo>/archive/<ref>.tar.gz`
6. Extract to temp directory
7. Navigate to `<path>` if specified
8. Validate SKILL.md exists
9. Copy to destination

**Authentication**:
- Read token from environment variable (default: `GITHUB_TOKEN`)
- Configurable via `config.github_token_env`
- Public repos work without token (rate limited to 60 req/hour)
- Private repos require token with `repo` scope

#### Local Source Format

**Pattern**: `local:<path>`

**Examples**:
```yaml
# Absolute path
source: local:/home/user/skills/custom-skill

# Home directory shorthand
source: local:~/skills/custom-skill

# Relative to skillset.yaml
source: local:./local-skills/dev-skill

# Relative parent directory
source: local:../shared-skills/common-skill
```

**Resolution Logic**:
1. Expand `~` to home directory
2. Resolve relative paths from skillset.yaml location
3. Verify path exists and is directory
4. Validate SKILL.md exists
5. Create symlink at destination → original path

**Symlink Behavior**:
- Local sources are **always symlinked** (not copied)
- Allows editing source and seeing changes immediately
- `skillset.lock` records `symlink: true`
- `asma uninstall` removes symlink, not source

#### Git URL Format (Future)

**Pattern**: `git:<url>[/<path>]`

**Examples**:
```yaml
source: git:https://gitlab.com/user/repo.git
source: git:ssh://git@bitbucket.org/team/skills.git/path/to/skill
```

---

## 3. Command Implementation Details

### 3.1 `asma install` Algorithm

```python
def install(skillset_path, skill_name=None, options):
    """
    Install skills from skillset.yaml

    Args:
        skillset_path: Path to skillset.yaml
        skill_name: Optional specific skill to install
        options: CLI options (dry_run, force, scope, etc.)
    """
    # 1. Load and validate configuration
    skillset = load_skillset(skillset_path)
    validate_skillset_schema(skillset)

    # 2. Load existing lock file
    lock = load_lock_file() or create_empty_lock()

    # 3. Filter skills by scope and name
    skills_to_install = filter_skills(
        skillset,
        scope=options.scope,
        name=skill_name
    )

    # 4. Check what's already installed
    for skill in skills_to_install:
        if is_installed(skill) and not options.force:
            if is_up_to_date(skill, lock):
                log(f"✓ {skill.name} already up to date")
                continue

    # 5. Resolve versions and download
    results = []
    with ThreadPoolExecutor(max_workers=config.parallel_downloads) as executor:
        futures = {
            executor.submit(install_skill, skill, options): skill
            for skill in skills_to_install
        }

        for future in as_completed(futures):
            skill = futures[future]
            try:
                result = future.result()
                results.append(result)
                update_lock_entry(lock, skill, result)
            except Exception as e:
                log_error(f"✗ {skill.name} - {e}")
                results.append({"skill": skill, "error": str(e)})

    # 6. Update lock file
    if not options.no_lock:
        save_lock_file(lock)

    # 7. Display summary
    display_summary(results)

    return results


def install_skill(skill, options):
    """Install single skill"""
    # Dry run: just simulate
    if options.dry_run:
        return {"skill": skill, "action": "would_install"}

    # Resolve source
    source_handler = get_source_handler(skill.source)
    resolved = source_handler.resolve(skill)

    # Download/copy to temp
    temp_path = source_handler.download(resolved)

    # Validate structure
    validate_skill_structure(temp_path)
    validate_skill_md(temp_path / "SKILL.md")

    # Determine destination
    if skill.scope == "global":
        dest = Path.home() / ".claude/skills" / (skill.alias or skill.name)
    else:
        dest = Path.cwd() / ".claude/skills" / (skill.alias or skill.name)

    # Install (copy or symlink)
    if source_handler.should_symlink():
        create_symlink(temp_path, dest)
    else:
        copy_directory(temp_path, dest)

    return {
        "skill": skill,
        "action": "installed",
        "version": resolved.version,
        "commit": resolved.commit,
        "path": dest
    }
```

### 3.2 Version Resolution Strategy

```python
def resolve_version(skill, source_handler):
    """
    Resolve version/ref to concrete commit SHA

    Priority:
    1. skill.version (git tag)
    2. skill.ref (branch or commit)
    3. Default branch (main/master)
    """
    if skill.version:
        if skill.version == "latest":
            # Fetch latest release from GitHub API
            return source_handler.get_latest_release()
        elif skill.version.startswith("^"):
            # Semver caret: ^1.2.0 allows >=1.2.0 <2.0.0
            constraint = skill.version[1:]
            return source_handler.resolve_semver(constraint, allow="minor")
        elif skill.version.startswith("~"):
            # Semver tilde: ~1.2.0 allows >=1.2.0 <1.3.0
            constraint = skill.version[1:]
            return source_handler.resolve_semver(constraint, allow="patch")
        else:
            # Exact version tag
            return source_handler.get_tag(skill.version)

    elif skill.ref:
        # Branch or commit SHA
        if len(skill.ref) == 40:  # SHA-1 hash
            return source_handler.get_commit(skill.ref)
        else:
            return source_handler.get_branch(skill.ref)

    else:
        # Default branch
        return source_handler.get_default_branch()
```

### 3.3 `asma update` Strategy

```python
def update(skillset_path, skill_name=None, options):
    """Update skills to latest versions"""

    # Load current lock file
    lock = load_lock_file()
    if not lock:
        error("No skills installed. Run 'asma install' first.")
        return

    # Determine which skills to check
    skills_to_check = lock.get_skills(name=skill_name, scope=options.scope)

    updates = []
    for skill in skills_to_check:
        # Get current version
        current = lock.get_entry(skill.name, skill.scope)

        # Fetch latest version based on constraint
        source_handler = get_source_handler(skill.source)
        latest = source_handler.get_latest_allowed_version(
            current_version=current.resolved_version,
            constraint=skill.version,
            allow_major=options.major
        )

        # Compare
        if latest.commit != current.resolved_commit:
            updates.append({
                "skill": skill,
                "current": current.resolved_version,
                "latest": latest.version,
                "breaking": is_major_version_change(current, latest)
            })

    # Dry run: just report
    if options.dry_run:
        display_available_updates(updates)
        return

    # Apply updates
    for update_info in updates:
        if update_info["breaking"] and not options.major:
            log(f"! {update_info['skill'].name} has breaking changes, skipping (use --major)")
            continue

        # Re-install with new version
        install_skill(update_info["skill"], force=True)

    # Update lock file
    save_lock_file(lock)
```

---

## 4. Data Models

### 4.1 Skill Model

```python
from dataclasses import dataclass
from typing import Optional, Literal

@dataclass
class Skill:
    """Represents a skill definition from skillset.yaml"""

    name: str
    source: str
    scope: Literal["global", "project"]

    version: Optional[str] = None
    ref: Optional[str] = None
    enabled: bool = True
    alias: Optional[str] = None

    def __post_init__(self):
        # Validate name format
        if not re.match(r'^[a-z0-9-]+$', self.name):
            raise ValueError(f"Invalid skill name: {self.name}")

        # Validate source format
        if not self.source.startswith(('github:', 'local:', 'git:')):
            raise ValueError(f"Invalid source format: {self.source}")

        # Validate version/ref mutual exclusivity
        if self.version and self.ref:
            raise ValueError(f"Cannot specify both version and ref for {self.name}")

    @property
    def install_name(self) -> str:
        """Name to use for installation directory"""
        return self.alias or self.name

    @property
    def install_path(self) -> Path:
        """Full path where skill will be installed"""
        if self.scope == "global":
            base = Path.home() / ".claude/skills"
        else:
            base = Path.cwd() / ".claude/skills"
        return base / self.install_name
```

### 4.2 LockEntry Model

```python
from datetime import datetime

@dataclass
class LockEntry:
    """Represents a locked skill version"""

    name: str
    scope: str
    source: str

    resolved_version: str  # Tag or "main@commit"
    resolved_commit: str   # Full SHA
    installed_at: datetime
    checksum: str          # SHA256 of SKILL.md

    # Optional fields
    symlink: bool = False
    resolved_path: Optional[str] = None  # For local sources

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "resolved_version": self.resolved_version,
            "resolved_commit": self.resolved_commit,
            "installed_at": self.installed_at.isoformat(),
            "checksum": self.checksum,
            "symlink": self.symlink,
            "resolved_path": self.resolved_path
        }

    @classmethod
    def from_dict(cls, name: str, scope: str, data: dict):
        return cls(
            name=name,
            scope=scope,
            source=data["source"],
            resolved_version=data["resolved_version"],
            resolved_commit=data["resolved_commit"],
            installed_at=datetime.fromisoformat(data["installed_at"]),
            checksum=data["checksum"],
            symlink=data.get("symlink", False),
            resolved_path=data.get("resolved_path")
        )
```

### 4.3 Skillset Model

```python
@dataclass
class SkillsetConfig:
    """Global configuration from skillset.yaml"""

    auto_update: bool = False
    parallel_downloads: int = 4
    github_token_env: str = "GITHUB_TOKEN"
    cache_dir: Path = Path.home() / ".asma/cache"
    strict: bool = False

    def __post_init__(self):
        if not 1 <= self.parallel_downloads <= 10:
            raise ValueError("parallel_downloads must be between 1 and 10")


@dataclass
class Skillset:
    """Complete skillset.yaml representation"""

    global_skills: list[Skill]
    project_skills: list[Skill]
    config: SkillsetConfig

    @classmethod
    def from_file(cls, path: Path) -> "Skillset":
        """Load and parse skillset.yaml"""
        with open(path) as f:
            data = yaml.safe_load(f)

        # Parse config
        config_data = data.get("config", {})
        config = SkillsetConfig(**config_data)

        # Parse global skills
        global_skills = [
            Skill(**skill, scope="global")
            for skill in data.get("global", [])
        ]

        # Parse project skills
        project_skills = [
            Skill(**skill, scope="project")
            for skill in data.get("project", [])
        ]

        return cls(
            global_skills=global_skills,
            project_skills=project_skills,
            config=config
        )

    def get_skill(self, name: str, scope: Optional[str] = None) -> Optional[Skill]:
        """Find skill by name and optional scope"""
        candidates = []

        if scope in (None, "global"):
            candidates.extend(self.global_skills)
        if scope in (None, "project"):
            candidates.extend(self.project_skills)

        for skill in candidates:
            if skill.name == name:
                return skill

        return None

    def all_skills(self) -> list[Skill]:
        """Get all skills (both scopes)"""
        return self.global_skills + self.project_skills
```

---

## 5. Source Handlers Architecture

### 5.1 Base Handler Interface

```python
from abc import ABC, abstractmethod

class SourceHandler(ABC):
    """Abstract base for skill source handlers"""

    @abstractmethod
    def resolve(self, skill: Skill) -> ResolvedSource:
        """
        Resolve skill source to downloadable URL/path

        Returns:
            ResolvedSource with version, commit, download_url
        """
        pass

    @abstractmethod
    def download(self, resolved: ResolvedSource) -> Path:
        """
        Download/copy skill to temporary directory

        Returns:
            Path to downloaded skill directory
        """
        pass

    @abstractmethod
    def should_symlink(self) -> bool:
        """Whether this source type should be symlinked"""
        pass

    @abstractmethod
    def get_latest_allowed_version(
        self,
        current_version: str,
        constraint: Optional[str],
        allow_major: bool
    ) -> ResolvedSource:
        """Get latest version respecting constraints"""
        pass


@dataclass
class ResolvedSource:
    """Resolved source information"""
    version: str
    commit: str
    download_url: Optional[str] = None
    local_path: Optional[Path] = None
```

### 5.2 GitHub Handler Implementation

```python
class GitHubSourceHandler(SourceHandler):
    """Handle github:owner/repo/path sources"""

    def __init__(self, config: SkillsetConfig):
        self.config = config
        self.token = os.getenv(config.github_token_env)
        self.session = requests.Session()
        if self.token:
            self.session.headers["Authorization"] = f"token {self.token}"

    def resolve(self, skill: Skill) -> ResolvedSource:
        # Parse source
        match = re.match(r'github:([^/]+)/([^/]+)(?:/(.+))?', skill.source)
        owner, repo, path = match.groups()

        # Resolve version
        if skill.version:
            ref_info = self._get_tag(owner, repo, skill.version)
        elif skill.ref:
            ref_info = self._get_ref(owner, repo, skill.ref)
        else:
            ref_info = self._get_default_branch(owner, repo)

        # Construct download URL
        download_url = f"https://github.com/{owner}/{repo}/archive/{ref_info['commit']}.tar.gz"

        return ResolvedSource(
            version=ref_info['version'],
            commit=ref_info['commit'],
            download_url=download_url,
            metadata={"owner": owner, "repo": repo, "path": path}
        )

    def download(self, resolved: ResolvedSource) -> Path:
        # Download tarball
        cache_path = self.config.cache_dir / f"{resolved.commit}.tar.gz"

        if not cache_path.exists():
            response = self.session.get(resolved.download_url, stream=True)
            response.raise_for_status()

            with open(cache_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

        # Extract
        extract_dir = self.config.cache_dir / f"extract-{resolved.commit}"
        with tarfile.open(cache_path) as tar:
            tar.extractall(extract_dir)

        # Navigate to skill path
        skill_dir = extract_dir / "repo-name"  # GitHub tarball root
        if resolved.metadata.get("path"):
            skill_dir = skill_dir / resolved.metadata["path"]

        return skill_dir

    def should_symlink(self) -> bool:
        return False  # GitHub sources are copied

    def _get_tag(self, owner: str, repo: str, tag: str) -> dict:
        """Fetch tag information"""
        url = f"https://api.github.com/repos/{owner}/{repo}/git/refs/tags/{tag}"
        response = self.session.get(url)
        response.raise_for_status()

        data = response.json()
        return {
            "version": tag,
            "commit": data["object"]["sha"]
        }
```

### 5.3 Local Handler Implementation

```python
class LocalSourceHandler(SourceHandler):
    """Handle local:path sources"""

    def resolve(self, skill: Skill) -> ResolvedSource:
        # Parse path
        path_str = skill.source.replace("local:", "")
        path = Path(path_str).expanduser().resolve()

        if not path.exists():
            raise FileNotFoundError(f"Local skill not found: {path}")

        if not path.is_dir():
            raise ValueError(f"Local skill path must be directory: {path}")

        # Calculate checksum of SKILL.md for version tracking
        skill_md = path / "SKILL.md"
        if not skill_md.exists():
            raise ValueError(f"SKILL.md not found in {path}")

        checksum = hashlib.sha256(skill_md.read_bytes()).hexdigest()

        return ResolvedSource(
            version=f"local@{checksum[:8]}",
            commit=checksum,
            local_path=path
        )

    def download(self, resolved: ResolvedSource) -> Path:
        # No download needed, return original path
        return resolved.local_path

    def should_symlink(self) -> bool:
        return True  # Local sources are symlinked

    def get_latest_allowed_version(self, *args, **kwargs) -> ResolvedSource:
        # Local sources don't have versions
        return self.resolve(kwargs.get("skill"))
```

---

## 6. Validation System

### 6.1 SKILL.md Validator

```python
class SkillValidator:
    """Validate SKILL.md structure and metadata"""

    @staticmethod
    def validate(skill_path: Path, strict: bool = False) -> ValidationResult:
        skill_md = skill_path / "SKILL.md"

        errors = []
        warnings = []

        # Check existence
        if not skill_md.exists():
            errors.append("SKILL.md not found")
            return ValidationResult(valid=False, errors=errors)

        # Parse frontmatter
        content = skill_md.read_text()
        frontmatter = SkillValidator._parse_frontmatter(content)

        if not frontmatter:
            errors.append("SKILL.md missing YAML frontmatter")
            return ValidationResult(valid=False, errors=errors)

        # Required fields
        if "name" not in frontmatter:
            errors.append("SKILL.md missing required field: name")
        elif not re.match(r'^[a-z0-9-]{1,64}$', frontmatter["name"]):
            errors.append(f"Invalid name format: {frontmatter['name']}")

        if "description" not in frontmatter:
            errors.append("SKILL.md missing required field: description")
        elif not frontmatter["description"].strip():
            errors.append("description field is empty")

        # Optional warnings
        body = SkillValidator._extract_body(content)
        word_count = len(body.split())

        if word_count > 5000:
            warnings.append(f"SKILL.md is very large ({word_count} words, recommend <5000)")

        if strict:
            # Additional strict checks
            if "instructions" not in body.lower():
                warnings.append("No 'Instructions' section found")

        valid = len(errors) == 0
        return ValidationResult(
            valid=valid,
            errors=errors,
            warnings=warnings,
            metadata=frontmatter
        )

    @staticmethod
    def _parse_frontmatter(content: str) -> Optional[dict]:
        """Extract YAML frontmatter between --- delimiters"""
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if not match:
            return None

        try:
            return yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            return None

    @staticmethod
    def _extract_body(content: str) -> str:
        """Get markdown content after frontmatter"""
        parts = re.split(r'^---\s*\n.*?\n---\s*\n', content, maxsplit=1, flags=re.DOTALL)
        return parts[-1] if len(parts) > 1 else content


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
```

---

## 7. Error Handling Strategy

### 7.1 Error Hierarchy

```python
class AsmaError(Exception):
    """Base exception for all asma errors"""
    pass

class ConfigError(AsmaError):
    """skillset.yaml parsing or validation error"""
    pass

class SourceError(AsmaError):
    """Error resolving or downloading source"""
    pass

class ValidationError(AsmaError):
    """SKILL.md validation failure"""
    pass

class InstallationError(AsmaError):
    """Error during installation process"""
    pass

class NetworkError(AsmaError):
    """Network connectivity issue"""
    pass
```

### 7.2 Error Messages

```python
ERROR_MESSAGES = {
    "skillset_not_found": """
skillset.yaml not found in current directory.

Run 'asma init' to create one, or specify path with --file:
  asma install --file path/to/skillset.yaml
""",

    "invalid_source_format": """
Invalid source format: {source}

Supported formats:
  - github:owner/repo/path
  - local:/path/to/skill
  - local:~/path/to/skill

Example:
  source: github:anthropics/skills/document-analyzer
""",

    "github_rate_limit": """
GitHub API rate limit exceeded.

Set GITHUB_TOKEN environment variable for higher limits:
  export GITHUB_TOKEN=ghp_your_token_here
  asma install

Generate token at: https://github.com/settings/tokens
Required scope: public_repo (or repo for private repos)
""",

    "skill_validation_failed": """
Skill validation failed: {skill_name}

Errors:
{errors}

Fix SKILL.md or remove skill from skillset.yaml
""",
}
```

### 7.3 Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential

class GitHubClient:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(NetworkError)
    )
    def fetch_with_retry(self, url: str) -> dict:
        """Fetch from GitHub API with automatic retries"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.Timeout:
            raise NetworkError(f"Request timeout: {url}")
        except requests.RequestException as e:
            if e.response and e.response.status_code == 403:
                # Check if rate limited
                if "rate limit" in e.response.text.lower():
                    raise AsmaError(ERROR_MESSAGES["github_rate_limit"])
            raise NetworkError(f"Network error: {e}")
```

---

## 8. CLI Output Formatting

### 8.1 Progress Indicators

```python
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()

def install_with_progress(skills: list[Skill]):
    """Install skills with progress bar"""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:

        for skill in skills:
            task = progress.add_task(
                f"Installing {skill.name}...",
                total=None
            )

            try:
                result = install_skill(skill)
                progress.update(task, description=f"✓ {skill.name}")
            except Exception as e:
                progress.update(task, description=f"✗ {skill.name}: {e}")


def display_list(skills: list[LockEntry]):
    """Display installed skills as table"""

    table = Table(title="Installed Skills")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="green")
    table.add_column("Source", style="yellow")
    table.add_column("Scope", style="magenta")

    for skill in skills:
        table.add_row(
            skill.name,
            skill.resolved_version,
            skill.source.split(":")[1],  # Strip prefix
            skill.scope
        )

    console.print(table)
```

### 8.2 Verbosity Levels

```python
class Logger:
    def __init__(self, verbosity: int = 0, quiet: bool = False):
        self.verbosity = verbosity  # 0=normal, 1=verbose, 2=debug
        self.quiet = quiet

    def info(self, msg: str):
        """Always shown unless --quiet"""
        if not self.quiet:
            console.print(msg)

    def verbose(self, msg: str):
        """Shown with --verbose"""
        if self.verbosity >= 1 and not self.quiet:
            console.print(f"[dim]{msg}[/dim]")

    def debug(self, msg: str):
        """Shown with --verbose --verbose"""
        if self.verbosity >= 2 and not self.quiet:
            console.print(f"[dim][DEBUG] {msg}[/dim]")

    def error(self, msg: str):
        """Always shown"""
        console.print(f"[bold red]Error:[/bold red] {msg}", style="red")

    def success(self, msg: str):
        """Always shown unless --quiet"""
        if not self.quiet:
            console.print(f"[green]✓[/green] {msg}")
```

---

## 9. Testing Strategy

### 9.1 Test Categories

1. **Unit Tests**: Test individual functions and classes
2. **Integration Tests**: Test command workflows end-to-end
3. **Fixture Tests**: Test with sample skillset.yaml files

### 9.2 Test Fixtures

```python
# tests/fixtures/simple_skillset.yaml
global:
  - name: test-skill
    source: github:anthropics/skills/test-skill
    version: v1.0.0

# tests/fixtures/sample_skill/SKILL.md
---
name: test-skill
description: A test skill for validation
---

# Test Skill

## Instructions
This is a test skill.
```

### 9.3 Example Tests

```python
import pytest
from asma.core.validator import SkillValidator

def test_valid_skill_md(tmp_path):
    """Test validation of properly formatted SKILL.md"""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()

    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("""---
name: test-skill
description: Test description
---

# Test Skill
""")

    result = SkillValidator.validate(skill_dir)
    assert result.valid
    assert len(result.errors) == 0


def test_missing_frontmatter(tmp_path):
    """Test skill without frontmatter"""
    skill_dir = tmp_path / "bad-skill"
    skill_dir.mkdir()

    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("# Just a heading")

    result = SkillValidator.validate(skill_dir)
    assert not result.valid
    assert "frontmatter" in result.errors[0].lower()


@pytest.fixture
def mock_github_api(requests_mock):
    """Mock GitHub API responses"""
    requests_mock.get(
        "https://api.github.com/repos/test/repo/git/refs/tags/v1.0.0",
        json={"object": {"sha": "abc123"}}
    )
    return requests_mock


def test_github_install(tmp_path, mock_github_api, monkeypatch):
    """Test installing from GitHub"""
    monkeypatch.chdir(tmp_path)

    skillset = tmp_path / "skillset.yaml"
    skillset.write_text("""
global:
  - name: test-skill
    source: github:test/repo
    version: v1.0.0
""")

    from asma.cli.commands.install import install
    result = install(skillset_path=skillset)

    assert result.success
    assert (Path.home() / ".claude/skills/test-skill").exists()
```

---

## 10. Performance Considerations

### 10.1 Caching Strategy

```python
class CacheManager:
    """Manage downloaded artifacts"""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cached_download(self, commit: str) -> Optional[Path]:
        """Check if commit tarball is cached"""
        cache_path = self.cache_dir / f"{commit}.tar.gz"
        return cache_path if cache_path.exists() else None

    def cache_download(self, commit: str, data: bytes) -> Path:
        """Store download in cache"""
        cache_path = self.cache_dir / f"{commit}.tar.gz"
        cache_path.write_bytes(data)
        return cache_path

    def clean_old_cache(self, max_age_days: int = 30):
        """Remove cache files older than specified days"""
        cutoff = datetime.now() - timedelta(days=max_age_days)

        for cache_file in self.cache_dir.glob("*.tar.gz"):
            if datetime.fromtimestamp(cache_file.stat().st_mtime) < cutoff:
                cache_file.unlink()
```

### 10.2 Parallel Downloads

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def parallel_install(skills: list[Skill], max_workers: int = 4):
    """Install multiple skills in parallel"""

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_skill = {
            executor.submit(install_skill, skill): skill
            for skill in skills
        }

        results = []
        for future in as_completed(future_to_skill):
            skill = future_to_skill[future]
            try:
                result = future.result(timeout=300)  # 5 min timeout
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to install {skill.name}: {e}")
                results.append({"skill": skill, "error": str(e)})

        return results
```

---

## 11. Security Considerations

### 11.1 Path Traversal Prevention

```python
def safe_extract(tar_file: tarfile.TarFile, dest: Path):
    """Safely extract tarball preventing path traversal"""

    for member in tar_file.getmembers():
        # Resolve member path
        member_path = (dest / member.name).resolve()

        # Ensure it's within dest directory
        if not str(member_path).startswith(str(dest.resolve())):
            raise SecurityError(f"Path traversal attempt: {member.name}")

        # Extract
        tar_file.extract(member, dest)
```

### 11.2 SKILL.md Size Limits

```python
MAX_SKILL_MD_SIZE = 1_000_000  # 1 MB

def validate_file_size(file_path: Path):
    """Prevent DoS via huge SKILL.md files"""
    size = file_path.stat().st_size
    if size > MAX_SKILL_MD_SIZE:
        raise ValidationError(
            f"SKILL.md too large: {size} bytes (max: {MAX_SKILL_MD_SIZE})"
        )
```

### 11.3 Code Execution Warnings

```python
def install_with_security_check(skill: Skill):
    """Warn about potentially executable content"""

    skill_path = skill.install_path
    executables = list(skill_path.glob("scripts/*"))

    if executables:
        console.print(
            f"[yellow]⚠ Warning:[/yellow] {skill.name} contains executable scripts:",
            style="yellow"
        )
        for exe in executables:
            console.print(f"  - {exe.name}")

        if not confirm("Continue installation?"):
            raise InstallationError("Installation cancelled by user")
```

---

## 12. Future Extensibility

### 12.1 Plugin System (Post-MVP)

```python
class SourcePlugin(Protocol):
    """Protocol for custom source handlers"""

    def can_handle(self, source: str) -> bool:
        """Return True if this plugin handles the source format"""
        ...

    def install(self, skill: Skill, dest: Path) -> InstallResult:
        """Install skill from custom source"""
        ...


# User can register custom handlers
asma.register_source_plugin(S3SourcePlugin())
asma.register_source_plugin(DockerHubPlugin())
```

### 12.2 Hooks (Post-MVP)

```yaml
# skillset.yaml
config:
  hooks:
    pre_install: .asma/hooks/pre-install.sh
    post_install: .asma/hooks/post-install.sh
    pre_update: .asma/hooks/pre-update.sh
```

---

This design document provides implementation-ready specifications. Ready to proceed with coding?
