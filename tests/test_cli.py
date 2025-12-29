"""Tests for CLI commands."""
import io
import tarfile
import pytest
from pathlib import Path
from unittest.mock import patch
from click.testing import CliRunner
from asma.cli.main import cli
from asma import __version__


class TestVersionCommand:
    """Test 'asma version' command."""

    def test_version_command(self):
        """Test that version command outputs version number."""
        # Given: CLI runner
        runner = CliRunner()

        # When: we run 'asma version'
        result = runner.invoke(cli, ['version'])

        # Then: should succeed and show version
        assert result.exit_code == 0
        assert __version__ in result.output


class TestInitCommand:
    """Test 'asma init' command."""

    def test_init_creates_skillset_file(self):
        """Test that init command creates skillset.yaml."""
        # Given: temporary directory without skillset.yaml
        runner = CliRunner()

        with runner.isolated_filesystem():
            # When: we run 'asma init'
            result = runner.invoke(cli, ['init'])

            # Then: should succeed
            assert result.exit_code == 0
            assert "Created skillset.yaml" in result.output

            # And: skillset.yaml should exist
            assert Path("skillset.yaml").exists()

            # And: file should have template content
            content = Path("skillset.yaml").read_text()
            assert "global:" in content
            assert "project:" in content

    def test_init_fails_if_file_exists(self):
        """Test that init fails if skillset.yaml already exists."""
        # Given: existing skillset.yaml
        runner = CliRunner()

        with runner.isolated_filesystem():
            Path("skillset.yaml").write_text("existing content")

            # When: we run 'asma init'
            result = runner.invoke(cli, ['init'])

            # Then: should fail
            assert result.exit_code != 0
            assert "already exists" in result.output.lower()

    def test_init_with_force_overwrites(self):
        """Test that init --force overwrites existing file."""
        # Given: existing skillset.yaml
        runner = CliRunner()

        with runner.isolated_filesystem():
            Path("skillset.yaml").write_text("old content")

            # When: we run 'asma init --force'
            result = runner.invoke(cli, ['init', '--force'])

            # Then: should succeed
            assert result.exit_code == 0

            # And: file should be overwritten with template
            content = Path("skillset.yaml").read_text()
            assert "old content" not in content
            assert "global:" in content


class TestMainCLI:
    """Test main CLI entry point."""

    def test_cli_help(self):
        """Test that CLI shows help message."""
        # Given: CLI runner
        runner = CliRunner()

        # When: we run 'asma --help'
        result = runner.invoke(cli, ['--help'])

        # Then: should show help
        assert result.exit_code == 0
        assert "asma" in result.output.lower()
        assert "Usage:" in result.output

    def test_cli_without_arguments(self):
        """Test that CLI without arguments shows usage."""
        # Given: CLI runner
        runner = CliRunner()

        # When: we run 'asma' with no args
        result = runner.invoke(cli, [])

        # Then: should show usage message (click behavior)
        assert "Usage:" in result.output


class TestInstallCommand:
    """Test 'asma install' command."""

    def test_install_from_skillset(self):
        """Test installing skills from skillset.yaml."""
        # Given: skillset.yaml with a local skill
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            # Create source skill
            source_dir = fs_path / "my-skill"
            source_dir.mkdir()
            (source_dir / "SKILL.md").write_text("""---
name: test-skill
description: A test skill for installation
---
# Test Skill
""")

            # Create skillset.yaml (use project scope to stay within isolated filesystem)
            skillset = fs_path / "skillset.yaml"
            skillset.write_text(f"""
project:
  - name: test-skill
    source: local:{source_dir}
""")

            # When: we run 'asma install'
            result = runner.invoke(cli, ['install'])

            # Then: should succeed
            assert result.exit_code == 0
            assert "test-skill" in result.output
            assert "Successfully installed" in result.output or "✓" in result.output

    def test_install_no_skillset_file(self):
        """Test that install fails if skillset.yaml not found."""
        # Given: no skillset.yaml
        runner = CliRunner()

        with runner.isolated_filesystem():
            # When: we run 'asma install'
            result = runner.invoke(cli, ['install'])

            # Then: should fail with helpful message
            assert result.exit_code != 0
            assert "skillset.yaml" in result.output.lower()
            assert "not found" in result.output.lower()

    def test_install_with_custom_file(self):
        """Test installing from custom file path."""
        # Given: custom skillset file
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            source_dir = fs_path / "my-skill"
            source_dir.mkdir()
            (source_dir / "SKILL.md").write_text("""---
name: test-skill
description: Test
---
# Test
""")

            custom_file = fs_path / "custom.yaml"
            custom_file.write_text(f"""
project:
  - name: test-skill
    source: local:{source_dir}
""")

            # When: we run with --file option
            result = runner.invoke(cli, ['install', '--file', str(custom_file)])

            # Then: should succeed
            assert result.exit_code == 0

    def test_install_unsupported_source(self):
        """Test that unsupported source types are handled gracefully."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            skillset = fs_path / "skillset.yaml"
            skillset.write_text("""
