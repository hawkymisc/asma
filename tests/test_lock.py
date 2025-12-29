"""Tests for lock file functionality."""
import pytest
from pathlib import Path
from datetime import datetime
from asma.models.lock import LockEntry, Lockfile
from asma.models.skill import SkillScope


class TestLockEntry:
    """Test LockEntry model."""

    def test_create_lock_entry(self):
        """Test creating a lock entry with all fields."""
        # Given: lock entry data
        now = datetime.now()

        # When: we create a lock entry
        entry = LockEntry(
            name="test-skill",
            scope=SkillScope.GLOBAL,
            source="github:owner/repo",
            resolved_version="v1.0.0",
            resolved_commit="abc123def456",
            installed_at=now,
            checksum="sha256:test123"
        )

        # Then: all fields should be set
        assert entry.name == "test-skill"
        assert entry.scope == SkillScope.GLOBAL
        assert entry.source == "github:owner/repo"
        assert entry.resolved_version == "v1.0.0"
        assert entry.resolved_commit == "abc123def456"
        assert entry.installed_at == now
        assert entry.checksum == "sha256:test123"
        assert entry.symlink is False
        assert entry.resolved_path is None

    def test_lock_entry_to_dict(self):
        """Test converting lock entry to dictionary."""
        # Given: a lock entry
        now = datetime.now()
        entry = LockEntry(
            name="test-skill",
            scope=SkillScope.GLOBAL,
            source="github:owner/repo",
            resolved_version="v1.0.0",
            resolved_commit="abc123",
            installed_at=now,
            checksum="sha256:test",
            symlink=True,
            resolved_path="/path/to/skill"
        )

        # When: we convert to dict
        data = entry.to_dict()

        # Then: should have expected fields
        assert data["source"] == "github:owner/repo"
        assert data["resolved_version"] == "v1.0.0"
        assert data["resolved_commit"] == "abc123"
        assert data["installed_at"] == now.isoformat()
        assert data["checksum"] == "sha256:test"
        assert data["symlink"] is True
        assert data["resolved_path"] == "/path/to/skill"

    def test_lock_entry_from_dict(self):
        """Test creating lock entry from dictionary."""
        # Given: lock entry data as dict
        now = datetime.now()
        data = {
            "source": "github:owner/repo",
            "resolved_version": "v1.0.0",
            "resolved_commit": "abc123",
            "installed_at": now.isoformat(),
            "checksum": "sha256:test",
            "symlink": True,
            "resolved_path": "/path/to/skill"
        }

        # When: we create from dict
        entry = LockEntry.from_dict("test-skill", SkillScope.GLOBAL, data)

        # Then: should have all fields
        assert entry.name == "test-skill"
        assert entry.scope == SkillScope.GLOBAL
        assert entry.source == "github:owner/repo"
        assert entry.resolved_version == "v1.0.0"
        assert entry.installed_at == now
        assert entry.symlink is True


class TestLockfile:
    """Test Lockfile model."""

    def test_create_empty_lockfile(self):
        """Test creating an empty lockfile."""
        # When: we create a lockfile
        lockfile = Lockfile()

        # Then: should be empty
        assert lockfile.version == 1
        assert len(lockfile.skills) == 0
        assert lockfile.generated_at is not None

    def test_add_entry_to_lockfile(self):
        """Test adding an entry to lockfile."""
        # Given: a lockfile and entry
        lockfile = Lockfile()
        entry = LockEntry(
            name="test-skill",
            scope=SkillScope.GLOBAL,
            source="github:owner/repo",
            resolved_version="v1.0.0",
            resolved_commit="abc123",
            installed_at=datetime.now(),
            checksum="sha256:test"
        )

        # When: we add the entry
        lockfile.add_entry(entry)

        # Then: should be in lockfile
        assert len(lockfile.skills) == 1
        assert ("test-skill", SkillScope.GLOBAL) in lockfile.skills

    def test_get_entry_from_lockfile(self):
        """Test getting an entry from lockfile."""
        # Given: a lockfile with an entry
        lockfile = Lockfile()
        entry = LockEntry(
            name="test-skill",
            scope=SkillScope.GLOBAL,
            source="github:owner/repo",
            resolved_version="v1.0.0",
            resolved_commit="abc123",
            installed_at=datetime.now(),
            checksum="sha256:test"
        )
        lockfile.add_entry(entry)

        # When: we get the entry
        retrieved = lockfile.get_entry("test-skill", SkillScope.GLOBAL)

        # Then: should match original
        assert retrieved is not None
        assert retrieved.name == "test-skill"
        assert retrieved.resolved_version == "v1.0.0"

    def test_save_and_load_lockfile(self, tmp_path):
        """Test saving and loading lockfile."""
        # Given: a lockfile with entries
        lockfile = Lockfile()
        entry1 = LockEntry(
            name="skill1",
            scope=SkillScope.GLOBAL,
            source="github:owner/repo1",
            resolved_version="v1.0.0",
            resolved_commit="abc123",
            installed_at=datetime.now(),
            checksum="sha256:test1"
        )
        entry2 = LockEntry(
            name="skill2",
            scope=SkillScope.PROJECT,
            source="local:/path/to/skill",
            resolved_version="local@def456",
            resolved_commit="def456",
            installed_at=datetime.now(),
            checksum="sha256:test2",
            symlink=True,
            resolved_path="/path/to/skill"
        )
        lockfile.add_entry(entry1)
        lockfile.add_entry(entry2)

        lock_path = tmp_path / "skillset.lock"

        # When: we save the lockfile
        lockfile.save(lock_path)

        # Then: file should exist
        assert lock_path.exists()

        # When: we load it back
        loaded = Lockfile.load(lock_path)

        # Then: should have same entries
        assert len(loaded.skills) == 2
        assert loaded.get_entry("skill1", SkillScope.GLOBAL) is not None
        assert loaded.get_entry("skill2", SkillScope.PROJECT) is not None
        assert loaded.get_entry("skill2", SkillScope.PROJECT).symlink is True
