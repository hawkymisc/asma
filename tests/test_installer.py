"""Tests for skill installer."""
import pytest
from pathlib import Path
from asma.core.installer import SkillInstaller, InstallResult
from asma.models.skill import Skill, SkillScope
from asma.core.sources.local import LocalSourceHandler


class TestSkillInstaller:
    """Test SkillInstaller class."""

    def test_install_local_skill_with_symlink(self, tmp_path):
        """Test installing a local skill creates symlink."""
        # Given: a local skill
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test skill
---
# Test
""")

        skill = Skill(
            name="test-skill",
            source=f"local:{source_dir}",
            scope=SkillScope.GLOBAL
        )

        # Mock install path
        install_base = tmp_path / "install"
        install_base.mkdir()

        # When: we install the skill
        installer = SkillInstaller()
        result = installer.install_skill(
            skill=skill,
            source_handler=LocalSourceHandler(),
            install_base=install_base
        )

        # Then: should create symlink
        assert result.success is True
        assert result.skill_name == "test-skill"
        assert result.install_path.exists()
        assert result.install_path.is_symlink()
        assert result.install_path.resolve() == source_dir.resolve()

    def test_install_skill_with_alias(self, tmp_path):
        """Test installing skill with alias uses alias as directory name."""
        # Given: skill with alias
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test
---
# Test
""")

        skill = Skill(
            name="test-skill",
            source=f"local:{source_dir}",
            scope=SkillScope.GLOBAL,
            alias="my-custom-name"
        )

        install_base = tmp_path / "install"
        install_base.mkdir()

        # When: we install
        installer = SkillInstaller()
        result = installer.install_skill(
            skill=skill,
            source_handler=LocalSourceHandler(),
            install_base=install_base
        )

        # Then: should use alias
        assert result.install_path.name == "my-custom-name"
        assert (install_base / "my-custom-name").exists()

    def test_install_creates_parent_directory(self, tmp_path):
        """Test that install creates parent directory if needed."""
        # Given: skill and non-existent install base
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test
---
# Test
""")

        skill = Skill(
            name="test-skill",
            source=f"local:{source_dir}",
            scope=SkillScope.GLOBAL
        )

        install_base = tmp_path / "nonexistent" / "install"

        # When: we install
        installer = SkillInstaller()
        result = installer.install_skill(
            skill=skill,
            source_handler=LocalSourceHandler(),
            install_base=install_base
        )

        # Then: should create parent directories
        assert result.success is True
        assert install_base.exists()
        assert result.install_path.exists()

    def test_install_validates_skill(self, tmp_path):
        """Test that install validates SKILL.md."""
        # Given: skill with invalid SKILL.md (missing description)
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "SKILL.md").write_text("""---
name: test-skill
---
# Test
""")

        skill = Skill(
            name="test-skill",
            source=f"local:{source_dir}",
            scope=SkillScope.GLOBAL
        )

        install_base = tmp_path / "install"
        install_base.mkdir()

        # When: we install
        installer = SkillInstaller()
        result = installer.install_skill(
            skill=skill,
            source_handler=LocalSourceHandler(),
            install_base=install_base
        )

        # Then: should fail validation
        assert result.success is False
        assert "description" in result.error.lower()

    def test_install_overwrites_existing_with_force(self, tmp_path):
        """Test that force=True overwrites existing installation."""
        # Given: already installed skill
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test
---
# Test
""")

        skill = Skill(
            name="test-skill",
            source=f"local:{source_dir}",
            scope=SkillScope.GLOBAL
        )

        install_base = tmp_path / "install"
        install_base.mkdir()
        existing = install_base / "test-skill"
        existing.mkdir()
        (existing / "old.txt").write_text("old content")

        # When: we install with force
        installer = SkillInstaller()
        result = installer.install_skill(
            skill=skill,
            source_handler=LocalSourceHandler(),
            install_base=install_base,
            force=True
        )

        # Then: should overwrite
        assert result.success is True
        assert not (existing / "old.txt").exists()

    def test_install_fails_if_exists_without_force(self, tmp_path):
        """Test that install fails if skill already exists and force=False."""
        # Given: already installed skill
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test
---
# Test
""")

        skill = Skill(
            name="test-skill",
            source=f"local:{source_dir}",
            scope=SkillScope.GLOBAL
        )

        install_base = tmp_path / "install"
        install_base.mkdir()
        (install_base / "test-skill").mkdir()

        # When: we install without force
        installer = SkillInstaller()
        result = installer.install_skill(
            skill=skill,
            source_handler=LocalSourceHandler(),
            install_base=install_base,
            force=False
        )

        # Then: should fail
        assert result.success is False
        assert "already exists" in result.error.lower()

    def test_install_overwrites_existing_symlink_with_force(self, tmp_path):
        """Test that force=True can overwrite existing symlink."""
        # Given: source skill
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test
---
# Test
""")

        # And: existing symlink
        install_base = tmp_path / "install"
        install_base.mkdir()
        old_source = tmp_path / "old_source"
        old_source.mkdir()
        existing_link = install_base / "test-skill"
        existing_link.symlink_to(old_source, target_is_directory=True)

        skill = Skill(
            name="test-skill",
            source=f"local:{source_dir}",
            scope=SkillScope.GLOBAL
        )

        # When: we install with force
        installer = SkillInstaller()
        result = installer.install_skill(
            skill=skill,
            source_handler=LocalSourceHandler(),
            install_base=install_base,
            force=True
        )

        # Then: should replace symlink
        assert result.success is True
        assert existing_link.is_symlink()
        assert existing_link.resolve() == source_dir.resolve()

    def test_install_with_copy_instead_of_symlink(self, tmp_path):
        """Test installing with a handler that copies instead of symlinks."""
        from asma.core.sources.base import SourceHandler, ResolvedSource
        from unittest.mock import Mock

        # Given: source skill
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test
---
# Test
""")
        (source_dir / "extra.txt").write_text("extra content")

        skill = Skill(
            name="test-skill",
            source="git:https://example.com/repo.git",
            scope=SkillScope.GLOBAL
        )

        install_base = tmp_path / "install"
        install_base.mkdir()

        # Create a mock handler that copies instead of symlinks
        mock_handler = Mock(spec=SourceHandler)
        mock_handler.resolve.return_value = ResolvedSource(
            version="1.0.0",
            commit="abc123",
            local_path=source_dir
        )
        mock_handler.download.return_value = source_dir
        mock_handler.should_symlink.return_value = False  # Copy instead

        # When: we install
        installer = SkillInstaller()
        result = installer.install_skill(
            skill=skill,
            source_handler=mock_handler,
            install_base=install_base
        )

        # Then: should copy files
        assert result.success is True
        install_path = install_base / "test-skill"
        assert install_path.exists()
        assert not install_path.is_symlink()  # Not a symlink
        assert (install_path / "SKILL.md").exists()
        assert (install_path / "extra.txt").exists()

    def test_install_handles_unexpected_exception(self, tmp_path):
        """Test that installer handles unexpected exceptions gracefully."""
        from asma.core.sources.base import SourceHandler
        from unittest.mock import Mock

        # Given: a handler that raises an unexpected exception
        skill = Skill(
            name="test-skill",
            source="git:https://example.com/repo.git",
            scope=SkillScope.GLOBAL
        )

        install_base = tmp_path / "install"
        install_base.mkdir()

        mock_handler = Mock(spec=SourceHandler)
        mock_handler.resolve.side_effect = RuntimeError("Unexpected network error")

        # When: we try to install
        installer = SkillInstaller()
        result = installer.install_skill(
            skill=skill,
            source_handler=mock_handler,
            install_base=install_base
        )

        # Then: should return failure with error message
        assert result.success is False
        assert result.skill_name == "test-skill"
        assert "Unexpected network error" in result.error
