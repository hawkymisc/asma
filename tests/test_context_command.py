"""Tests for 'asma context' command."""
import json
import pytest
import yaml
from pathlib import Path
from click.testing import CliRunner
from datetime import datetime

from asma.cli.main import cli
from asma.models.lock import Lockfile, LockEntry
from asma.models.skill import SkillScope


class TestContextCommand:
    """Test 'asma context' command."""

    def test_context_no_lock_file(self):
        """Test context command when no lock file exists."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(cli, ['context'])

            assert result.exit_code != 0 or "not found" in result.output.lower()

    def test_context_text_format(self):
        """Test context command with default text format (basic fields only)."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            # Create skill directory with SKILL.md
            skill_dir = fs_path / ".claude/skills/test-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: A helpful test skill
author: Test Author
version: 1.0.0
---

# Test Skill
""")

            # Create lock file
            lockfile = Lockfile()
            lockfile.add_entry(LockEntry(
                name="test-skill",
                scope=SkillScope.PROJECT,
                source="local:/path",
                resolved_version="local@abc",
                resolved_commit="abc123",
                installed_at=datetime.now(),
                checksum="sha256:test",
            ))
            lockfile.save(fs_path / "skillset.lock")

            result = runner.invoke(cli, ['context'])

            assert result.exit_code == 0
            assert "test-skill" in result.output
            assert "A helpful test skill" in result.output
            # Default mode shows basic fields only (name, description, version)
            assert "author:" not in result.output

    def test_context_verbose_shows_all_fields(self):
        """Test context command with --verbose shows all fields."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            # Create skill directory with SKILL.md
            skill_dir = fs_path / ".claude/skills/test-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: A helpful test skill
author: Test Author
version: 1.0.0
---

# Test Skill
""")

            # Create lock file
            lockfile = Lockfile()
            lockfile.add_entry(LockEntry(
                name="test-skill",
                scope=SkillScope.PROJECT,
                source="local:/path",
                resolved_version="local@abc",
                resolved_commit="abc123",
                installed_at=datetime.now(),
                checksum="sha256:test",
            ))
            lockfile.save(fs_path / "skillset.lock")

            result = runner.invoke(cli, ['context', '--verbose'])

            assert result.exit_code == 0
            assert "test-skill" in result.output
            assert "A helpful test skill" in result.output
            assert "Test Author" in result.output

    def test_context_yaml_format(self):
        """Test context command with YAML format."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            # Create skill directory
            skill_dir = fs_path / ".claude/skills/test-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test description
version: 1.0.0
---
""")

            # Create lock file
            lockfile = Lockfile()
            lockfile.add_entry(LockEntry(
                name="test-skill",
                scope=SkillScope.PROJECT,
                source="local:/path",
                resolved_version="local@abc",
                resolved_commit="abc123",
                installed_at=datetime.now(),
                checksum="sha256:test",
            ))
            lockfile.save(fs_path / "skillset.lock")

            result = runner.invoke(cli, ['context', '--format', 'yaml'])

            assert result.exit_code == 0
            # Verify it's valid YAML
            data = yaml.safe_load(result.output)
            assert "project" in data
            assert "test-skill" in data["project"]
            assert data["project"]["test-skill"]["description"] == "Test description"

    def test_context_json_format(self):
        """Test context command with JSON format."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            # Create skill directory
            skill_dir = fs_path / ".claude/skills/test-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test description
---
""")

            # Create lock file
            lockfile = Lockfile()
            lockfile.add_entry(LockEntry(
                name="test-skill",
                scope=SkillScope.PROJECT,
                source="local:/path",
                resolved_version="local@abc",
                resolved_commit="abc123",
                installed_at=datetime.now(),
                checksum="sha256:test",
            ))
            lockfile.save(fs_path / "skillset.lock")

            result = runner.invoke(cli, ['context', '--format', 'json'])

            assert result.exit_code == 0
            # Verify it's valid JSON
            data = json.loads(result.output)
            assert "project" in data
            assert "test-skill" in data["project"]

    def test_context_specific_skill(self):
        """Test context command for a specific skill."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            # Create two skills
            for skill_name in ["skill1", "skill2"]:
                skill_dir = fs_path / f".claude/skills/{skill_name}"
                skill_dir.mkdir(parents=True)
                (skill_dir / "SKILL.md").write_text(f"""---
name: {skill_name}
description: Description for {skill_name}
---
""")

            # Create lock file with both skills
            lockfile = Lockfile()
            for skill_name in ["skill1", "skill2"]:
                lockfile.add_entry(LockEntry(
                    name=skill_name,
                    scope=SkillScope.PROJECT,
                    source="local:/path",
                    resolved_version="local@abc",
                    resolved_commit="abc123",
                    installed_at=datetime.now(),
                    checksum="sha256:test",
                ))
            lockfile.save(fs_path / "skillset.lock")

            result = runner.invoke(cli, ['context', 'skill1'])

            assert result.exit_code == 0
            assert "skill1" in result.output
            assert "skill2" not in result.output

    def test_context_scope_filter(self):
        """Test context command with --scope filter."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            # Create project skill only (global skill would be in home dir)
            skill_dir = fs_path / ".claude/skills/project-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("""---
name: project-skill
description: Project skill
---
""")

            # Create lock file with both scopes
            lockfile = Lockfile()
            lockfile.add_entry(LockEntry(
                name="global-skill",
                scope=SkillScope.GLOBAL,
                source="github:owner/repo",
                resolved_version="v1.0.0",
                resolved_commit="abc123",
                installed_at=datetime.now(),
                checksum="sha256:test1",
            ))
            lockfile.add_entry(LockEntry(
                name="project-skill",
                scope=SkillScope.PROJECT,
                source="local:/path",
                resolved_version="local@def",
                resolved_commit="def456",
                installed_at=datetime.now(),
                checksum="sha256:test2",
            ))
            lockfile.save(fs_path / "skillset.lock")

            result = runner.invoke(cli, ['context', '--scope', 'project'])

            assert result.exit_code == 0
            assert "project-skill" in result.output
            # Global skill should not appear
            assert "global-skill" not in result.output

    def test_context_missing_skill_shows_error(self):
        """Test context command shows error for missing skill."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            # Create lock file without creating skill directory
            lockfile = Lockfile()
            lockfile.add_entry(LockEntry(
                name="missing-skill",
                scope=SkillScope.PROJECT,
                source="local:/path",
                resolved_version="local@abc",
                resolved_commit="abc123",
                installed_at=datetime.now(),
                checksum="sha256:test",
            ))
            lockfile.save(fs_path / "skillset.lock")

            result = runner.invoke(cli, ['context'])

            assert result.exit_code == 0  # Should still succeed but show error
            assert "missing-skill" in result.output
            assert "error" in result.output.lower() or "not found" in result.output.lower()

    def test_context_empty_lock_file(self):
        """Test context command with empty lock file."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            # Create empty lock file
            lockfile = Lockfile()
            lockfile.save(fs_path / "skillset.lock")

            result = runner.invoke(cli, ['context'])

            assert result.exit_code == 0
            assert "No skills" in result.output or "{}" in result.output or "global" in result.output.lower()
