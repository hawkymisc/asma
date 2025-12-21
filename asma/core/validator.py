"""SKILL.md validator for validating skill structure and metadata."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional
import re
import yaml


@dataclass
class ValidationResult:
    """Result of skill validation."""

    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SkillValidator:
    """Validator for SKILL.md files."""

    @staticmethod
    def validate(skill_path: Path, strict: bool = False) -> ValidationResult:
        """
        Validate a skill directory and its SKILL.md file.

        Args:
            skill_path: Path to the skill directory
            strict: Enable strict validation mode

        Returns:
            ValidationResult with validation status and any errors/warnings
        """
        skill_md = skill_path / "SKILL.md"
        errors = []

        # Check if SKILL.md exists
        if not skill_md.exists():
            errors.append("SKILL.md not found")
            return ValidationResult(valid=False, errors=errors)

        # Read and parse frontmatter
        content = skill_md.read_text()
        frontmatter = SkillValidator._parse_frontmatter(content)

        if frontmatter is None:
            errors.append("SKILL.md missing YAML frontmatter")
            return ValidationResult(valid=False, errors=errors)

        # Validate required fields
        if "name" not in frontmatter:
            errors.append("SKILL.md missing required field: name")
        elif not isinstance(frontmatter["name"], str):
            errors.append("SKILL.md field 'name' must be a string")
        elif not re.match(r'^[a-z0-9-]{1,64}$', frontmatter["name"]):
            errors.append(f"Invalid name format: {frontmatter['name']} (must be lowercase letters, numbers, and hyphens only)")

        if "description" not in frontmatter:
            errors.append("SKILL.md missing required field: description")
        elif not isinstance(frontmatter["description"], str):
            errors.append("SKILL.md field 'description' must be a string")
        elif not frontmatter["description"].strip():
            errors.append("SKILL.md field 'description' is empty")

        valid = len(errors) == 0
        return ValidationResult(valid=valid, errors=errors, metadata=frontmatter)

    @staticmethod
    def _parse_frontmatter(content: str) -> Optional[Dict[str, Any]]:
        """
        Extract YAML frontmatter from markdown content.

        Args:
            content: Markdown file content

        Returns:
            Parsed frontmatter as dict, or None if not found/invalid
        """
        # Match frontmatter between --- delimiters
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if not match:
            return None

        try:
            return yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            return None
