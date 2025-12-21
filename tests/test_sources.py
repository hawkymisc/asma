"""Tests for source handlers."""
import pytest
from pathlib import Path
from asma.core.sources.local import LocalSourceHandler
from asma.core.sources.base import ResolvedSource
from asma.models.skill import Skill, SkillScope


class TestLocalSourceHandler:
    """Test LocalSourceHandler for local filesystem sources."""

    def test_resolve_absolute_path(self, tmp_path):
        """Test resolving absolute path."""
        # Given: a local skill directory with SKILL.md
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: test-skill
description: Test
---
# Test
""")

        # And: a skill definition
        skill = Skill(
            name="test-skill",
            source=f"local:{skill_dir}",
            scope=SkillScope.GLOBAL
        )

        # When: we resolve the source
        handler = LocalSourceHandler()
        resolved = handler.resolve(skill)

        # Then: should resolve to the path
        assert resolved.local_path == skill_dir
        assert resolved.commit  # Should have a checksum
        assert "local@" in resolved.version

    def test_resolve_path_normalized(self, tmp_path):
        """Test that paths are normalized to absolute."""
        # Given: skill directory
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: test\ndescription: test\n---\n")

        skill = Skill(
            name="test-skill",
            source=f"local:{skill_dir}",
            scope=SkillScope.GLOBAL
        )

        # When: we resolve
        handler = LocalSourceHandler()
        resolved = handler.resolve(skill)

        # Then: should be absolute and resolved
        assert resolved.local_path.is_absolute()
        assert resolved.local_path == skill_dir.resolve()

    def test_resolve_nonexistent_path(self):
        """Test that resolving non-existent path raises error."""
        # Given: skill with non-existent path
        skill = Skill(
            name="test-skill",
            source="local:/nonexistent/path",
            scope=SkillScope.GLOBAL
        )

        # When/Then: should raise FileNotFoundError
        handler = LocalSourceHandler()
        with pytest.raises(FileNotFoundError, match="Local skill not found"):
            handler.resolve(skill)

    def test_resolve_path_without_skill_md(self, tmp_path):
        """Test that path must contain SKILL.md."""
        # Given: directory without SKILL.md
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()

        skill = Skill(
            name="test-skill",
            source=f"local:{skill_dir}",
            scope=SkillScope.GLOBAL
        )

        # When/Then: should raise ValueError
        handler = LocalSourceHandler()
        with pytest.raises(ValueError, match="SKILL.md not found"):
            handler.resolve(skill)

    def test_should_symlink(self):
        """Test that local sources should be symlinked."""
        # Given: local source handler
        handler = LocalSourceHandler()

        # When/Then: should return True for symlink
        assert handler.should_symlink() is True

    def test_download_returns_original_path(self, tmp_path):
        """Test that download just returns the original path."""
        # Given: resolved local source
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: test\ndescription: test\n---\n")

        skill = Skill(
            name="test-skill",
            source=f"local:{skill_dir}",
            scope=SkillScope.GLOBAL
        )

        handler = LocalSourceHandler()
        resolved = handler.resolve(skill)

        # When: we "download"
        result_path = handler.download(resolved)

        # Then: should return same path (no actual download)
        assert result_path == skill_dir
