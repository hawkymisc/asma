"""Tests for data models."""
import pytest
from asma.models.skill import Skill, SkillScope


class TestSkill:
    """Test Skill data model."""

    def test_create_skill_with_required_fields(self):
        """Test creating a skill with minimal required fields."""
        # Given: minimal skill data
        # When: we create a Skill
        skill = Skill(
            name="test-skill",
            source="github:anthropics/skills/test-skill",
            scope=SkillScope.GLOBAL
        )

        # Then: skill should be created successfully
        assert skill.name == "test-skill"
        assert skill.source == "github:anthropics/skills/test-skill"
        assert skill.scope == SkillScope.GLOBAL
        assert skill.version is None
        assert skill.ref is None
        assert skill.enabled is True
        assert skill.alias is None

    def test_skill_name_validation(self):
        """Test that skill name must follow format rules."""
        # Given: invalid skill names
        invalid_names = [
            "Invalid_Name",  # underscores
            "UPPERCASE",     # uppercase
            "has spaces",    # spaces
            "has@special",   # special chars
            "",              # empty
        ]

        # When/Then: creating skill should raise ValueError
        for invalid_name in invalid_names:
            with pytest.raises(ValueError, match="Invalid skill name"):
                Skill(
                    name=invalid_name,
                    source="github:test/repo",
                    scope=SkillScope.GLOBAL
                )

    def test_skill_valid_names(self):
        """Test that valid skill names are accepted."""
        # Given: valid skill names
        valid_names = [
            "simple",
            "with-hyphens",
            "with123numbers",
            "a",  # single char
            "very-long-name-with-many-hyphens-123",
        ]

        # When/Then: should create successfully
        for valid_name in valid_names:
            skill = Skill(
                name=valid_name,
                source="github:test/repo",
                scope=SkillScope.GLOBAL
            )
            assert skill.name == valid_name

    def test_skill_source_validation(self):
        """Test that source must have valid format."""
        # Given: invalid source formats
        invalid_sources = [
            "invalid-format",
            "http://example.com",
            "ftp:test/repo",
            "",
        ]

        # When/Then: should raise ValueError
        for invalid_source in invalid_sources:
            with pytest.raises(ValueError, match="Invalid source format"):
                Skill(
                    name="test-skill",
                    source=invalid_source,
                    scope=SkillScope.GLOBAL
                )

    def test_skill_valid_sources(self):
        """Test that valid source formats are accepted."""
        # Given: valid source formats
        valid_sources = [
            "github:user/repo",
            "github:user/repo/path/to/skill",
            "local:/absolute/path",
            "local:~/home/path",
            "local:./relative/path",
            "git:https://example.com/repo.git",
        ]

        # When/Then: should create successfully
        for valid_source in valid_sources:
            skill = Skill(
                name="test-skill",
                source=valid_source,
                scope=SkillScope.GLOBAL
            )
            assert skill.source == valid_source

    def test_skill_version_and_ref_mutual_exclusivity(self):
        """Test that both version and ref cannot be specified."""
        # Given: skill with both version and ref
        # When/Then: should raise ValueError
        with pytest.raises(ValueError, match="Cannot specify both version and ref"):
            Skill(
                name="test-skill",
                source="github:test/repo",
                scope=SkillScope.GLOBAL,
                version="v1.0.0",
                ref="main"
            )

    def test_skill_install_name(self):
        """Test that install_name returns alias if set, otherwise name."""
        # Given: skill without alias
        skill1 = Skill(
            name="test-skill",
            source="github:test/repo",
            scope=SkillScope.GLOBAL
        )

        # When/Then: install_name should be name
        assert skill1.install_name == "test-skill"

        # Given: skill with alias
        skill2 = Skill(
            name="test-skill",
            source="github:test/repo",
            scope=SkillScope.GLOBAL,
            alias="my-custom-name"
        )

        # When/Then: install_name should be alias
        assert skill2.install_name == "my-custom-name"
