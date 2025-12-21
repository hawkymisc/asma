"""Base classes for source handlers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from asma.models.skill import Skill


@dataclass
class ResolvedSource:
    """Resolved source information."""

    version: str
    commit: str
    local_path: Optional[Path] = None
    download_url: Optional[str] = None


class SourceHandler(ABC):
    """Abstract base class for skill source handlers."""

    @abstractmethod
    def resolve(self, skill: Skill) -> ResolvedSource:
        """
        Resolve skill source to downloadable information.

        Args:
            skill: Skill to resolve

        Returns:
            ResolvedSource with version, commit, and location info

        Raises:
            FileNotFoundError: If source doesn't exist
            ValueError: If source is invalid
        """
        pass

    @abstractmethod
    def download(self, resolved: ResolvedSource) -> Path:
        """
        Download/copy skill to a local directory.

        Args:
            resolved: Resolved source information

        Returns:
            Path to the skill directory

        Raises:
            FileNotFoundError: If download fails
        """
        pass

    @abstractmethod
    def should_symlink(self) -> bool:
        """Whether this source type should be symlinked instead of copied."""
        pass
