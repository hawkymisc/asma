"""Tests for skillset writer."""
import pytest
from pathlib import Path

from asma.core.skillset_writer import SkillsetWriter, SkillEntry
from asma.models.skill import SkillScope


class TestSkillEntry:
    """Test SkillEntry dataclass."""

    def test_skill_entry_required_fields(self):
        """Test creating SkillEntry with required fields only."""
        entry = SkillEntry(name="test-skill", source="github:owner/repo")

        assert entry.name == "test-skill"
        assert entry.source == "github:owner/repo"
        assert entry.version is None
        assert entry.ref is None

    def test_skill_entry_all_fields(self):
        """Test creating SkillEntry with all fields."""
        entry = SkillEntry(
            name="test-skill",
            source="github:owner/repo",
            version="v1.0.0",
            ref="main"
        )

        assert entry.name == "test-skill"
        assert entry.source == "github:owner/repo"
        assert entry.version == "v1.0.0"
        assert entry.ref == "main"


class TestSkillsetWriter:
    """Test SkillsetWriter class."""

    def test_load_raw_creates_empty_sections(self, tmp_path):
        """Test that load_raw creates empty sections if file doesn't exist."""
        skillset_path = tmp_path / "skillset.yaml"

        writer = SkillsetWriter(skillset_path)
        data = writer.load_raw()

        assert data["global"] == {}
        assert data["project"] == {}

    def test_load_raw_existing_file(self, tmp_path):
        """Test loading existing skillset.yaml."""
        skillset_path = tmp_path / "skillset.yaml"
        skillset_path.write_text("""
global:
  skill1:
    source: github:owner/repo
project:
  skill2:
    source: local:~/skills/local
""")

        writer = SkillsetWriter(skillset_path)
        data = writer.load_raw()

        assert "skill1" in data["global"]
        assert "skill2" in data["project"]

    def test_load_raw_adds_missing_sections(self, tmp_path):
        """Test that load_raw adds missing sections."""
        skillset_path = tmp_path / "skillset.yaml"
        skillset_path.write_text("""
global:
  skill1:
    source: github:owner/repo
""")

        writer = SkillsetWriter(skillset_path)
        data = writer.load_raw()

        assert "global" in data
        assert "project" in data
        assert data["project"] == {}

    def test_skill_exists_dict_format(self, tmp_path):
        """Test skill_exists with dict format skillset."""
        skillset_path = tmp_path / "skillset.yaml"
        skillset_path.write_text("""
global:
  existing-skill:
    source: github:owner/repo
project: {}
""")

        writer = SkillsetWriter(skillset_path)

        assert writer.skill_exists("existing-skill", SkillScope.GLOBAL) is True
        assert writer.skill_exists("nonexistent", SkillScope.GLOBAL) is False
        assert writer.skill_exists("existing-skill", SkillScope.PROJECT) is False

    def test_skill_exists_list_format(self, tmp_path):
        """Test skill_exists with list format skillset."""
        skillset_path = tmp_path / "skillset.yaml"
        skillset_path.write_text("""
global:
  - name: existing-skill
    source: github:owner/repo
project: []
""")

        writer = SkillsetWriter(skillset_path)

        assert writer.skill_exists("existing-skill", SkillScope.GLOBAL) is True
        assert writer.skill_exists("nonexistent", SkillScope.GLOBAL) is False

    def test_add_skill_to_empty_skillset(self, tmp_path):
        """Test adding skill to empty skillset.yaml."""
        skillset_path = tmp_path / "skillset.yaml"
        skillset_path.write_text("global: {}\nproject: {}")

        writer = SkillsetWriter(skillset_path)
        entry = SkillEntry(name="test-skill", source="github:owner/repo")

        writer.add_skill(entry, SkillScope.PROJECT)

        content = skillset_path.read_text()
        assert "test-skill" in content
        assert "github:owner/repo" in content

    def test_add_skill_to_project_scope(self, tmp_path):
        """Test adding skill to project scope."""
        skillset_path = tmp_path / "skillset.yaml"
        skillset_path.write_text("global: {}\nproject: {}")

        writer = SkillsetWriter(skillset_path)
        entry = SkillEntry(name="new-skill", source="github:owner/repo")

        writer.add_skill(entry, SkillScope.PROJECT)

        data = writer.load_raw()
        assert "new-skill" in data["project"]
        assert data["project"]["new-skill"]["source"] == "github:owner/repo"

    def test_add_skill_to_global_scope(self, tmp_path):
        """Test adding skill to global scope."""
        skillset_path = tmp_path / "skillset.yaml"
        skillset_path.write_text("global: {}\nproject: {}")

        writer = SkillsetWriter(skillset_path)
        entry = SkillEntry(name="global-skill", source="github:owner/repo")

        writer.add_skill(entry, SkillScope.GLOBAL)

        data = writer.load_raw()
        assert "global-skill" in data["global"]

    def test_add_skill_with_version(self, tmp_path):
        """Test adding skill with version."""
        skillset_path = tmp_path / "skillset.yaml"
        skillset_path.write_text("global: {}\nproject: {}")

        writer = SkillsetWriter(skillset_path)
        entry = SkillEntry(
            name="versioned-skill",
            source="github:owner/repo",
            version="v1.0.0"
        )

        writer.add_skill(entry, SkillScope.PROJECT)

        data = writer.load_raw()
        assert data["project"]["versioned-skill"]["version"] == "v1.0.0"

    def test_add_skill_with_ref(self, tmp_path):
        """Test adding skill with ref."""
        skillset_path = tmp_path / "skillset.yaml"
        skillset_path.write_text("global: {}\nproject: {}")

        writer = SkillsetWriter(skillset_path)
        entry = SkillEntry(
            name="ref-skill",
            source="github:owner/repo",
            ref="develop"
        )

        writer.add_skill(entry, SkillScope.PROJECT)

        data = writer.load_raw()
        assert data["project"]["ref-skill"]["ref"] == "develop"

    def test_add_existing_skill_raises_error(self, tmp_path):
        """Test adding existing skill raises error without force."""
        skillset_path = tmp_path / "skillset.yaml"
        skillset_path.write_text("""
global: {}
project:
  existing-skill:
    source: github:old/repo
""")

        writer = SkillsetWriter(skillset_path)
        entry = SkillEntry(name="existing-skill", source="github:new/repo")

        with pytest.raises(ValueError) as exc_info:
            writer.add_skill(entry, SkillScope.PROJECT)

        assert "already exists" in str(exc_info.value)
        assert "--force" in str(exc_info.value)

    def test_add_existing_skill_with_force(self, tmp_path):
        """Test adding existing skill with force flag."""
        skillset_path = tmp_path / "skillset.yaml"
        skillset_path.write_text("""
global: {}
project:
  existing-skill:
    source: github:old/repo
""")

        writer = SkillsetWriter(skillset_path)
        entry = SkillEntry(name="existing-skill", source="github:new/repo")

        writer.add_skill(entry, SkillScope.PROJECT, force=True)

        data = writer.load_raw()
        assert data["project"]["existing-skill"]["source"] == "github:new/repo"

    def test_add_skill_to_list_format(self, tmp_path):
        """Test adding skill to list format skillset."""
        skillset_path = tmp_path / "skillset.yaml"
        skillset_path.write_text("""
global: []
project:
  - name: existing-skill
    source: github:owner/existing
""")

        writer = SkillsetWriter(skillset_path)
        entry = SkillEntry(name="new-skill", source="github:owner/new")

        writer.add_skill(entry, SkillScope.PROJECT)

        data = writer.load_raw()
        assert isinstance(data["project"], list)
        assert len(data["project"]) == 2
        names = [s.get("name") for s in data["project"]]
        assert "existing-skill" in names
        assert "new-skill" in names

    def test_add_skill_preserves_config(self, tmp_path):
        """Test that adding skill preserves config section."""
        skillset_path = tmp_path / "skillset.yaml"
        skillset_path.write_text("""
config:
  auto_update: false
  parallel_downloads: 4

global: {}
project: {}
""")

        writer = SkillsetWriter(skillset_path)
        entry = SkillEntry(name="test-skill", source="github:owner/repo")

        writer.add_skill(entry, SkillScope.PROJECT)

        data = writer.load_raw()
        assert "config" in data
        assert data["config"]["auto_update"] is False
        assert data["config"]["parallel_downloads"] == 4

    def test_skill_exists_with_none_section(self, tmp_path):
        """Test skill_exists handles None section gracefully."""
        skillset_path = tmp_path / "skillset.yaml"
        skillset_path.write_text("""
global:
project:
""")

        writer = SkillsetWriter(skillset_path)
        assert writer.skill_exists("any-skill", SkillScope.GLOBAL) is False
        assert writer.skill_exists("any-skill", SkillScope.PROJECT) is False