global:
  - name: test-skill
    source: unknown:some/path
""")

            result = runner.invoke(cli, ['install'])

            # Should fail with invalid source format error
            # (Skill model validates source prefix at load time)
            assert "invalid source format" in result.output.lower()

    def test_install_no_skills_in_skillset(self):
        """Test that empty skillset is handled gracefully."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            skillset = fs_path / "skillset.yaml"
            skillset.write_text("""
global: []
project: []
""")

            result = runner.invoke(cli, ['install'])

            assert result.exit_code == 0
            assert "No skills to install" in result.output

    def test_install_git_source_unsupported(self):
        """Test that git: source (not yet implemented) shows unsupported message."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            skillset = fs_path / "skillset.yaml"
            skillset.write_text("""
global:
  - name: test-skill
    source: git:https://example.com/repo.git
""")

            result = runner.invoke(cli, ['install'])

            assert result.exit_code == 0
            assert "unsupported source" in result.output


class TestInstallCommandGitHub:
    """Test 'asma install' command with GitHub sources."""

    def _create_mock_tarball(self) -> bytes:
        """Create a mock tarball with SKILL.md."""
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            dir_info = tarfile.TarInfo(name="repo-main/")
            dir_info.type = tarfile.DIRTYPE
            dir_info.mode = 0o755
            tar.addfile(dir_info)

            skill_content = b"---\nname: test-skill\ndescription: Test\n---\n# Test"
            skill_info = tarfile.TarInfo(name="repo-main/SKILL.md")
            skill_info.size = len(skill_content)
            skill_info.mode = 0o644
            tar.addfile(skill_info, io.BytesIO(skill_content))

        return tar_buffer.getvalue()

    def test_install_github_source(self, requests_mock):
        """Test installing skill from GitHub source."""
        runner = CliRunner()

        # Mock GitHub API
        requests_mock.get(
            "https://api.github.com/repos/owner/repo",
            json={"default_branch": "main"}
        )
        requests_mock.get(
            "https://api.github.com/repos/owner/repo/tarball/main",
            content=self._create_mock_tarball()
        )

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            skillset = fs_path / "skillset.yaml"
            skillset.write_text("""
global:
  - name: test-skill
    source: github:owner/repo
""")

            result = runner.invoke(cli, ['install'])

            assert result.exit_code == 0
            assert "test-skill" in result.output

    def test_install_github_with_ref(self, requests_mock):
        """Test installing skill from GitHub with specific ref."""
        runner = CliRunner()

        # Mock GitHub API (no need to mock repo endpoint when ref is specified)
        requests_mock.get(
            "https://api.github.com/repos/owner/repo/tarball/v1.0.0",
            content=self._create_mock_tarball()
        )

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            skillset = fs_path / "skillset.yaml"
            skillset.write_text("""
global:
  - name: test-skill
    source: github:owner/repo
    version: v1.0.0
""")

            result = runner.invoke(cli, ['install'])

            assert result.exit_code == 0
            assert "test-skill" in result.output

    def test_install_github_repo_not_found(self, requests_mock):
        """Test handling GitHub repo not found."""
        runner = CliRunner()

        requests_mock.get(
            "https://api.github.com/repos/nonexistent/repo",
            status_code=404,
            json={"message": "Not Found"}
        )

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            skillset = fs_path / "skillset.yaml"
            skillset.write_text("""
global:
  - name: test-skill
    source: github:nonexistent/repo
""")

            result = runner.invoke(cli, ['install'])

            # Should complete but report failure
            assert "Failed" in result.output or "✗" in result.output

    def test_install_github_with_token(self, requests_mock):
        """Test that GITHUB_TOKEN environment variable is used."""
        runner = CliRunner()

        requests_mock.get(
            "https://api.github.com/repos/owner/private-repo",
            json={"default_branch": "main"}
        )
        requests_mock.get(
            "https://api.github.com/repos/owner/private-repo/tarball/main",
            content=self._create_mock_tarball()
        )

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            skillset = fs_path / "skillset.yaml"
            skillset.write_text("""
global:
  - name: test-skill
    source: github:owner/private-repo
""")

            # Run with GITHUB_TOKEN environment variable
            result = runner.invoke(
                cli,
                ['install'],
                env={"GITHUB_TOKEN": "test-token"}
            )

            assert result.exit_code == 0

            # Verify token was used in requests
            for request in requests_mock.request_history:
                if "api.github.com" in request.url:
                    assert request.headers.get("Authorization") == "token test-token"

