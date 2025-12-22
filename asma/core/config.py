"""Configuration parser for skillset.yaml."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
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
    global_skills = []
    for skill_data in data.get("global", []):
        skill = Skill(**skill_data, scope=SkillScope.GLOBAL)
        global_skills.append(skill)

    # Parse project skills
    project_skills = []
    for skill_data in data.get("project", []):
        skill = Skill(**skill_data, scope=SkillScope.PROJECT)
        project_skills.append(skill)

    return Skillset(
        global_skills=global_skills,
        project_skills=project_skills,
        config=config
    )
