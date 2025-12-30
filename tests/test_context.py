"""Tests for context extractor module."""
import json
import pytest
import yaml
from pathlib import Path
from datetime import datetime

from asma.core.context import ContextExtractor, SkillContext
from asma.models.lock import LockEntry
from asma.models.skill import SkillScope


class TestSkillContext:
    """Tests for SkillContext dataclass."""

    def test_skill_context_creation(self):
        """Test creating a SkillContext."""
        context = SkillContext(
            skill_name="test-skill",
            scope=SkillScope.GLOBAL,
            metadata={"name": "test-skill", "description": "A test skill"},
            install_path=Path("/home/user/.claude/skills/test-skill"),
        )
        assert context.skill_name == "test-skill"
        assert context.metadata["description"] == "A test skill"
        assert context.error is None

    def test_skill_context_with_error(self):
        """Test creating a SkillContext with error."""
        context = SkillContext(
            skill_name="broken-skill",
            scope=SkillScope.PROJECT,
            metadata={},
            install_path=Path(".claude/skills/broken-skill"),
            error="SKILL.md not found",
        )
        assert context.error == "SKILL.md not found"
        assert context.metadata == {}


class TestContextExtractor:
    """Tests for ContextExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create a ContextExtractor instance."""
        return ContextExtractor()

    @pytest.fixture
    def sample_skill_dir(self, tmp_path):
        """Create a sample skill directory with SKILL.md."""
        skill_dir = tmp_path / ".claude/skills/test-skill"
        skill_dir.mkdir(parents=True)
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: test-skill
description: A helpful test skill
author: Test Author
version: 1.0.0
tags:
  - testing
  - example
---

# Test Skill

