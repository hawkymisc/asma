"""Tests for skill fetcher."""
import io
import tarfile
import pytest
from pathlib import Path

from asma.core.skill_fetcher import SkillFetcher, FetchResult


class TestFetchResult:
    """Test FetchResult dataclass."""

    def test_fetch_result_success(self):
        """Test creating successful FetchResult."""
        result = FetchResult(
            success=True,
            name="test-skill",
            description="A test skill",
            metadata={"name": "test-skill", "description": "A test skill"},
            version="v1.0.0"
        )

        assert result.success is True
        assert result.name == "test-skill"
        assert result.description == "A test skill"
        assert result.error is None

    def test_fetch_result_failure(self):
        """Test creating failed FetchResult."""
        result = FetchResult(
            success=False,
            error="Source not found"
        )

        assert result.success is False
        assert result.error == "Source not found"
        assert result.name is None

    def test_fetch_result_default_metadata(self):
        """Test that metadata defaults to empty dict."""
        result = FetchResult(success=True)

        assert result.metadata == {}


class TestSkillFetcher:
    """Test SkillFetcher class."""

    def test_get_source_handler_local(self):
        """Test getting LocalSourceHandler for local: source."""
        fetcher = SkillFetcher()
        handler = fetcher.get_source_handler("local:/path/to/skill")

        from asma.core.sources.local import LocalSourceHandler
        assert isinstance(handler, LocalSourceHandler)

    def test_get_source_handler_github(self):
        """Test getting GitHubSourceHandler for github: source."""
        fetcher = SkillFetcher(github_token="test-token")
        handler = fetcher.get_source_handler("github:owner/repo")

        from asma.core.sources.github import GitHubSourceHandler
        assert isinstance(handler, GitHubSourceHandler)

    def test_get_source_handler_unsupported(self):
        """Test that unsupported source raises ValueError."""
        fetcher = SkillFetcher()

        with pytest.raises(ValueError) as exc_info:
            fetcher.get_source_handler("unknown:source")

        assert "Unsupported source type" in str(exc_info.value)

    def test_fetch_local_skill(self, tmp_path):
        """Test fetching metadata from local skill."""
        # Create local skill
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: local-test-skill
description: A local test skill for testing
---
# Local Test Skill

Instructions for using this skill.
""")

        fetcher = SkillFetcher()
        result = fetcher.fetch_metadata(f"local:{skill_dir}")

        assert result.success is True
        assert result.name == "local-test-skill"
        assert result.description == "A local test skill for testing"
        assert result.version is not None  # Should have local@checksum format

    def test_fetch_local_skill_not_found(self, tmp_path):
        """Test fetching from non-existent local path."""
        fetcher = SkillFetcher()
        result = fetcher.fetch_metadata(f"local:{tmp_path}/nonexistent")

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_fetch_local_skill_no_skillmd(self, tmp_path):
        """Test fetching from directory without SKILL.md."""
        skill_dir = tmp_path / "empty-skill"
        skill_dir.mkdir()

        fetcher = SkillFetcher()
        result = fetcher.fetch_metadata(f"local:{skill_dir}")

        assert result.success is False
        assert "SKILL.md" in result.error

    def test_fetch_local_skill_invalid_frontmatter(self, tmp_path):
        """Test fetching skill with invalid frontmatter."""
        skill_dir = tmp_path / "invalid-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""# No frontmatter here

Just plain markdown.
""")

        fetcher = SkillFetcher()
        result = fetcher.fetch_metadata(f"local:{skill_dir}")

        assert result.success is False
        assert "Invalid skill" in result.error or "frontmatter" in result.error.lower()

    def test_fetch_local_skill_missing_name(self, tmp_path):
        """Test fetching skill without name in frontmatter."""
        skill_dir = tmp_path / "nameless-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
description: A skill without name
---
# Nameless Skill
""")

        fetcher = SkillFetcher()
        result = fetcher.fetch_metadata(f"local:{skill_dir}")

        assert result.success is False
        assert "name" in result.error.lower()


class TestSkillFetcherGitHub:
    """Test SkillFetcher with GitHub sources."""

    def _create_mock_tarball(self, skill_content: bytes) -> bytes:
        """Create a mock tarball with SKILL.md."""
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            # Add directory
            dir_info = tarfile.TarInfo(name="repo-main/")
            dir_info.type = tarfile.DIRTYPE
            dir_info.mode = 0o755
            tar.addfile(dir_info)

            # Add SKILL.md
            skill_info = tarfile.TarInfo(name="repo-main/SKILL.md")
            skill_info.size = len(skill_content)
            skill_info.mode = 0o644
            tar.addfile(skill_info, io.BytesIO(skill_content))

        return tar_buffer.getvalue()

    def test_fetch_github_skill(self, requests_mock, tmp_path):
        """Test fetching metadata from GitHub skill."""
        skill_content = b"""---
name: github-skill
description: A skill from GitHub
---
# GitHub Skill
"""
        # Mock GitHub API
        requests_mock.get(
            "https://api.github.com/repos/owner/repo",
            json={"default_branch": "main"}
        )
        requests_mock.get(
            "https://api.github.com/repos/owner/repo/tarball/main",
            content=self._create_mock_tarball(skill_content)
        )

        fetcher = SkillFetcher(cache_dir=tmp_path / "cache")
        result = fetcher.fetch_metadata("github:owner/repo")

        assert result.success is True
        assert result.name == "github-skill"
        assert result.description == "A skill from GitHub"
        assert result.version == "main"

    def test_fetch_github_skill_with_token(self, requests_mock, tmp_path):
        """Test fetching with GitHub token."""
        skill_content = b"""---
name: private-skill
description: A private skill
---
# Private Skill
"""
        requests_mock.get(
            "https://api.github.com/repos/owner/private-repo",
            json={"default_branch": "main"}
        )
        requests_mock.get(
            "https://api.github.com/repos/owner/private-repo/tarball/main",
            content=self._create_mock_tarball(skill_content)
        )

        fetcher = SkillFetcher(github_token="test-token", cache_dir=tmp_path / "cache")
        result = fetcher.fetch_metadata("github:owner/private-repo")

        assert result.success is True

        # Verify token was used
        for request in requests_mock.request_history:
            if "api.github.com" in request.url:
                assert request.headers.get("Authorization") == "token test-token"

    def test_fetch_github_skill_not_found(self, requests_mock):
        """Test fetching from non-existent GitHub repo."""
        requests_mock.get(
            "https://api.github.com/repos/nonexistent/repo",
            status_code=404,
            json={"message": "Not Found"}
        )

        fetcher = SkillFetcher()
        result = fetcher.fetch_metadata("github:nonexistent/repo")

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_fetch_github_rate_limited(self, requests_mock):
        """Test handling GitHub rate limit."""
        requests_mock.get(
            "https://api.github.com/repos/owner/repo",
            status_code=403,
            json={"message": "API rate limit exceeded"}
        )

        fetcher = SkillFetcher()
        result = fetcher.fetch_metadata("github:owner/repo")

        assert result.success is False
        assert "rate limit" in result.error.lower() or "denied" in result.error.lower()
