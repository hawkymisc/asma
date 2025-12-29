"""Tests for SKILL.md validator."""
import pytest
from pathlib import Path
from asma.core.validator import SkillValidator, ValidationResult


class TestSkillValidator:
    """Test SkillValidator class."""

    def test_validate_skill_md_exists(self, tmp_path):
        """Test that validator checks if SKILL.md exists."""
        # Given: a directory without SKILL.md
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()

        # When: we validate the skill
        result = SkillValidator.validate(skill_dir)

        # Then: validation should fail with appropriate error
        assert result.valid is False
        assert len(result.errors) == 1
        assert "SKILL.md not found" in result.errors[0]

    def test_validate_skill_md_requires_frontmatter(self, tmp_path):
        """Test that SKILL.md must have YAML frontmatter."""
        # Given: SKILL.md without frontmatter
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("# Just a heading\n\nNo frontmatter here.")

        # When: we validate the skill
        result = SkillValidator.validate(skill_dir)

        # Then: validation should fail
        assert result.valid is False
        assert any("frontmatter" in error.lower() for error in result.errors)

    def test_validate_requires_name_field(self, tmp_path):
        """Test that frontmatter must have 'name' field."""
        # Given: SKILL.md with frontmatter but no name
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
description: A test skill
---

# Test Skill
""")

        # When: we validate
        result = SkillValidator.validate(skill_dir)

        # Then: should fail with missing name error
        assert result.valid is False
        assert any("name" in error.lower() for error in result.errors)

    def test_validate_requires_description_field(self, tmp_path):
        """Test that frontmatter must have 'description' field."""
        # Given: SKILL.md with frontmatter but no description
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: test-skill
---

# Test Skill
""")

        # When: we validate
        result = SkillValidator.validate(skill_dir)

        # Then: should fail with missing description error
        assert result.valid is False
        assert any("description" in error.lower() for error in result.errors)

    def test_validate_name_format(self, tmp_path):
        """Test that name must be lowercase with hyphens only."""
        # Given: SKILL.md with invalid name format
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: Invalid_Name_With_CAPS
description: A test skill
---

# Test Skill
""")

        # When: we validate
        result = SkillValidator.validate(skill_dir)

        # Then: should fail with invalid format error
        assert result.valid is False
        assert any("name" in error.lower() and "format" in error.lower() for error in result.errors)

    def test_validate_valid_skill(self, tmp_path):
        """Test that a properly formatted skill passes validation."""
        # Given: valid SKILL.md
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: test-skill
description: A properly formatted test skill for validation
---

# Test Skill

## Instructions
Follow these instructions.

## Examples
- Example 1

## Guidelines
- Guideline 1
""")

        # When: we validate
        result = SkillValidator.validate(skill_dir)

        # Then: should pass
        assert result.valid is True
        assert len(result.errors) == 0
        assert result.metadata["name"] == "test-skill"
        assert result.metadata["description"] == "A properly formatted test skill for validation"

    def test_validate_name_not_string(self, tmp_path):
        """Test that name field must be a string."""
        # Given: SKILL.md with non-string name
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: 123
description: Test skill
---
# Test
""")

        # When: we validate
        result = SkillValidator.validate(skill_dir)

        # Then: should fail
        assert result.valid is False
        assert any("name" in error.lower() and "string" in error.lower() for error in result.errors)

    def test_validate_description_not_string(self, tmp_path):
        """Test that description field must be a string."""
        # Given: SKILL.md with non-string description
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: test-skill
description: 123
---
# Test
""")

        # When: we validate
        result = SkillValidator.validate(skill_dir)

        # Then: should fail
        assert result.valid is False
        assert any("description" in error.lower() and "string" in error.lower() for error in result.errors)

    def test_validate_description_empty(self, tmp_path):
        """Test that description cannot be empty."""
        # Given: SKILL.md with empty description
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: test-skill
description: "   "
---
# Test
""")

        # When: we validate
        result = SkillValidator.validate(skill_dir)

        # Then: should fail
        assert result.valid is False
        assert any("description" in error.lower() and "empty" in error.lower() for error in result.errors)

    def test_validate_frontmatter_not_dict(self, tmp_path):
        """Test that frontmatter must be a YAML object (dict)."""
        # Given: SKILL.md with frontmatter that's not a dict
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
- just
- a
- list
---
# Test
""")

        # When: we validate
        result = SkillValidator.validate(skill_dir)

        # Then: should fail
        assert result.valid is False
        assert any("frontmatter" in error.lower() for error in result.errors)

    def test_validate_invalid_yaml_syntax(self, tmp_path):
        """Test that invalid YAML syntax is handled gracefully."""
        # Given: SKILL.md with invalid YAML in frontmatter
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: test-skill
description: "unterminated string
---
# Test
""")

        # When: we validate
        result = SkillValidator.validate(skill_dir)

        # Then: should fail
        assert result.valid is False
        assert any("frontmatter" in error.lower() for error in result.errors)
