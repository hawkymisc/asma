"""Skill installer for installing skills to target directories."""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import shutil
import hashlib

from asma.models.skill import Skill
from asma.core.sources.base import SourceHandler, ResolvedSource
from asma.core.validator import SkillValidator


@dataclass
class InstallResult:
    """Result of skill installation."""

    success: bool
    skill_name: str
    install_path: Path
    error: Optional[str] = None

    # Lock file fields
    version: Optional[str] = None
    resolved_commit: Optional[str] = None
    checksum: Optional[str] = None
    symlink: bool = False
    resolved_path: Optional[str] = None


class SkillInstaller:
    """Installer for skills."""

    def install_skill(
        self,
        skill: Skill,
        source_handler: SourceHandler,
        install_base: Path,
        force: bool = False
    ) -> InstallResult:
        """
        Install a skill to the target directory.

        Args:
            skill: Skill to install
            source_handler: Source handler for the skill
            install_base: Base directory for installation
            force: Overwrite existing installation

        Returns:
            InstallResult with installation details
        """
        try:
            # Determine install path
            install_path = install_base / skill.install_name

            # Check if already exists
            if install_path.exists() and not force:
                return InstallResult(
                    success=False,
                    skill_name=skill.name,
                    install_path=install_path,
                    error="Skill already exists. Use --force to overwrite."
                )

            # Resolve source
            resolved = source_handler.resolve(skill)

            # Download/get source
            source_path = source_handler.download(resolved)

            # Validate SKILL.md
            validation = SkillValidator.validate(source_path)
            if not validation.valid:
                return InstallResult(
                    success=False,
                    skill_name=skill.name,
                    install_path=install_path,
                    error=f"Validation failed: {', '.join(validation.errors)}"
                )

            # Remove existing if force
            # Use try-except for atomic operation to mitigate TOCTOU vulnerability
            try:
                if install_path.is_symlink():
                    install_path.unlink()
                elif install_path.is_dir():
                    shutil.rmtree(install_path)
                elif install_path.exists():
                    install_path.unlink()
            except OSError as e:
                return InstallResult(
                    success=False,
                    skill_name=skill.name,
                    install_path=install_path,
                    error=f"Failed to remove existing installation: {e}"
                )

            # Create parent directory
            install_path.parent.mkdir(parents=True, exist_ok=True)

            # Install (symlink or copy)
            is_symlink = source_handler.should_symlink()
            if is_symlink:
                install_path.symlink_to(source_path, target_is_directory=True)
            else:
                shutil.copytree(source_path, install_path)

            # Calculate checksum of SKILL.md for lock file
            skill_md_path = source_path / "SKILL.md"
            checksum = None
            if skill_md_path.exists():
                checksum_hash = hashlib.sha256(skill_md_path.read_bytes()).hexdigest()
                checksum = f"sha256:{checksum_hash}"

            return InstallResult(
                success=True,
                skill_name=skill.name,
                install_path=install_path,
                version=resolved.version,
                resolved_commit=resolved.commit,
                checksum=checksum,
                symlink=is_symlink,
                resolved_path=str(resolved.local_path) if resolved.local_path else None
            )

        except Exception as e:
            return InstallResult(
                success=False,
                skill_name=skill.name,
                install_path=install_base / skill.install_name,
                error=str(e)
            )
