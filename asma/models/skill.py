"""Data models for skills and skillsets."""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional
import re


class SkillScope(str, Enum):
    """Scope where a skill is installed."""

    GLOBAL = "global"
    PROJECT = "project"


@dataclass
class Skill:
    """Represents a skill definition from skillset.yaml."""

    name: str
    source: str
    scope: SkillScope

    version: Optional[str] = None
    ref: Optional[str] = None
    enabled: bool = True
    alias: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate skill data after initialization."""
        # Validate name format
        if not self.name or not re.match(r'^[a-z0-9-]+$', self.name):
            raise ValueError(
                f"Invalid skill name: '{self.name}'. "
                "Name must contain only lowercase letters, numbers, and hyphens."
            )

        # Validate source format
        valid_prefixes = ('github:', 'local:', 'git:')
        if not self.source or not self.source.startswith(valid_prefixes):
            raise ValueError(
                f"Invalid source format: '{self.source}'. "
                f"Source must start with one of: {', '.join(valid_prefixes)}"
            )

        # Validate version/ref mutual exclusivity
        if self.version and self.ref:
            raise ValueError(
                f"Cannot specify both version and ref for skill '{self.name}'. "
                "Use either version (for tags) or ref (for branches/commits)."
            )

    @property
    def install_name(self) -> str:
        """Name to use for installation directory."""
        return self.alias or self.name

    @property
    def install_path(self) -> Path:
        """Full path where skill will be installed."""
        if self.scope == SkillScope.GLOBAL:
            base = Path.home() / ".claude/skills"
        else:
            base = Path.cwd() / ".claude/skills"
        return base / self.install_name
