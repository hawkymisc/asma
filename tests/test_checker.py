"""Tests for skill checker module."""
import pytest
from pathlib import Path
from datetime import datetime

from asma.core.checker import SkillChecker, CheckResult
from asma.models.lock import LockEntry
from asma.models.skill import SkillScope


class TestCheckResult:
    """Tests for CheckResult dataclass."""

    def test_check_result_ok(self):
        """Test creating an OK result."""
        result = CheckResult(
            skill_name="test-skill",
            scope=SkillScope.GLOBAL,
            status="ok",
            expected_path=Path("/home/user/.claude/skills/test-skill"),
        )
        assert result.status == "ok"
        assert result.skill_name == "test-skill"
        assert result.error_message is None

    def test_check_result_missing(self):
        """Test creating a missing result."""
        result = CheckResult(
            skill_name="test-skill",
            scope=SkillScope.PROJECT,
            status="missing",
            expected_path=Path(".claude/skills/test-skill"),
            error_message="Directory not found",
        )
        assert result.status == "missing"
        assert result.error_message == "Directory not found"

    def test_check_result_checksum_mismatch(self):
        """Test creating a checksum mismatch result."""
        result = CheckResult(
            skill_name="test-skill",
            scope=SkillScope.GLOBAL,
            status="checksum_mismatch",
            expected_path=Path("/home/user/.claude/skills/test-skill"),
            expected_checksum="sha256:abc123",
            actual_checksum="sha256:def456",
        )
        assert result.status == "checksum_mismatch"
        assert result.expected_checksum != result.actual_checksum


class TestSkillChecker:
    """Tests for SkillChecker class."""

    @pytest.fixture
    def checker(self):
        """Create a SkillChecker instance."""
        return SkillChecker()

    @pytest.fixture
    def sample_lock_entry(self, tmp_path):
        """Create a sample lock entry."""
        return LockEntry(
            name="test-skill",
            scope=SkillScope.PROJECT,
            source="local:/path/to/skill",
            resolved_version="local@abc123",
            resolved_commit="abc123def456",
            installed_at=datetime.now(),
            checksum="sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
            symlink=False,
        )

    def test_get_install_path_global(self, checker):
        """Test getting install path for global scope."""
        entry = LockEntry(
            name="my-skill",
            scope=SkillScope.GLOBAL,
            source="github:owner/repo",
            resolved_version="v1.0.0",
            resolved_commit="abc123",
            installed_at=datetime.now(),
            checksum="sha256:test",
        )
        path = checker.get_install_path(entry)
        assert path == Path.home() / ".claude/skills/my-skill"

    def test_get_install_path_project(self, checker):
        """Test getting install path for project scope."""
        entry = LockEntry(
            name="my-skill",
            scope=SkillScope.PROJECT,
            source="local:/path",
            resolved_version="local@abc",
            resolved_commit="abc123",
            installed_at=datetime.now(),
            checksum="sha256:test",
        )
        path = checker.get_install_path(entry)
        assert path == Path.cwd() / ".claude/skills/my-skill"

    def test_check_skill_exists(self, checker, tmp_path):
        """Test checking a skill that exists."""
        # Create skill directory with SKILL.md
        skill_dir = tmp_path / ".claude/skills/test-skill"
        skill_dir.mkdir(parents=True)
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: test-skill
description: Test skill
---
# Test
""")

        entry = LockEntry(
            name="test-skill",
            scope=SkillScope.PROJECT,
            source="local:/path",
            resolved_version="local@abc",
            resolved_commit="abc123",
            installed_at=datetime.now(),
            checksum="sha256:test",
        )

        result = checker.check_skill(entry, base_path=tmp_path)
        assert result.status == "ok"

    def test_check_skill_missing(self, checker, tmp_path):
        """Test checking a skill that doesn't exist."""
        entry = LockEntry(
            name="missing-skill",
            scope=SkillScope.PROJECT,
            source="local:/path",
            resolved_version="local@abc",
            resolved_commit="abc123",
            installed_at=datetime.now(),
            checksum="sha256:test",
        )

        result = checker.check_skill(entry, base_path=tmp_path)
        assert result.status == "missing"
        assert "not found" in result.error_message.lower()

    def test_check_skill_broken_symlink(self, checker, tmp_path):
        """Test checking a skill with broken symlink."""
        # Create parent directory
        skills_dir = tmp_path / ".claude/skills"
        skills_dir.mkdir(parents=True)

        # Create broken symlink
        skill_link = skills_dir / "broken-skill"
        skill_link.symlink_to("/nonexistent/path")

        entry = LockEntry(
            name="broken-skill",
            scope=SkillScope.PROJECT,
            source="local:/nonexistent/path",
            resolved_version="local@abc",
            resolved_commit="abc123",
            installed_at=datetime.now(),
            checksum="sha256:test",
            symlink=True,
        )

        result = checker.check_skill(entry, base_path=tmp_path)
        assert result.status == "broken_symlink"

    def test_check_skill_checksum_match(self, checker, tmp_path):
        """Test checking a skill with matching checksum."""
        import hashlib

        # Create skill directory with SKILL.md
        skill_dir = tmp_path / ".claude/skills/test-skill"
        skill_dir.mkdir(parents=True)
        skill_content = """---
name: test-skill
description: Test skill
---
# Test
"""
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(skill_content)

        # Calculate expected checksum
        expected_checksum = "sha256:" + hashlib.sha256(skill_content.encode()).hexdigest()

        entry = LockEntry(
            name="test-skill",
            scope=SkillScope.PROJECT,
            source="local:/path",
            resolved_version="local@abc",
            resolved_commit="abc123",
            installed_at=datetime.now(),
            checksum=expected_checksum,
        )

        result = checker.check_skill(entry, base_path=tmp_path, verify_checksum=True)
        assert result.status == "ok"

    def test_check_skill_checksum_mismatch(self, checker, tmp_path):
        """Test checking a skill with mismatched checksum."""
        # Create skill directory with SKILL.md
        skill_dir = tmp_path / ".claude/skills/test-skill"
        skill_dir.mkdir(parents=True)
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""---
name: test-skill
description: Test skill
---
# Test
""")

        entry = LockEntry(
            name="test-skill",
            scope=SkillScope.PROJECT,
            source="local:/path",
            resolved_version="local@abc",
            resolved_commit="abc123",
            installed_at=datetime.now(),
            checksum="sha256:wrongchecksum123",
        )

        result = checker.check_skill(entry, base_path=tmp_path, verify_checksum=True)
        assert result.status == "checksum_mismatch"
        assert result.expected_checksum == "sha256:wrongchecksum123"
        assert result.actual_checksum is not None
        assert result.actual_checksum != result.expected_checksum

    def test_calculate_checksum(self, checker, tmp_path):
        """Test checksum calculation."""
        import hashlib

        content = "test content"
        test_file = tmp_path / "test.md"
        test_file.write_text(content)

        expected = "sha256:" + hashlib.sha256(content.encode()).hexdigest()
        actual = checker.calculate_checksum(test_file)

        assert actual == expected
