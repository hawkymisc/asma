"""Tests for 'asma check' command."""
import pytest
from pathlib import Path
from click.testing import CliRunner
from datetime import datetime
import hashlib

from asma.cli.main import cli
from asma.models.lock import Lockfile, LockEntry
from asma.models.skill import SkillScope


class TestCheckCommand:
    """Test 'asma check' command."""

    def test_check_no_lock_file(self):
        """Test check command when no lock file exists."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(cli, ['check'])

            assert result.exit_code == 2
            assert "skillset.lock not found" in result.output.lower() or "no skills" in result.output.lower()

    def test_check_all_skills_present(self):
        """Test check command when all skills are installed."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            # Create skill directory with SKILL.md
            skill_dir = fs_path / ".claude/skills/test-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test
---
# Test
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

            result = runner.invoke(cli, ['check'])

            assert result.exit_code == 0
            assert "test-skill" in result.output
            assert "OK" in result.output or "✓" in result.output

    def test_check_missing_skill(self):
        """Test check command when a skill is missing."""
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

            result = runner.invoke(cli, ['check'])

            assert result.exit_code == 1
            assert "missing-skill" in result.output
            assert "not found" in result.output.lower() or "✗" in result.output

    def test_check_with_checksum_match(self):
        """Test check command with --checksum when checksum matches."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            # Create skill directory with SKILL.md
            skill_dir = fs_path / ".claude/skills/test-skill"
            skill_dir.mkdir(parents=True)
            content = """---
name: test-skill
description: Test
---
# Test
"""
            (skill_dir / "SKILL.md").write_text(content)

            # Calculate correct checksum
            checksum = "sha256:" + hashlib.sha256(content.encode()).hexdigest()

            # Create lock file with matching checksum
            lockfile = Lockfile()
            lockfile.add_entry(LockEntry(
                name="test-skill",
                scope=SkillScope.PROJECT,
                source="local:/path",
                resolved_version="local@abc",
                resolved_commit="abc123",
                installed_at=datetime.now(),
                checksum=checksum,
            ))
            lockfile.save(fs_path / "skillset.lock")

            result = runner.invoke(cli, ['check', '--checksum'])

            assert result.exit_code == 0
            assert "test-skill" in result.output

    def test_check_with_checksum_mismatch(self):
        """Test check command with --checksum when checksum doesn't match."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            # Create skill directory with SKILL.md
            skill_dir = fs_path / ".claude/skills/test-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test
---
# Test
""")

            # Create lock file with wrong checksum
            lockfile = Lockfile()
            lockfile.add_entry(LockEntry(
                name="test-skill",
                scope=SkillScope.PROJECT,
                source="local:/path",
                resolved_version="local@abc",
                resolved_commit="abc123",
                installed_at=datetime.now(),
                checksum="sha256:wrongchecksum",
            ))
            lockfile.save(fs_path / "skillset.lock")

            result = runner.invoke(cli, ['check', '--checksum'])

            assert result.exit_code == 1
            assert "test-skill" in result.output
            assert "mismatch" in result.output.lower() or "!" in result.output

    def test_check_scope_filter(self):
        """Test check command with --scope filter."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            # Create project skill only
            skill_dir = fs_path / ".claude/skills/project-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("""---
name: project-skill
description: Test
---
""")

            # Create lock file with both global and project skills
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

            # Check only project scope
            result = runner.invoke(cli, ['check', '--scope', 'project'])

            assert result.exit_code == 0
            assert "project-skill" in result.output
            # Global skill should not be checked
            assert "global-skill" not in result.output or "1/1" in result.output

    def test_check_quiet_mode(self):
        """Test check command with --quiet flag."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            # Create skill
            skill_dir = fs_path / ".claude/skills/test-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test
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

            result = runner.invoke(cli, ['check', '--quiet'])

            # Quiet mode should have minimal output when everything is OK
            assert result.exit_code == 0
            # Output should be minimal or empty
            assert len(result.output.strip()) < 100 or "OK" in result.output

    def test_check_quiet_mode_with_error(self):
        """Test check command with --quiet shows errors."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            # Create lock file without skill
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

            result = runner.invoke(cli, ['check', '--quiet'])

            # Should still show errors even in quiet mode
            assert result.exit_code == 1
            assert "missing-skill" in result.output

    def test_check_multiple_skills_mixed_status(self):
        """Test check command with multiple skills having different statuses."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            # Create only one skill
            skill_dir = fs_path / ".claude/skills/present-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("""---
name: present-skill
description: Test
---
""")

            # Create lock file with two skills
            lockfile = Lockfile()
            lockfile.add_entry(LockEntry(
                name="present-skill",
                scope=SkillScope.PROJECT,
                source="local:/path1",
                resolved_version="local@abc",
                resolved_commit="abc123",
                installed_at=datetime.now(),
                checksum="sha256:test1",
            ))
            lockfile.add_entry(LockEntry(
                name="missing-skill",
                scope=SkillScope.PROJECT,
                source="local:/path2",
                resolved_version="local@def",
                resolved_commit="def456",
                installed_at=datetime.now(),
                checksum="sha256:test2",
            ))
            lockfile.save(fs_path / "skillset.lock")

            result = runner.invoke(cli, ['check'])

            # Should fail because one skill is missing
            assert result.exit_code == 1
            assert "present-skill" in result.output
            assert "missing-skill" in result.output
            # Should show summary
            assert "1/2" in result.output or "1 " in result.output
