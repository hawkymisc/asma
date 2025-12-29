"""Tests for 'asma list' command."""
import pytest
from pathlib import Path
from click.testing import CliRunner
from asma.cli.main import cli
from asma.models.lock import Lockfile, LockEntry
from asma.models.skill import SkillScope
from datetime import datetime


class TestListCommand:
    """Test 'asma list' command."""

    def test_list_with_no_lock_file(self):
        """Test list command when no lock file exists."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # When: we run list without a lock file
            result = runner.invoke(cli, ['list'])

            # Then: should show message
            assert result.exit_code == 0
            assert "No skills installed" in result.output or "skillset.lock not found" in result.output

    def test_list_shows_installed_skills(self):
        """Test that list command shows installed skills from lock file."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            # Given: a lock file with skills
            lockfile = Lockfile()
            lockfile.add_entry(LockEntry(
                name="skill1",
                scope=SkillScope.GLOBAL,
                source="github:owner/repo",
                resolved_version="v1.0.0",
                resolved_commit="abc123",
                installed_at=datetime.now(),
                checksum="sha256:test1"
            ))
            lockfile.add_entry(LockEntry(
                name="skill2",
                scope=SkillScope.PROJECT,
                source="local:/path/to/skill",
                resolved_version="local@def456",
                resolved_commit="def456",
                installed_at=datetime.now(),
                checksum="sha256:test2",
                symlink=True
            ))
            lockfile.save(fs_path / "skillset.lock")

            # When: we run list
            result = runner.invoke(cli, ['list'])

            # Then: should show both skills
            assert result.exit_code == 0
            assert "skill1" in result.output
            assert "skill2" in result.output
            assert "Global" in result.output or "global" in result.output
            assert "Project" in result.output or "project" in result.output

    def test_list_scope_global(self):
        """Test list command with --scope global."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            # Given: a lock file with both global and project skills
            lockfile = Lockfile()
            lockfile.add_entry(LockEntry(
                name="global-skill",
                scope=SkillScope.GLOBAL,
                source="github:owner/repo",
                resolved_version="v1.0.0",
                resolved_commit="abc123",
                installed_at=datetime.now(),
                checksum="sha256:test1"
            ))
            lockfile.add_entry(LockEntry(
                name="project-skill",
                scope=SkillScope.PROJECT,
                source="local:/path",
                resolved_version="local@def",
                resolved_commit="def456",
                installed_at=datetime.now(),
                checksum="sha256:test2"
            ))
            lockfile.save(fs_path / "skillset.lock")

            # When: we run list --scope global
            result = runner.invoke(cli, ['list', '--scope', 'global'])

            # Then: should only show global skill
            assert result.exit_code == 0
            assert "global-skill" in result.output
            assert "project-skill" not in result.output

    def test_list_scope_project(self):
        """Test list command with --scope project."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            # Given: a lock file with both scopes
            lockfile = Lockfile()
            lockfile.add_entry(LockEntry(
                name="global-skill",
                scope=SkillScope.GLOBAL,
                source="github:owner/repo",
                resolved_version="v1.0.0",
                resolved_commit="abc123",
                installed_at=datetime.now(),
                checksum="sha256:test1"
            ))
            lockfile.add_entry(LockEntry(
                name="project-skill",
                scope=SkillScope.PROJECT,
                source="local:/path",
                resolved_version="local@def",
                resolved_commit="def456",
                installed_at=datetime.now(),
                checksum="sha256:test2"
            ))
            lockfile.save(fs_path / "skillset.lock")

            # When: we run list --scope project
            result = runner.invoke(cli, ['list', '--scope', 'project'])

            # Then: should only show project skill
            assert result.exit_code == 0
            assert "project-skill" in result.output
            assert "global-skill" not in result.output

    def test_list_empty_lock_file(self):
        """Test list command with empty lock file."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            # Given: an empty lock file
            lockfile = Lockfile()
            lockfile.save(fs_path / "skillset.lock")

            # When: we run list
            result = runner.invoke(cli, ['list'])

            # Then: should show no skills message
            assert result.exit_code == 0
            assert "No skills installed" in result.output or "0" in result.output
