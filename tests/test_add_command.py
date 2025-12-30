"""Tests for 'asma add' command."""
import io
import tarfile
import pytest
from pathlib import Path
from click.testing import CliRunner

from asma.cli.main import cli


class TestAddCommand:
    """Test 'asma add' command."""

    def test_add_local_skill(self):
        """Test adding local skill to skillset.yaml."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            # Create source skill
            source_dir = fs_path / "my-skill"
            source_dir.mkdir()
            (source_dir / "SKILL.md").write_text("""---
name: awesome-skill
description: An awesome skill for testing
---
# Awesome Skill

This is an awesome skill.
""")

            # Create skillset.yaml
            (fs_path / "skillset.yaml").write_text("global: {}\nproject: {}")

            # Run add command
            result = runner.invoke(cli, ['add', f'local:{source_dir}'])

            assert result.exit_code == 0
            assert "Found skill: awesome-skill" in result.output
            assert "Added 'awesome-skill'" in result.output
            assert "project" in result.output

            # Verify skillset.yaml was updated
            content = (fs_path / "skillset.yaml").read_text()
            assert "awesome-skill" in content
            assert f"local:{source_dir}" in content

    def test_add_with_global_flag(self):
        """Test adding skill with --global flag."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            source_dir = fs_path / "my-skill"
            source_dir.mkdir()
            (source_dir / "SKILL.md").write_text("""---
name: global-skill
description: A global skill
---
# Global Skill
""")

            (fs_path / "skillset.yaml").write_text("global: {}\nproject: {}")

            result = runner.invoke(cli, ['add', f'local:{source_dir}', '--global'])

            assert result.exit_code == 0
            assert "global" in result.output

            # Verify skill was added to global section
            content = (fs_path / "skillset.yaml").read_text()
            assert "global:" in content

    def test_add_with_scope_option(self):
        """Test adding skill with --scope option."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            source_dir = fs_path / "my-skill"
            source_dir.mkdir()
            (source_dir / "SKILL.md").write_text("""---
name: scoped-skill
description: A scoped skill
---
# Scoped Skill
""")

            (fs_path / "skillset.yaml").write_text("global: {}\nproject: {}")

            result = runner.invoke(cli, ['add', '--scope', 'global', f'local:{source_dir}'])

            assert result.exit_code == 0
            assert "global" in result.output

    def test_add_existing_skill_fails(self):
        """Test adding existing skill fails without --force."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            source_dir = fs_path / "my-skill"
            source_dir.mkdir()
            (source_dir / "SKILL.md").write_text("""---
name: existing-skill
description: An existing skill
---
# Existing Skill
""")

            (fs_path / "skillset.yaml").write_text("""
global: {}
project:
  existing-skill:
    source: github:old/repo
""")

            result = runner.invoke(cli, ['add', f'local:{source_dir}'])

            assert result.exit_code != 0
            assert "already exists" in result.output
            assert "--force" in result.output

    def test_add_existing_skill_with_force(self):
        """Test adding existing skill succeeds with --force."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            source_dir = fs_path / "my-skill"
            source_dir.mkdir()
            (source_dir / "SKILL.md").write_text("""---
name: existing-skill
description: An updated skill
---
# Updated Skill
""")

            (fs_path / "skillset.yaml").write_text("""
global: {}
project:
  existing-skill:
    source: github:old/repo
