"""Skill checker module for verifying installed skills."""
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Literal

from asma.models.lock import LockEntry
from asma.models.skill import SkillScope


@dataclass
class CheckResult:
    """Result of checking a skill's installation status."""

    skill_name: str
    scope: SkillScope
    status: Literal["ok", "missing", "broken_symlink", "checksum_mismatch"]
    expected_path: Path
    actual_path: Optional[Path] = None
    expected_checksum: Optional[str] = None
    actual_checksum: Optional[str] = None
    error_message: Optional[str] = None


class SkillChecker:
    """Check that installed skills exist and are valid."""

    def get_install_path(self, entry: LockEntry) -> Path:
        """
        Get the expected install path for a skill.

        Args:
            entry: Lock file entry for the skill

        Returns:
            Path where the skill should be installed
        """
        if entry.scope == SkillScope.GLOBAL:
            return Path.home() / ".claude/skills" / entry.name
        else:
            return Path.cwd() / ".claude/skills" / entry.name

    def check_skill(
        self,
        entry: LockEntry,
        base_path: Optional[Path] = None,
        verify_checksum: bool = False,
    ) -> CheckResult:
        """
        Check if a skill is properly installed.

        Args:
            entry: Lock file entry for the skill
            base_path: Optional base path override (for testing)
            verify_checksum: Whether to verify SKILL.md checksum

        Returns:
            CheckResult with status and details
        """
        # Determine install path
        if base_path is not None:
            install_path = base_path / ".claude/skills" / entry.name
        else:
            install_path = self.get_install_path(entry)

        # Check if path exists
        if not install_path.exists():
            # Check if it's a broken symlink
            if install_path.is_symlink():
                return CheckResult(
                    skill_name=entry.name,
                    scope=entry.scope,
                    status="broken_symlink",
                    expected_path=install_path,
                    error_message=f"Symlink target does not exist: {install_path.resolve()}",
                )
            return CheckResult(
                skill_name=entry.name,
                scope=entry.scope,
                status="missing",
                expected_path=install_path,
                error_message=f"Directory not found: {install_path}",
            )

        # Check for broken symlink (exists but symlink is broken)
        if install_path.is_symlink():
            try:
                # Try to resolve the symlink
                resolved = install_path.resolve(strict=True)
            except (OSError, FileNotFoundError):
                return CheckResult(
                    skill_name=entry.name,
                    scope=entry.scope,
                    status="broken_symlink",
                    expected_path=install_path,
                    error_message="Symlink target does not exist",
                )

        # Verify checksum if requested
        if verify_checksum:
            skill_md_path = install_path / "SKILL.md"
            if not skill_md_path.exists():
                return CheckResult(
                    skill_name=entry.name,
                    scope=entry.scope,
                    status="missing",
                    expected_path=install_path,
                    error_message="SKILL.md not found",
                )

            actual_checksum = self.calculate_checksum(skill_md_path)
            if actual_checksum != entry.checksum:
                return CheckResult(
                    skill_name=entry.name,
                    scope=entry.scope,
                    status="checksum_mismatch",
                    expected_path=install_path,
                    expected_checksum=entry.checksum,
                    actual_checksum=actual_checksum,
                    error_message="Checksum does not match",
                )

        # All checks passed
        return CheckResult(
            skill_name=entry.name,
            scope=entry.scope,
            status="ok",
            expected_path=install_path,
        )

    def calculate_checksum(self, file_path: Path) -> str:
        """
        Calculate SHA256 checksum of a file.

        Args:
            file_path: Path to the file

        Returns:
            Checksum string in format "sha256:hexdigest"
        """
        content = file_path.read_text()
        digest = hashlib.sha256(content.encode()).hexdigest()
        return f"sha256:{digest}"
