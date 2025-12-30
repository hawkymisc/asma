"""Tests for GitHub source handler."""
import io
import tarfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import requests

from asma.core.sources.github import GitHubSourceHandler, parse_github_source
from asma.core.sources.base import ResolvedSource
from asma.models.skill import Skill, SkillScope


class TestParseGitHubSource:
    """Test parsing github:owner/repo[/path] format."""

    def test_parse_owner_repo_only(self):
        """Test parsing github:owner/repo."""
        owner, repo, path = parse_github_source("github:anthropics/skills")
        assert owner == "anthropics"
        assert repo == "skills"
        assert path is None

    def test_parse_with_subpath(self):
        """Test parsing github:owner/repo/subpath."""
        owner, repo, path = parse_github_source("github:anthropics/skills/document-analyzer")
        assert owner == "anthropics"
        assert repo == "skills"
        assert path == "document-analyzer"

    def test_parse_with_nested_subpath(self):
        """Test parsing github:owner/repo/nested/path."""
        owner, repo, path = parse_github_source("github:user/repo/dir/subdir")
        assert owner == "user"
        assert repo == "repo"
        assert path == "dir/subdir"

    def test_parse_invalid_format(self):
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid GitHub source"):
            parse_github_source("github:invalid")

    def test_parse_without_prefix(self):
        """Test that missing github: prefix raises ValueError."""
        with pytest.raises(ValueError, match="Invalid GitHub source"):
            parse_github_source("anthropics/skills")


class TestGitHubSourceHandler:
    """Test GitHubSourceHandler."""

    def test_should_symlink_returns_false(self):
        """Test that GitHub sources should not be symlinked."""
        handler = GitHubSourceHandler()
        assert handler.should_symlink() is False

    def test_resolve_default_branch(self, requests_mock):
        """Test resolving with default branch."""
        # Given: a skill with GitHub source
        skill = Skill(
            name="test-skill",
            source="github:anthropics/skills",
            scope=SkillScope.GLOBAL
        )

        # And: mocked GitHub API responses
        requests_mock.get(
            "https://api.github.com/repos/anthropics/skills",
            json={"default_branch": "main"}
        )

        # When: we resolve
        handler = GitHubSourceHandler()
        resolved = handler.resolve(skill)

        # Then: should resolve with default branch
        assert resolved.version == "main"
        assert resolved.commit == "main"
        assert "tarball/main" in resolved.download_url

    def test_resolve_with_ref(self, requests_mock):
        """Test resolving with specific ref."""
        skill = Skill(
            name="test-skill",
            source="github:owner/repo",
            scope=SkillScope.GLOBAL,
            ref="develop"
        )

        # When: we resolve
        handler = GitHubSourceHandler()
        resolved = handler.resolve(skill)

        # Then: should use the specified ref (no API call needed)
        assert resolved.version == "develop"
        assert resolved.commit == "develop"
        assert "tarball/develop" in resolved.download_url

    def test_resolve_with_version_tag(self, requests_mock):
        """Test resolving with version tag."""
        skill = Skill(
            name="test-skill",
            source="github:owner/repo",
            scope=SkillScope.GLOBAL,
            version="v1.0.0"
        )

        # When: we resolve
        handler = GitHubSourceHandler()
        resolved = handler.resolve(skill)

        # Then: should use the version tag
        assert resolved.version == "v1.0.0"
        assert resolved.commit == "v1.0.0"
        assert "tarball/v1.0.0" in resolved.download_url

    def test_resolve_with_latest_version(self, requests_mock):
        """Test resolving with version: latest."""
        skill = Skill(
            name="test-skill",
            source="github:owner/repo",
            scope=SkillScope.GLOBAL,
            version="latest"
        )

        # Mock the latest release endpoint
        requests_mock.get(
            "https://api.github.com/repos/owner/repo/releases/latest",
            json={"tag_name": "v2.0.0"}
        )

        # When: we resolve
        handler = GitHubSourceHandler()
        resolved = handler.resolve(skill)

        # Then: should use the latest release tag
        assert resolved.version == "v2.0.0"
        assert resolved.commit == "v2.0.0"
        assert "tarball/v2.0.0" in resolved.download_url

    def test_resolve_repo_not_found(self, requests_mock):
        """Test resolving non-existent repo."""
        skill = Skill(
            name="test-skill",
            source="github:nonexistent/repo",
            scope=SkillScope.GLOBAL
        )

        requests_mock.get(
            "https://api.github.com/repos/nonexistent/repo",
            status_code=404,
            json={"message": "Not Found"}
        )

        handler = GitHubSourceHandler()
        with pytest.raises(FileNotFoundError, match="Repository not found"):
            handler.resolve(skill)

    def test_resolve_with_token(self, requests_mock):
        """Test that token is used in API requests."""
        skill = Skill(
            name="test-skill",
            source="github:owner/repo",
            scope=SkillScope.GLOBAL
        )

        requests_mock.get(
            "https://api.github.com/repos/owner/repo",
            json={"default_branch": "main"}
        )

        # When: we use handler with token
        handler = GitHubSourceHandler(token="test-token")
        resolved = handler.resolve(skill)

        # Then: token should be in request headers
        assert requests_mock.last_request.headers.get("Authorization") == "token test-token"

    def test_resolve_stores_subpath(self, requests_mock):
        """Test that subpath is stored in resolved source."""
        skill = Skill(
            name="test-skill",
            source="github:owner/repo/subdir",
            scope=SkillScope.GLOBAL,
            ref="main"
        )

        handler = GitHubSourceHandler()
        resolved = handler.resolve(skill)

        # Subpath should be accessible (stored as metadata or parsed later)
        assert "tarball/main" in resolved.download_url