## Instructions
This is a test skill.
""")
        return skill_dir

    @pytest.fixture
    def sample_lock_entry(self):
        """Create a sample lock entry."""
        return LockEntry(
            name="test-skill",
            scope=SkillScope.PROJECT,
            source="local:/path/to/skill",
            resolved_version="local@abc123",
            resolved_commit="abc123def456",
            installed_at=datetime.now(),
            checksum="sha256:test",
        )

    def test_extract_context_success(self, extractor, sample_skill_dir, sample_lock_entry, tmp_path):
        """Test extracting context from a valid skill."""
        context = extractor.extract_context(sample_lock_entry, base_path=tmp_path)

        assert context.skill_name == "test-skill"
        assert context.scope == SkillScope.PROJECT
        assert context.error is None
        assert context.metadata["name"] == "test-skill"
        assert context.metadata["description"] == "A helpful test skill"
        assert context.metadata["author"] == "Test Author"
        assert context.metadata["version"] == "1.0.0"
        assert "testing" in context.metadata["tags"]

    def test_extract_context_missing_skill(self, extractor, tmp_path):
        """Test extracting context from a missing skill."""
        entry = LockEntry(
            name="missing-skill",
            scope=SkillScope.PROJECT,
            source="local:/path",
            resolved_version="local@abc",
            resolved_commit="abc123",
            installed_at=datetime.now(),
            checksum="sha256:test",
        )

        context = extractor.extract_context(entry, base_path=tmp_path)

        assert context.skill_name == "missing-skill"
        assert context.error is not None
        assert "not found" in context.error.lower()

    def test_extract_context_invalid_frontmatter(self, extractor, tmp_path):
        """Test extracting context from skill with invalid frontmatter."""
        skill_dir = tmp_path / ".claude/skills/bad-skill"
        skill_dir.mkdir(parents=True)
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("# No frontmatter here")

        entry = LockEntry(
            name="bad-skill",
            scope=SkillScope.PROJECT,
            source="local:/path",
            resolved_version="local@abc",
            resolved_commit="abc123",
            installed_at=datetime.now(),
            checksum="sha256:test",
        )

        context = extractor.extract_context(entry, base_path=tmp_path)

        assert context.error is not None
        assert "frontmatter" in context.error.lower()

    def test_format_text_single_skill(self, extractor):
        """Test formatting a single skill as text."""
        contexts = [
            SkillContext(
                skill_name="test-skill",
                scope=SkillScope.GLOBAL,
                metadata={
                    "name": "test-skill",
                    "description": "A test skill",
                },
                install_path=Path("/home/user/.claude/skills/test-skill"),
            )
        ]

        output = extractor.format_text(contexts)

        assert "Global Skills:" in output
        assert "test-skill:" in output
        assert "name: test-skill" in output
        assert "description: A test skill" in output

    def test_format_text_multiple_scopes(self, extractor):
        """Test formatting skills from multiple scopes."""
        contexts = [
            SkillContext(
                skill_name="global-skill",
                scope=SkillScope.GLOBAL,
                metadata={"name": "global-skill", "description": "Global"},
                install_path=Path("/home/user/.claude/skills/global-skill"),
            ),
            SkillContext(
                skill_name="project-skill",
                scope=SkillScope.PROJECT,
                metadata={"name": "project-skill", "description": "Project"},
                install_path=Path(".claude/skills/project-skill"),
            ),
        ]

        output = extractor.format_text(contexts)

        assert "Global Skills:" in output
        assert "Project Skills:" in output
        assert "global-skill:" in output
        assert "project-skill:" in output

    def test_format_text_with_error(self, extractor):
        """Test formatting a skill with error."""
        contexts = [
            SkillContext(
                skill_name="error-skill",
                scope=SkillScope.GLOBAL,
                metadata={},
                install_path=Path("/home/user/.claude/skills/error-skill"),
                error="SKILL.md not found",
            )
        ]

        output = extractor.format_text(contexts)

        assert "error-skill:" in output
        assert "error:" in output.lower()

    def test_format_yaml(self, extractor):
        """Test formatting contexts as YAML."""
        contexts = [
            SkillContext(
                skill_name="test-skill",
                scope=SkillScope.GLOBAL,
                metadata={
                    "name": "test-skill",
                    "description": "A test skill",
                    "version": "1.0.0",
                },
                install_path=Path("/home/user/.claude/skills/test-skill"),
            ),
            SkillContext(
                skill_name="project-skill",
                scope=SkillScope.PROJECT,
                metadata={
                    "name": "project-skill",
                    "description": "Project skill",
                },
                install_path=Path(".claude/skills/project-skill"),
            ),
        ]

        output = extractor.format_yaml(contexts)

        # Parse the YAML to verify it's valid
        data = yaml.safe_load(output)

        assert "global" in data
        assert "project" in data
        assert data["global"]["test-skill"]["name"] == "test-skill"
        assert data["global"]["test-skill"]["version"] == "1.0.0"
        assert data["project"]["project-skill"]["description"] == "Project skill"

    def test_format_json(self, extractor):
        """Test formatting contexts as JSON."""
        contexts = [
            SkillContext(
                skill_name="test-skill",
                scope=SkillScope.GLOBAL,
                metadata={
                    "name": "test-skill",
                    "description": "A test skill",
                },
                install_path=Path("/home/user/.claude/skills/test-skill"),
            ),
        ]

        output = extractor.format_json(contexts)

        # Parse the JSON to verify it's valid
        data = json.loads(output)

        assert "global" in data
        assert data["global"]["test-skill"]["name"] == "test-skill"
        assert data["global"]["test-skill"]["description"] == "A test skill"

    def test_format_yaml_empty(self, extractor):
        """Test formatting empty contexts as YAML."""
        output = extractor.format_yaml([])
        data = yaml.safe_load(output)

        assert data["global"] == {}
        assert data["project"] == {}

    def test_format_json_empty(self, extractor):
        """Test formatting empty contexts as JSON."""
        output = extractor.format_json([])
        data = json.loads(output)

        assert data["global"] == {}
        assert data["project"] == {}


class TestContextExtractorFormatOptions:
    """Tests for format options (indent, wrap_width, verbose, table)."""

    @pytest.fixture
    def extractor(self):
        """Create a ContextExtractor instance."""
        return ContextExtractor()

    @pytest.fixture
    def sample_contexts(self):
        """Create sample contexts with various metadata."""
        return [
            SkillContext(
                skill_name="test-skill",
                scope=SkillScope.GLOBAL,
                metadata={
                    "name": "test-skill",
                    "description": "A very long description that should be wrapped when the wrap width is set to a smaller value than the description length for testing purposes",
                    "version": "1.0.0",
                    "author": "Test Author",
                    "tags": ["testing", "example"],
                },
                install_path=Path("/home/user/.claude/skills/test-skill"),
            ),
            SkillContext(
                skill_name="another-skill",
                scope=SkillScope.PROJECT,
                metadata={
                    "name": "another-skill",
                    "description": "Project skill description",
                    "version": "2.0.0",
                },
                install_path=Path(".claude/skills/another-skill"),
            ),
        ]

    # format_text option tests

    def test_format_text_with_custom_indent(self, extractor, sample_contexts):
        """Test text formatting with custom indent."""
        output = extractor.format_text(sample_contexts, indent=4)
        lines = output.split('\n')
        # Skill name line should be indented with 4 spaces
        skill_lines = [line for line in lines if "test-skill:" in line]
        assert len(skill_lines) > 0
        assert skill_lines[0].startswith("    ")

    def test_format_text_with_wrap_width(self, extractor, sample_contexts):
        """Test text formatting with wrap width."""
        output = extractor.format_text(sample_contexts, wrap_width=60)
        lines = output.split('\n')
        # All lines should be <= 60 characters
        for line in lines:
            assert len(line) <= 60, f"Line exceeds wrap width: '{line}' ({len(line)} chars)"

    def test_format_text_default_shows_basic_fields(self, extractor, sample_contexts):
        """Test that default text format shows only basic fields."""
        output = extractor.format_text(sample_contexts, verbose=False)
        # Should contain basic fields
        assert "name:" in output
        assert "description:" in output
        assert "version:" in output
        # Should NOT contain extra fields
        assert "author:" not in output
        assert "tags:" not in output

    def test_format_text_verbose_shows_all_fields(self, extractor, sample_contexts):
        """Test that verbose text format shows all fields."""
        output = extractor.format_text(sample_contexts, verbose=True)
        # Should contain all fields
        assert "name:" in output
        assert "description:" in output
        assert "version:" in output
        assert "author:" in output
        assert "tags:" in output

    # format_table tests

    def test_format_table_basic(self, extractor, sample_contexts):
        """Test basic table format output."""
        output = extractor.format_table(sample_contexts)
        # Should contain table headers
        assert "Name" in output
        assert "Scope" in output
        assert "Description" in output
        assert "Version" in output
        # Should contain skill data
        assert "test-skill" in output
        assert "another-skill" in output

    def test_format_table_empty(self, extractor):
        """Test table format with empty contexts."""
        output = extractor.format_table([])
        # Headers should still be present
        assert "Name" in output

    def test_format_table_with_error(self, extractor):
        """Test table format with error skill."""
        contexts = [
            SkillContext(
                skill_name="error-skill",
                scope=SkillScope.PROJECT,
                metadata={},
                install_path=Path(".claude/skills/error-skill"),
                error="SKILL.md not found",
            )
        ]
        output = extractor.format_table(contexts)
        assert "error-skill" in output
        # Error should be displayed somehow
        assert "not found" in output.lower() or "error" in output.lower()

    def test_format_table_verbose(self, extractor, sample_contexts):
        """Test verbose table format shows additional columns."""
        output = extractor.format_table(sample_contexts, verbose=True)
        # Should have additional columns
        assert "Author" in output
        assert "Test Author" in output