""")

            result = runner.invoke(cli, ['add', f'local:{source_dir}', '--force'])

            assert result.exit_code == 0
            assert "Added 'existing-skill'" in result.output

            # Verify source was updated
            content = (fs_path / "skillset.yaml").read_text()
            assert f"local:{source_dir}" in content

    def test_add_no_skillset_file(self):
        """Test add fails when skillset.yaml doesn't exist."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            source_dir = fs_path / "my-skill"
            source_dir.mkdir()
            (source_dir / "SKILL.md").write_text("""---
name: test-skill
description: A test skill
---
# Test Skill
""")

            result = runner.invoke(cli, ['add', f'local:{source_dir}'])

            assert result.exit_code != 0
            assert "skillset.yaml" in result.output
            assert "not found" in result.output.lower()
            assert "asma init" in result.output

    def test_add_invalid_source(self):
        """Test add fails with invalid source."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            (fs_path / "skillset.yaml").write_text("global: {}\nproject: {}")

            result = runner.invoke(cli, ['add', 'invalid:source'])

            assert result.exit_code != 0
            assert "Unsupported source type" in result.output or "Failed to fetch" in result.output

    def test_add_source_not_found(self):
        """Test add fails when source doesn't exist."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            (fs_path / "skillset.yaml").write_text("global: {}\nproject: {}")

            result = runner.invoke(cli, ['add', 'local:/nonexistent/path'])

            assert result.exit_code != 0
            assert "Failed to fetch" in result.output

    def test_add_with_custom_name(self):
        """Test adding skill with custom name override."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            source_dir = fs_path / "my-skill"
            source_dir.mkdir()
            (source_dir / "SKILL.md").write_text("""---
name: original-name
description: A skill with original name
---
# Original Name Skill
""")

            (fs_path / "skillset.yaml").write_text("global: {}\nproject: {}")

            result = runner.invoke(cli, ['add', f'local:{source_dir}', '--name', 'custom-name'])

            assert result.exit_code == 0
            assert "Added 'custom-name'" in result.output

            content = (fs_path / "skillset.yaml").read_text()
            assert "custom-name" in content
            assert "original-name" not in content

    def test_add_shows_description(self):
        """Test that add command shows skill description."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            source_dir = fs_path / "my-skill"
            source_dir.mkdir()
            (source_dir / "SKILL.md").write_text("""---
name: desc-skill
description: This is a detailed description of the skill
---
# Descriptive Skill
""")

            (fs_path / "skillset.yaml").write_text("global: {}\nproject: {}")

            result = runner.invoke(cli, ['add', f'local:{source_dir}'])

            assert result.exit_code == 0
            assert "Description: This is a detailed description" in result.output

    def test_add_shows_install_hint(self):
        """Test that add command shows hint to run install."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            source_dir = fs_path / "my-skill"
            source_dir.mkdir()
            (source_dir / "SKILL.md").write_text("""---
name: hint-skill
description: A skill for testing hints
---
# Hint Skill
""")

            (fs_path / "skillset.yaml").write_text("global: {}\nproject: {}")

            result = runner.invoke(cli, ['add', f'local:{source_dir}'])

            assert result.exit_code == 0
            assert "asma install" in result.output

    def test_add_with_custom_file(self):
        """Test adding skill with custom skillset file."""
        runner = CliRunner()

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            source_dir = fs_path / "my-skill"
            source_dir.mkdir()
            (source_dir / "SKILL.md").write_text("""---
name: custom-file-skill
description: A skill for custom file test
---
# Custom File Skill
""")

            custom_file = fs_path / "custom.yaml"
            custom_file.write_text("global: {}\nproject: {}")

            result = runner.invoke(cli, ['add', f'local:{source_dir}', '--file', str(custom_file)])

            assert result.exit_code == 0
            assert "Added 'custom-file-skill'" in result.output

            content = custom_file.read_text()
            assert "custom-file-skill" in content


class TestAddCommandGitHub:
    """Test 'asma add' command with GitHub sources."""

    def _create_mock_tarball(self, name: str, description: str) -> bytes:
        """Create a mock tarball with SKILL.md."""
        skill_content = f"""---