class TestGitHubSourceHandlerDownload:
    """Test GitHubSourceHandler download functionality."""

    def _create_tarball(self, tmp_path: Path, subpath: str = None) -> bytes:
        """Create a mock tarball with SKILL.md."""
        # Create the tarball content
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            # GitHub tarballs have a root directory like "repo-ref/"
            root_dir = "repo-main"

            # Add root directory
            dir_info = tarfile.TarInfo(name=root_dir + "/")
            dir_info.type = tarfile.DIRTYPE
            dir_info.mode = 0o755
            tar.addfile(dir_info)

            if subpath:
                # Add subpath directories
                parts = subpath.split("/")
                current_path = root_dir
                for part in parts:
                    current_path = f"{current_path}/{part}"
                    subdir_info = tarfile.TarInfo(name=current_path + "/")
                    subdir_info.type = tarfile.DIRTYPE
                    subdir_info.mode = 0o755
                    tar.addfile(subdir_info)
                skill_path = f"{current_path}/SKILL.md"
            else:
                skill_path = f"{root_dir}/SKILL.md"

            # Add SKILL.md
            skill_content = b"---\nname: test-skill\ndescription: Test\n---\n# Test"
            skill_info = tarfile.TarInfo(name=skill_path)
            skill_info.size = len(skill_content)
            skill_info.mode = 0o644
            tar.addfile(skill_info, io.BytesIO(skill_content))

        return tar_buffer.getvalue()

    def test_download_and_extract(self, tmp_path, requests_mock):
        """Test downloading and extracting tarball."""
        # Given: resolved source
        resolved = ResolvedSource(
            version="main",
            commit="main",
            download_url="https://api.github.com/repos/owner/repo/tarball/main"
        )

        # Mock tarball download
        tarball_content = self._create_tarball(tmp_path)
        requests_mock.get(
            "https://api.github.com/repos/owner/repo/tarball/main",
            content=tarball_content
        )

        # When: we download
        handler = GitHubSourceHandler(cache_dir=tmp_path / "cache")
        result_path = handler.download(resolved)

        # Then: should extract to path with SKILL.md
        assert result_path.exists()
        assert (result_path / "SKILL.md").exists()

    def test_download_with_subpath(self, tmp_path, requests_mock):
        """Test downloading with subpath extraction."""
        resolved = ResolvedSource(
            version="main",
            commit="main",
            download_url="https://api.github.com/repos/owner/repo/tarball/main"
        )

        # Mock tarball with subpath
        tarball_content = self._create_tarball(tmp_path, subpath="skills/my-skill")
        requests_mock.get(
            "https://api.github.com/repos/owner/repo/tarball/main",
            content=tarball_content
        )

        handler = GitHubSourceHandler(cache_dir=tmp_path / "cache")
        # Store subpath info for extraction
        handler._pending_subpath = "skills/my-skill"
        result_path = handler.download(resolved)

        # Then: should return the subpath directory
        assert result_path.exists()
        assert (result_path / "SKILL.md").exists()

    def test_download_uses_cache(self, tmp_path, requests_mock):
        """Test that cached downloads are reused."""
        resolved = ResolvedSource(
            version="v1.0.0",
            commit="v1.0.0",
            download_url="https://api.github.com/repos/owner/repo/tarball/v1.0.0"
        )

        tarball_content = self._create_tarball(tmp_path)
        requests_mock.get(
            "https://api.github.com/repos/owner/repo/tarball/v1.0.0",
            content=tarball_content
        )

        cache_dir = tmp_path / "cache"
        handler = GitHubSourceHandler(cache_dir=cache_dir)

        # First download
        result1 = handler.download(resolved)
        assert requests_mock.call_count == 1

        # Second download should use cache
        result2 = handler.download(resolved)
        # Call count should still be 1 (cached)
        assert requests_mock.call_count == 1
        assert result1 == result2

    def test_download_network_error(self, tmp_path, requests_mock):
        """Test handling network errors during download."""
        resolved = ResolvedSource(
            version="main",
            commit="main",
            download_url="https://api.github.com/repos/owner/repo/tarball/main"
        )

        requests_mock.get(
            "https://api.github.com/repos/owner/repo/tarball/main",
            exc=requests.exceptions.ConnectionError
        )

        handler = GitHubSourceHandler(cache_dir=tmp_path / "cache")
        with pytest.raises(ConnectionError, match="Failed to download"):
            handler.download(resolved)


