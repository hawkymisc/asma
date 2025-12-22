"""Tests for skillset.yaml configuration parser."""
import pytest
from pathlib import Path
from asma.core.config import SkillsetConfig, Skillset, load_skillset
from asma.models.skill import SkillScope


class TestSkillsetConfig:
    """Test SkillsetConfig model."""

    def test_default_config(self):
        """Test that default config has sensible defaults."""
        # Given/When: create default config
        config = SkillsetConfig()

        # Then: should have expected defaults
        assert config.auto_update is False
        assert config.parallel_downloads == 4
        assert config.github_token_env == "GITHUB_TOKEN"
        assert config.strict is False

    def test_config_parallel_downloads_validation(self):
        """Test that parallel_downloads must be between 1 and 10."""
        # Given: invalid parallel_downloads values
        # When/Then: should raise ValueError
        with pytest.raises(ValueError, match="parallel_downloads must be between 1 and 10"):
            SkillsetConfig(parallel_downloads=0)

        with pytest.raises(ValueError, match="parallel_downloads must be between 1 and 10"):
            SkillsetConfig(parallel_downloads=11)

        # Valid values should work
        config = SkillsetConfig(parallel_downloads=1)
        assert config.parallel_downloads == 1

        config = SkillsetConfig(parallel_downloads=10)
        assert config.parallel_downloads == 10


class TestSkillset:
    """Test Skillset model."""

    def test_load_minimal_skillset(self, tmp_path):
        """Test loading a minimal valid skillset.yaml."""
        # Given: minimal skillset.yaml
        skillset_file = tmp_path / "skillset.yaml"
        skillset_file.write_text("""
global:
  - name: test-skill
    source: github:test/repo
""")

        # When: we load the skillset
        skillset = load_skillset(skillset_file)

        # Then: should parse correctly
        assert len(skillset.global_skills) == 1
        assert len(skillset.project_skills) == 0
        assert skillset.global_skills[0].name == "test-skill"
        assert skillset.global_skills[0].source == "github:test/repo"
        assert skillset.global_skills[0].scope == SkillScope.GLOBAL

    def test_load_complete_skillset(self, tmp_path):
        """Test loading a complete skillset.yaml with all features."""
        # Given: complete skillset.yaml
        skillset_file = tmp_path / "skillset.yaml"
        skillset_file.write_text("""
config:
  auto_update: true
  parallel_downloads: 8
  github_token_env: MY_GITHUB_TOKEN
  strict: true

global:
  - name: skill1
    source: github:user/repo1
    version: v1.0.0

  - name: skill2
    source: github:user/repo2
    ref: main
    enabled: false

  - name: skill3
    source: local:~/my-skills/skill3
    alias: custom-name

project:
  - name: project-skill
    source: github:company/repo
    version: v2.1.0
""")

        # When: we load the skillset
        skillset = load_skillset(skillset_file)

        # Then: config should be parsed
        assert skillset.config.auto_update is True
        assert skillset.config.parallel_downloads == 8
        assert skillset.config.github_token_env == "MY_GITHUB_TOKEN"
        assert skillset.config.strict is True

        # And: global skills should be parsed
        assert len(skillset.global_skills) == 3
        assert skillset.global_skills[0].name == "skill1"
        assert skillset.global_skills[0].version == "v1.0.0"
        assert skillset.global_skills[1].enabled is False
        assert skillset.global_skills[2].alias == "custom-name"

        # And: project skills should be parsed
        assert len(skillset.project_skills) == 1
        assert skillset.project_skills[0].scope == SkillScope.PROJECT

    def test_load_skillset_empty_file(self, tmp_path):
        """Test loading an empty skillset.yaml."""
        # Given: empty skillset.yaml
        skillset_file = tmp_path / "skillset.yaml"
        skillset_file.write_text("")

        # When: we load the skillset
        skillset = load_skillset(skillset_file)

        # Then: should have no skills but valid config
        assert len(skillset.global_skills) == 0
        assert len(skillset.project_skills) == 0
        assert skillset.config.auto_update is False  # defaults

    def test_load_skillset_file_not_found(self, tmp_path):
        """Test loading non-existent skillset.yaml."""
        # Given: non-existent file
        skillset_file = tmp_path / "nonexistent.yaml"

        # When/Then: should raise FileNotFoundError
        with pytest.raises(FileNotFoundError):
            load_skillset(skillset_file)

    def test_get_skill_by_name(self, tmp_path):
        """Test finding a skill by name."""
        # Given: skillset with multiple skills
        skillset_file = tmp_path / "skillset.yaml"
        skillset_file.write_text("""
global:
  - name: global-skill
    source: github:test/global

project:
  - name: project-skill
    source: github:test/project
""")
        skillset = load_skillset(skillset_file)

        # When: we search for skills by name
        global_skill = skillset.get_skill("global-skill")
        project_skill = skillset.get_skill("project-skill")
        missing_skill = skillset.get_skill("missing")

        # Then: should find existing skills
        assert global_skill is not None
        assert global_skill.name == "global-skill"
        assert project_skill is not None
        assert project_skill.name == "project-skill"
        assert missing_skill is None

    def test_get_skill_by_name_and_scope(self, tmp_path):
        """Test finding a skill by name with scope filter."""
        # Given: skillset
        skillset_file = tmp_path / "skillset.yaml"
        skillset_file.write_text("""
global:
  - name: shared-name
    source: github:test/global

project:
  - name: shared-name
    source: github:test/project
""")
        skillset = load_skillset(skillset_file)

        # When: we search with scope
        global_skill = skillset.get_skill("shared-name", scope=SkillScope.GLOBAL)
        project_skill = skillset.get_skill("shared-name", scope=SkillScope.PROJECT)

        # Then: should find correct scoped skills
        assert global_skill.source == "github:test/global"
        assert project_skill.source == "github:test/project"

    def test_all_skills(self, tmp_path):
        """Test getting all skills regardless of scope."""
        # Given: skillset with global and project skills
        skillset_file = tmp_path / "skillset.yaml"
        skillset_file.write_text("""
global:
  - name: skill1
    source: github:test/1
  - name: skill2
    source: github:test/2

project:
  - name: skill3
    source: github:test/3
""")
        skillset = load_skillset(skillset_file)

        # When: we get all skills
        all_skills = skillset.all_skills()

        # Then: should return all 3 skills
        assert len(all_skills) == 3
        names = [s.name for s in all_skills]
        assert "skill1" in names
        assert "skill2" in names
        assert "skill3" in names
