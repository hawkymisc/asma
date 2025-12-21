"""Tests for CLI commands."""
import pytest
from pathlib import Path
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