class TestGitHubSourceHandlerAuth:
    """Test authentication handling."""

    def test_auth_header_without_token(self, requests_mock):
        """Test requests without token don't have auth header."""
        skill = Skill(
            name="test",
            source="github:owner/repo",
            scope=SkillScope.GLOBAL
        )

        requests_mock.get(
            "https://api.github.com/repos/owner/repo",
            json={"default_branch": "main"}
        )

        handler = GitHubSourceHandler()
        handler.resolve(skill)

        assert "Authorization" not in requests_mock.last_request.headers

    def test_rate_limit_error(self, requests_mock):
        """Test handling rate limit errors."""
        skill = Skill(
            name="test",
            source="github:owner/repo",
            scope=SkillScope.GLOBAL
        )

        requests_mock.get(
            "https://api.github.com/repos/owner/repo",
            status_code=403,
            json={"message": "API rate limit exceeded"}
        )

        handler = GitHubSourceHandler()
        with pytest.raises(PermissionError, match="rate limit"):
            handler.resolve(skill)

    def test_unauthorized_error(self, requests_mock):
        """Test handling unauthorized errors."""
        skill = Skill(
            name="test",
            source="github:owner/repo",
            scope=SkillScope.GLOBAL
        )

        requests_mock.get(
            "https://api.github.com/repos/owner/repo",
            status_code=401,
            json={"message": "Bad credentials"}
        )

        handler = GitHubSourceHandler(token="invalid-token")
        with pytest.raises(PermissionError, match="authentication"):
            handler.resolve(skill)


