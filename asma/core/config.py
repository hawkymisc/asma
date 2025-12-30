"""Configuration parser for skillset.yaml."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional
import yaml

from asma.models.skill import Skill, SkillScope


@dataclass
class SkillsetConfig:
    """Global configuration from skillset.yaml."""

    auto_update: bool = False
    parallel_downloads: int = 4
    github_token_env: str = "GITHUB_TOKEN"
    cache_dir: Optional[Path] = None
    strict: bool = False

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not 1 <= self.parallel_downloads <= 10:
            raise ValueError("parallel_downloads must be between 1 and 10")

        # Set default cache_dir if not provided
        if self.cache_dir is None:
            self.cache_dir = Path.home() / ".asma/cache"
        elif isinstance(self.cache_dir, str):
            self.cache_dir = Path(self.cache_dir)


@dataclass
class Skillset:
    """Complete skillset.yaml representation."""

    global_skills: List[Skill] = field(default_factory=list)
    project_skills: List[Skill] = field(default_factory=list)
    config: SkillsetConfig = field(default_factory=SkillsetConfig)

    def get_skill(
        self,
        name: str,
        scope: Optional[SkillScope] = None
    ) -> Optional[Skill]:
        """
        Find skill by name and optional scope.

        Args:
            name: Skill name to search for
            scope: Optional scope filter (GLOBAL or PROJECT)

        Returns:
            Skill if found, None otherwise
        """
        candidates = []

        if scope in (None, SkillScope.GLOBAL):
            candidates.extend(self.global_skills)
        if scope in (None, SkillScope.PROJECT):
            candidates.extend(self.project_skills)

        for skill in candidates:
            if skill.name == name:
                return skill

        return None

    def all_skills(self) -> List[Skill]:
        """Get all skills (both scopes)."""
        return self.global_skills + self.project_skills


def _parse_skills_section(data: Any, section_name: str, scope: SkillScope) -> List[Skill]:
    """
    Parse a skills section (global or project) from skillset.yaml.

    Supports three formats:
    1. List format (block style):
       global:
         - name: skill1
           source: github:...
         - name: skill2
           source: github:...

    2. List format (flow style):
       global: [{name: skill1, source: "github:..."}, ...]

    3. Dict of dicts format (name as key):
       global:
         skill1:
           source: github:...
         skill2:
           source: github:...

    Args:
        data: The section data from YAML
        section_name: Name of the section (for error messages)
        scope: Skill scope (GLOBAL or PROJECT)

    Returns:
        List of parsed Skill objects

    Raises:
        ValueError: If using unsupported single-dict format
    """
    if data is None:
        return []

    skills = []

    # Format 1, 2: List of skill dicts
    if isinstance(data, list):
        for skill_data in data:
            skill = Skill(**skill_data, scope=scope)
            skills.append(skill)

    # Dict format - need to distinguish between dict-of-dicts and single-dict
    elif isinstance(data, dict):
        # Single-dict format (has 'name' key) - NOT supported
        if "name" in data:
            raise ValueError(
                f"Invalid format in '{section_name}' section: "
                f"single skill dict format is not supported. "
                f"Use list format (with '-') or dict-of-dicts format (skill name as key). "
                f"Example:\n"
                f"  {section_name}:\n"
                f"    - name: {data.get('name', 'my-skill')}\n"
                f"      source: {data.get('source', 'github:...')}\n"
                f"Or:\n"
                f"  {section_name}:\n"
                f"    {data.get('name', 'my-skill')}:\n"
                f"      source: {data.get('source', 'github:...')}"
            )

        # Format 3: Dict of dicts (skill name as key)
        for skill_name, skill_data in data.items():
            if not isinstance(skill_data, dict):
                raise ValueError(
                    f"Invalid skill definition for '{skill_name}' in '{section_name}': "
                    f"expected a dict, got {type(skill_data).__name__}"
                )
            skill = Skill(name=skill_name, **skill_data, scope=scope)
            skills.append(skill)

    else:
        raise ValueError(
            f"Invalid format in '{section_name}' section: "
            f"expected list or dict, got {type(data).__name__}"
        )

    return skills


def load_skillset(path: Path) -> Skillset:
    """
    Load and parse skillset.yaml file.

    Args:
        path: Path to skillset.yaml file

    Returns:
        Parsed Skillset object

    Raises:
        FileNotFoundError: If skillset.yaml doesn't exist
        yaml.YAMLError: If YAML syntax is invalid
        ValueError: If skill definitions are invalid
    """
    if not path.exists():
        raise FileNotFoundError(f"Skillset file not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    # Parse config
    config_data = data.get("config", {})
    config = SkillsetConfig(**config_data)

    # Parse global skills
    global_skills = _parse_skills_section(
        data.get("global"), "global", SkillScope.GLOBAL
    )

    # Parse project skills
    project_skills = _parse_skills_section(
        data.get("project"), "project", SkillScope.PROJECT
    )

    return Skillset(
        global_skills=global_skills,
        project_skills=project_skills,
        config=config
    )
