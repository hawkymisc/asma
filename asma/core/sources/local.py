"""Local filesystem source handler."""
import hashlib
from pathlib import Path

from asma.core.sources.base import SourceHandler, ResolvedSource
from asma.models.skill import Skill


class LocalSourceHandler(SourceHandler):
    """Handle local:path sources."""

    def resolve(self, skill: Skill) -> ResolvedSource:
        """
        Resolve local filesystem path.

        Args:
            skill: Skill with local: source

        Returns:
            ResolvedSource with local_path

        Raises:
            FileNotFoundError: If path doesn't exist
            ValueError: If SKILL.md not found
        """
        # Parse path from source (remove "local:" prefix)
        path_str = skill.source.replace("local:", "")
        path = Path(path_str).expanduser().resolve()

        # Check path exists
        if not path.exists():
            raise FileNotFoundError(f"Local skill not found: {path}")

        if not path.is_dir():
            raise ValueError(f"Local skill path must be directory: {path}")

        # Check for SKILL.md
        skill_md = path / "SKILL.md"
        if not skill_md.exists():
            raise ValueError(f"SKILL.md not found in {path}")

        # Calculate checksum of SKILL.md for version tracking
        checksum = hashlib.sha256(skill_md.read_bytes()).hexdigest()

        return ResolvedSource(
            version=f"local@{checksum[:8]}",
            commit=checksum,
            local_path=path
        )

    def download(self, resolved: ResolvedSource) -> Path:
        """
        Return the local path (no download needed).

        Args:
            resolved: Resolved source with local_path

        Returns:
            Path to the skill directory
        """
        if resolved.local_path is None:
            raise ValueError("ResolvedSource must have local_path for local sources")

        return resolved.local_path

    def should_symlink(self) -> bool:
        """Local sources should be symlinked."""
        return True