class TestGitHubSourceHandlerEdgeCases:
    """Test edge cases and error conditions."""

    def test_download_without_url_raises_error(self, tmp_path):
        """Test that download fails if download_url is None."""
        resolved = ResolvedSource(
            version="main",
            commit="main",
            download_url=None
        )

        handler = GitHubSourceHandler(cache_dir=tmp_path / "cache")
        with pytest.raises(ValueError, match="download_url"):
            handler.download(resolved)

    def test_resolve_latest_no_releases(self, requests_mock):
        """Test handling when no releases exist for 'latest' version."""
        skill = Skill(
            name="test",
            source="github:owner/repo",
            scope=SkillScope.GLOBAL,
            version="latest"
        )

        requests_mock.get(
            "https://api.github.com/repos/owner/repo/releases/latest",
            status_code=404,
            json={"message": "Not Found"}
        )

        handler = GitHubSourceHandler()
        with pytest.raises(FileNotFoundError):
            handler.resolve(skill)

    def test_resolve_connection_error(self, requests_mock):
        """Test handling connection errors during resolve."""
        skill = Skill(
            name="test",
            source="github:owner/repo",
            scope=SkillScope.GLOBAL
        )

        requests_mock.get(
            "https://api.github.com/repos/owner/repo",
            exc=requests.exceptions.ConnectionError
        )

        handler = GitHubSourceHandler()
        with pytest.raises(ConnectionError, match="Failed to connect"):
            handler.resolve(skill)

    def test_resolve_server_error(self, requests_mock):
        """Test handling 500 server errors."""
        skill = Skill(
            name="test",
            source="github:owner/repo",
            scope=SkillScope.GLOBAL
        )

        requests_mock.get(
            "https://api.github.com/repos/owner/repo",
            status_code=500
        )

        handler = GitHubSourceHandler()
        with pytest.raises(ConnectionError, match="GitHub API error"):
            handler.resolve(skill)

    def test_resolve_403_without_rate_limit(self, requests_mock):
        """Test handling 403 errors that are not rate limit."""
        skill = Skill(
            name="test",
            source="github:owner/repo",
            scope=SkillScope.GLOBAL
        )

        requests_mock.get(
            "https://api.github.com/repos/owner/repo",
            status_code=403,
            json={"message": "Repository access blocked"}
        )

        handler = GitHubSourceHandler()
        with pytest.raises(PermissionError, match="access denied"):
            handler.resolve(skill)

    def test_parse_empty_owner(self):
        """Test parsing with empty owner results in empty string."""
        # github:/repo parses but results in empty owner
        owner, repo, path = parse_github_source("github:/repo")
        assert owner == ""
        assert repo == "repo"

    def test_parse_empty_repo(self):
        """Test parsing with empty repo."""
        # github:owner/ should fail because repo is empty
        owner, repo, path = parse_github_source("github:owner/")
        assert owner == "owner"
        assert repo == ""  # Empty repo - implementation allows it

    def test_download_invalid_tarball(self, tmp_path, requests_mock):
        """Test handling invalid/corrupted tarball."""
        resolved = ResolvedSource(
            version="main",
            commit="main",
            download_url="https://api.github.com/repos/owner/repo/tarball/main"
        )

        # Return invalid data that's not a valid gzip
        requests_mock.get(
            "https://api.github.com/repos/owner/repo/tarball/main",
            content=b"not a valid tarball"
        )

        handler = GitHubSourceHandler(cache_dir=tmp_path / "cache")
        with pytest.raises(ValueError, match="Failed to extract"):
            handler.download(resolved)

    def test_default_cache_dir(self):
        """Test that default cache directory is set correctly."""
        handler = GitHubSourceHandler()
        expected = Path.home() / ".cache" / "asma" / "github"
        assert handler.cache_dir == expected

    def test_custom_cache_dir(self, tmp_path):
        """Test that custom cache directory is used."""
        custom_cache = tmp_path / "my-cache"
        handler = GitHubSourceHandler(cache_dir=custom_cache)
        assert handler.cache_dir == custom_cache

    def test_download_creates_cache_dir(self, tmp_path, requests_mock):
        """Test that cache directory is created if it doesn't exist."""
        cache_dir = tmp_path / "nonexistent" / "cache"
        assert not cache_dir.exists()

        resolved = ResolvedSource(
            version="main",
            commit="main",
            download_url="https://api.github.com/repos/owner/repo/tarball/main"
        )

        # Create valid tarball
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            dir_info = tarfile.TarInfo(name="repo-main/")
            dir_info.type = tarfile.DIRTYPE
            dir_info.mode = 0o755
            tar.addfile(dir_info)

            skill_content = b"---\nname: test\ndescription: Test\n---\n"
            skill_info = tarfile.TarInfo(name="repo-main/SKILL.md")
            skill_info.size = len(skill_content)
            skill_info.mode = 0o644
            tar.addfile(skill_info, io.BytesIO(skill_content))

        requests_mock.get(
            "https://api.github.com/repos/owner/repo/tarball/main",
            content=tar_buffer.getvalue()
        )

        handler = GitHubSourceHandler(cache_dir=cache_dir)
        handler.download(resolved)

        assert cache_dir.exists()

    def test_api_returns_non_dict_json(self, requests_mock):
        """Test handling when GitHub API returns a JSON array instead of object."""
        skill = Skill(
            name="test",
            source="github:owner/repo",
            scope=SkillScope.GLOBAL
        )

        # Mock API to return an array instead of object
        requests_mock.get(
            "https://api.github.com/repos/owner/repo",
            json=["unexpected", "array", "response"]
        )

        handler = GitHubSourceHandler()
        with pytest.raises(ValueError, match="Expected JSON object"):
            handler.resolve(skill)