name: {name}
description: {description}
---
# {name}
""".encode()

        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            dir_info = tarfile.TarInfo(name="repo-main/")
            dir_info.type = tarfile.DIRTYPE
            dir_info.mode = 0o755
            tar.addfile(dir_info)

            skill_info = tarfile.TarInfo(name="repo-main/SKILL.md")
            skill_info.size = len(skill_content)
            skill_info.mode = 0o644
            tar.addfile(skill_info, io.BytesIO(skill_content))

        return tar_buffer.getvalue()

    def test_add_github_skill(self, requests_mock):
        """Test adding skill from GitHub."""
        import uuid
        runner = CliRunner()

        # Use unique repo name to avoid cache conflicts
        repo_id = uuid.uuid4().hex[:8]
        repo_name = f"add-test-repo-{repo_id}"

        requests_mock.get(
            f"https://api.github.com/repos/owner/{repo_name}",
            json={"default_branch": "main"}
        )
        requests_mock.get(
            f"https://api.github.com/repos/owner/{repo_name}/tarball/main",
            content=self._create_mock_tarball("github-skill", "A GitHub skill")
        )

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            (fs_path / "skillset.yaml").write_text("global: {}\nproject: {}")

            result = runner.invoke(cli, ['add', f'github:owner/{repo_name}'])

            assert result.exit_code == 0
            assert "Found skill: github-skill" in result.output
            assert "Added 'github-skill'" in result.output

            content = (fs_path / "skillset.yaml").read_text()
            assert "github-skill" in content
            assert f"github:owner/{repo_name}" in content

    def test_add_github_skill_with_subpath(self, requests_mock):
        """Test adding skill from GitHub with subpath."""
        import uuid
        runner = CliRunner()

        # Use unique repo name to avoid cache conflicts
        repo_id = uuid.uuid4().hex[:8]
        repo_name = f"subpath-repo-{repo_id}"

        # Create tarball with subpath
        skill_content = b"""---
name: subpath-skill
description: A skill in subpath
---
# Subpath Skill
"""
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            # Root dir
            dir_info = tarfile.TarInfo(name="repo-main/")
            dir_info.type = tarfile.DIRTYPE
            tar.addfile(dir_info)

            # Subpath dir
            subdir_info = tarfile.TarInfo(name="repo-main/skills/my-skill/")
            subdir_info.type = tarfile.DIRTYPE
            tar.addfile(subdir_info)

            # SKILL.md in subpath
            skill_info = tarfile.TarInfo(name="repo-main/skills/my-skill/SKILL.md")
            skill_info.size = len(skill_content)
            tar.addfile(skill_info, io.BytesIO(skill_content))

        requests_mock.get(
            f"https://api.github.com/repos/owner/{repo_name}",
            json={"default_branch": "main"}
        )
        requests_mock.get(
            f"https://api.github.com/repos/owner/{repo_name}/tarball/main",
            content=tar_buffer.getvalue()
        )

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            (fs_path / "skillset.yaml").write_text("global: {}\nproject: {}")

            result = runner.invoke(cli, ['add', f'github:owner/{repo_name}/skills/my-skill'])

            assert result.exit_code == 0
            assert "subpath-skill" in result.output

    def test_add_github_skill_not_found(self, requests_mock):
        """Test adding non-existent GitHub repo."""
        runner = CliRunner()

        requests_mock.get(
            "https://api.github.com/repos/nonexistent/repo",
            status_code=404,
            json={"message": "Not Found"}
        )

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            (fs_path / "skillset.yaml").write_text("global: {}\nproject: {}")

            result = runner.invoke(cli, ['add', 'github:nonexistent/repo'])

            assert result.exit_code != 0
            assert "Failed to fetch" in result.output

    def test_add_github_skill_saves_version(self, requests_mock):
        """Test that GitHub skill version is saved."""
        import uuid
        runner = CliRunner()

        # Use unique repo name to avoid cache conflicts
        repo_id = uuid.uuid4().hex[:8]
        repo_name = f"version-repo-{repo_id}"

        requests_mock.get(
            f"https://api.github.com/repos/owner/{repo_name}",
            json={"default_branch": "main"}
        )
        requests_mock.get(
            f"https://api.github.com/repos/owner/{repo_name}/tarball/main",
            content=self._create_mock_tarball("versioned-skill", "A versioned skill")
        )

        with runner.isolated_filesystem() as fs:
            fs_path = Path(fs)

            (fs_path / "skillset.yaml").write_text("global: {}\nproject: {}")

            result = runner.invoke(cli, ['add', f'github:owner/{repo_name}'])

            assert result.exit_code == 0

            content = (fs_path / "skillset.yaml").read_text()
            assert "version: main" in content
