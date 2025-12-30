"""Skillset.yaml writer for adding and updating skills."""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from asma.models.skill import SkillScope


@dataclass
class SkillEntry:
    """Skill entry to add to skillset.yaml."""

    name: str
    source: str
    version: Optional[str] = None
    ref: Optional[str] = None


class SkillsetWriter:
    """Writer for skillset.yaml files."""

    def __init__(self, skillset_path: Path):
        """
        Initialize skillset writer.

        Args:
            skillset_path: Path to skillset.yaml file
        """
        self.skillset_path = skillset_path

    def load_raw(self) -> Dict[str, Any]:
        """
        Load raw YAML data from skillset.yaml.

        Returns:
            Dict containing raw YAML data with global and project sections
        """
        if not self.skillset_path.exists():
            return {"global": {}, "project": {}}

        with open(self.skillset_path) as f:
            data = yaml.safe_load(f) or {}

        # Ensure sections exist
        if "global" not in data:
            data["global"] = {}
        if "project" not in data:
            data["project"] = {}

        return data

    def skill_exists(self, name: str, scope: SkillScope) -> bool:
        """
        Check if a skill already exists in the skillset.

        Args:
            name: Skill name to check
            scope: Scope to check (GLOBAL or PROJECT)

        Returns:
            True if skill exists, False otherwise
        """
        data = self.load_raw()
        section = data.get(scope.value, {})

        if section is None:
            return False

        # Handle both list and dict formats
        if isinstance(section, list):
            return any(
                s.get("name") == name for s in section if isinstance(s, dict)
            )
        elif isinstance(section, dict):
            return name in section

        return False

    def add_skill(
        self,
        entry: SkillEntry,
        scope: SkillScope,
        force: bool = False
    ) -> None:
        """
        Add a skill to skillset.yaml.

        Args:
            entry: Skill entry to add
            scope: Scope (GLOBAL or PROJECT)
            force: Overwrite if exists

        Raises:
            ValueError: If skill exists and force=False
        """
        data = self.load_raw()
        section_key = scope.value

        # Check if skill exists
        if self.skill_exists(entry.name, scope) and not force:
            raise ValueError(
                f"Skill '{entry.name}' already exists in {scope.value} scope. "
                f"Use --force to overwrite."
            )

        # Build skill data
        skill_data: Dict[str, Any] = {"source": entry.source}
        if entry.version:
            skill_data["version"] = entry.version
        if entry.ref:
            skill_data["ref"] = entry.ref

        # Handle different section formats
        section = data.get(section_key)

        if section is None:
            # Initialize as dict
            section = {entry.name: skill_data}
        elif isinstance(section, list):
            # List format: remove existing and append
            section = [
                s for s in section
                if isinstance(s, dict) and s.get("name") != entry.name
            ]
            section.append({"name": entry.name, **skill_data})
        elif isinstance(section, dict):
            # Dict format: add/update entry
            section[entry.name] = skill_data
        else:
            # Initialize as dict if invalid type
            section = {entry.name: skill_data}

        data[section_key] = section

        # Write back to file
        self.save(data)

    def save(self, data: Dict[str, Any]) -> None:
        """
        Save data to skillset.yaml with proper formatting.

        Args:
            data: Data to write to skillset.yaml
        """
        with open(self.skillset_path, 'w') as f:
            yaml.safe_dump(
                data,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True
            )