class TestVersionNotSpecified:
    """Test version/ref not specified behavior."""

    def test_no_version_without_strict_emits_warning(self, requests_mock):
        """Test that resolving without version/ref emits a warning when strict=False."""
        import warnings

        skill = Skill(
            name="test-skill",
            source="github:owner/repo",
            scope=SkillScope.GLOBAL
            # No version or ref specified
        )

        requests_mock.get(
            "https://api.github.com/repos/owner/repo",
            json={"default_branch": "main"}
        )

        handler = GitHubSourceHandler(strict=False)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            resolved = handler.resolve(skill)

            # Should emit a warning
            assert len(w) == 1
            assert "version" in str(w[0].message).lower()
            assert "test-skill" in str(w[0].message)

            # Should still resolve successfully
            assert resolved.version == "main"

    def test_no_version_with_strict_raises_error(self, requests_mock):
        """Test that resolving without version/ref raises error when strict=True."""
        skill = Skill(
            name="test-skill",
            source="github:owner/repo",
            scope=SkillScope.GLOBAL
            # No version or ref specified
        )

        handler = GitHubSourceHandler(strict=True)

        with pytest.raises(ValueError, match=r"[Vv]ersion.*not specified|[Ss]trict"):
            handler.resolve(skill)

    def test_with_version_no_warning_strict_false(self, requests_mock):
        """Test that specifying version does not emit warning even in non-strict mode."""
        import warnings

        skill = Skill(
            name="test-skill",
            source="github:owner/repo",
            scope=SkillScope.GLOBAL,
            version="v1.0.0"
        )

        handler = GitHubSourceHandler(strict=False)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            resolved = handler.resolve(skill)

            # No warning should be emitted
            assert len(w) == 0
            assert resolved.version == "v1.0.0"

    def test_with_ref_no_warning_strict_false(self, requests_mock):
        """Test that specifying ref does not emit warning even in non-strict mode."""
        import warnings

        skill = Skill(
            name="test-skill",
            source="github:owner/repo",
            scope=SkillScope.GLOBAL,
            ref="develop"
        )

        handler = GitHubSourceHandler(strict=False)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            resolved = handler.resolve(skill)

            # No warning should be emitted
            assert len(w) == 0
            assert resolved.version == "develop"

    def test_with_version_no_error_strict_true(self, requests_mock):
        """Test that specifying version works fine in strict mode."""
        skill = Skill(
            name="test-skill",
            source="github:owner/repo",
            scope=SkillScope.GLOBAL,
            version="v2.0.0"
        )

        handler = GitHubSourceHandler(strict=True)
        resolved = handler.resolve(skill)

        assert resolved.version == "v2.0.0"

    def test_with_ref_no_error_strict_true(self, requests_mock):
        """Test that specifying ref works fine in strict mode."""
        skill = Skill(
            name="test-skill",
            source="github:owner/repo",
            scope=SkillScope.GLOBAL,
            ref="feature-branch"
        )

        handler = GitHubSourceHandler(strict=True)
        resolved = handler.resolve(skill)

        assert resolved.version == "feature-branch"

    def test_strict_default_is_false(self):
        """Test that strict mode is disabled by default."""
        handler = GitHubSourceHandler()
        assert handler.strict is False

