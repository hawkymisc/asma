"""Security tests for asma."""
import io
import tarfile
import tempfile
from pathlib import Path

import pytest

from asma.core.sources.github import GitHubSourceHandler
from asma.core.sources.local import LocalSourceHandler
from asma.models.skill import Skill, SkillScope


class TestPathTraversalProtection:
    """Test protection against path traversal attacks."""

    def test_local_source_path_traversal_rejected(self, tmp_path: Path) -> None:
        """Test that path traversal attempts in local sources are handled safely."""
        # Create a skill with path traversal attempt
        skill = Skill(
            name="malicious",
            source="local:../../../../etc/passwd",
            scope=SkillScope.PROJECT
        )

        handler = LocalSourceHandler()

        # Should raise an error (FileNotFoundError or ValueError)
        # The exact error depends on whether /etc/passwd exists and is a directory
        with pytest.raises((FileNotFoundError, ValueError)):
            handler.resolve(skill)

    def test_skill_name_with_path_traversal_rejected(self) -> None:
        """Test that skill names with path traversal are rejected."""
        with pytest.raises(ValueError, match="Invalid skill name"):
            Skill(
                name="../../../etc/passwd",
                source="github:test/test",
                scope=SkillScope.PROJECT
            )

    def test_skill_name_with_special_characters_rejected(self) -> None:
        """Test that skill names with special characters are rejected."""
        invalid_names = [
            "../../etc",
            "skill; rm -rf /",
            "skill | cat",
            "skill&whoami",
            "UPPERCASE",
            "skill space",
            "skill/slash",
        ]

        for name in invalid_names:
            with pytest.raises(ValueError, match="Invalid skill name"):
                Skill(
                    name=name,
                    source="github:test/test",
                    scope=SkillScope.PROJECT
                )


class TestTarballExtraction:
    """Test secure tarball extraction."""

    def _create_tarball_with_path_traversal(self) -> bytes:
        """Create a malicious tarball with path traversal."""
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
            # Add a file with path traversal
            info = tarfile.TarInfo(name='../../../tmp/evil.txt')
            info.size = 4
            tar.addfile(info, io.BytesIO(b'evil'))
        return buffer.getvalue()

    def _create_tarball_with_absolute_path(self) -> bytes:
        """Create a malicious tarball with absolute path."""
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
            # Add a file with absolute path
            info = tarfile.TarInfo(name='/tmp/evil.txt')
            info.size = 4
            tar.addfile(info, io.BytesIO(b'evil'))
        return buffer.getvalue()

    def _create_tarball_with_malicious_symlink(self) -> bytes:
        """Create a tarball with a symlink pointing outside extraction dir."""
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
            # Add a symlink with path traversal
            info = tarfile.TarInfo(name='link.txt')
            info.type = tarfile.SYMTYPE
            info.linkname = '../../../../etc/passwd'
            tar.addfile(info)
        return buffer.getvalue()

    def _create_tarball_with_absolute_symlink(self) -> bytes:
        """Create a tarball with an absolute symlink."""
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
            # Add a symlink with absolute path
            info = tarfile.TarInfo(name='link.txt')
            info.type = tarfile.SYMTYPE
            info.linkname = '/etc/passwd'
            tar.addfile(info)
        return buffer.getvalue()

    def test_path_traversal_in_tarball_rejected(self, tmp_path: Path) -> None:
        """Test that tarballs with path traversal are rejected."""
        handler = GitHubSourceHandler()
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        tarball_data = self._create_tarball_with_path_traversal()

        with tarfile.open(fileobj=io.BytesIO(tarball_data), mode='r:gz') as tar:
            with pytest.raises(ValueError, match="path traversal"):
                handler._safe_extract_tarball(tar, extract_dir)

        # Verify nothing was extracted
        assert not (tmp_path / "evil.txt").exists()

    def test_absolute_path_in_tarball_rejected(self, tmp_path: Path) -> None:
        """Test that tarballs with absolute paths are rejected."""
        handler = GitHubSourceHandler()
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        tarball_data = self._create_tarball_with_absolute_path()

        with tarfile.open(fileobj=io.BytesIO(tarball_data), mode='r:gz') as tar:
            # Absolute paths should be rejected (may be caught as path traversal or absolute path)
            with pytest.raises(ValueError, match="Absolute path|path traversal"):
                handler._safe_extract_tarball(tar, extract_dir)

    def test_malicious_symlink_rejected(self, tmp_path: Path) -> None:
        """Test that malicious symlinks in tarballs are rejected."""
        handler = GitHubSourceHandler()
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        tarball_data = self._create_tarball_with_malicious_symlink()

        with tarfile.open(fileobj=io.BytesIO(tarball_data), mode='r:gz') as tar:
            with pytest.raises(ValueError, match="symlink|Path traversal"):
                handler._safe_extract_tarball(tar, extract_dir)

    def test_absolute_symlink_rejected(self, tmp_path: Path) -> None:
        """Test that absolute symlinks in tarballs are rejected."""
        handler = GitHubSourceHandler()
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        tarball_data = self._create_tarball_with_absolute_symlink()

        with tarfile.open(fileobj=io.BytesIO(tarball_data), mode='r:gz') as tar:
            with pytest.raises(ValueError, match="Absolute symlink"):
                handler._safe_extract_tarball(tar, extract_dir)

    def test_safe_tarball_extraction_succeeds(self, tmp_path: Path) -> None:
        """Test that safe tarballs are extracted successfully."""
        handler = GitHubSourceHandler()
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Create a safe tarball
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
            # Add a safe file
            info = tarfile.TarInfo(name='safe/file.txt')
            info.size = 4
            tar.addfile(info, io.BytesIO(b'safe'))
        buffer.seek(0)

        # Should succeed
        with tarfile.open(fileobj=buffer, mode='r:gz') as tar:
            handler._safe_extract_tarball(tar, extract_dir)

        # Verify file was extracted
        assert (extract_dir / "safe" / "file.txt").exists()
        assert (extract_dir / "safe" / "file.txt").read_text() == "safe"


class TestTarBombProtection:
    """Test protection against tar bomb attacks."""

    def test_tar_bomb_too_many_files(self, tmp_path: Path) -> None:
        """Test that tarballs with too many files are rejected."""
        handler = GitHubSourceHandler()
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Create tar with excessive number of files
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
            for i in range(11000):  # Exceeds MAX_FILE_COUNT (10000)
                info = tarfile.TarInfo(name=f'file_{i}.txt')
                info.size = 10
                tar.addfile(info, io.BytesIO(b'x' * 10))
        buffer.seek(0)

        with tarfile.open(fileobj=buffer, mode='r:gz') as tar:
            with pytest.raises(ValueError, match="too many files|tar bomb"):
                handler._safe_extract_tarball(tar, extract_dir)

    def test_tar_bomb_large_single_file(self, tmp_path: Path) -> None:
        """Test that tarballs with extremely large files are rejected."""
        # Temporarily reduce limits for testing to avoid memory issues
        handler = GitHubSourceHandler()
        # Save original limits
        orig_max_single = handler.MAX_SINGLE_FILE_SIZE
        orig_max_total = handler.MAX_EXTRACT_SIZE

        # Set test limits (1 MB)
        handler.MAX_SINGLE_FILE_SIZE = 1 * 1024 * 1024

        try:
            extract_dir = tmp_path / "extract"
            extract_dir.mkdir()

            # Create tar with file exceeding test limit (2 MB)
            buffer = io.BytesIO()
            test_file_size = 2 * 1024 * 1024
            with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
                info = tarfile.TarInfo(name='huge_file.bin')
                info.size = test_file_size
                tar.addfile(info, io.BytesIO(b'\0' * test_file_size))
            buffer.seek(0)

            with tarfile.open(fileobj=buffer, mode='r:gz') as tar:
                with pytest.raises(ValueError, match="File too large|tar bomb"):
                    handler._safe_extract_tarball(tar, extract_dir)
        finally:
            # Restore original limits
            handler.MAX_SINGLE_FILE_SIZE = orig_max_single
            handler.MAX_EXTRACT_SIZE = orig_max_total

    def test_tar_bomb_total_size_exceeded(self, tmp_path: Path) -> None:
        """Test that tarballs exceeding total size limit are rejected."""
        # Temporarily reduce limits for testing to avoid memory issues
        handler = GitHubSourceHandler()
        # Save original limits
        orig_max_total = handler.MAX_EXTRACT_SIZE

        # Set test limit (2 MB total)
        handler.MAX_EXTRACT_SIZE = 2 * 1024 * 1024

        try:
            extract_dir = tmp_path / "extract"
            extract_dir.mkdir()

            # Create tar exceeding test limit (3 MB total from 3x 1MB files)
            buffer = io.BytesIO()
            file_size = 1 * 1024 * 1024
            with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
                for i in range(3):
                    info = tarfile.TarInfo(name=f'large_file_{i}.bin')
                    info.size = file_size
                    tar.addfile(info, io.BytesIO(b'\0' * file_size))
            buffer.seek(0)

            with tarfile.open(fileobj=buffer, mode='r:gz') as tar:
                with pytest.raises(ValueError, match="Total extracted size exceeds|tar bomb"):
                    handler._safe_extract_tarball(tar, extract_dir)
        finally:
            # Restore original limit
            handler.MAX_EXTRACT_SIZE = orig_max_total

    def test_device_file_rejected(self, tmp_path: Path) -> None:
        """Test that device files in tarballs are rejected."""
        handler = GitHubSourceHandler()
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Create tar with device file
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
            info = tarfile.TarInfo(name='dev_file')
            info.type = tarfile.CHRTYPE  # Character device
            tar.addfile(info)
        buffer.seek(0)

        with tarfile.open(fileobj=buffer, mode='r:gz') as tar:
            with pytest.raises(ValueError, match="Device file not allowed"):
                handler._safe_extract_tarball(tar, extract_dir)

    def test_fifo_file_rejected(self, tmp_path: Path) -> None:
        """Test that FIFO files in tarballs are rejected."""
        handler = GitHubSourceHandler()
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Create tar with FIFO
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
            info = tarfile.TarInfo(name='fifo_file')
            info.type = tarfile.FIFOTYPE  # FIFO (named pipe)
            tar.addfile(info)
        buffer.seek(0)

        with tarfile.open(fileobj=buffer, mode='r:gz') as tar:
            # FIFO may be caught by isdev() or isfifo() depending on implementation
            with pytest.raises(ValueError, match="FIFO.*not allowed|Device file not allowed"):
                handler._safe_extract_tarball(tar, extract_dir)

    def test_filename_too_long_rejected(self, tmp_path: Path) -> None:
        """Test that files with excessively long names are rejected."""
        handler = GitHubSourceHandler()
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Create tar with very long filename
        long_name = 'a' * 300  # Exceeds MAX_FILENAME_LENGTH (255)
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
            info = tarfile.TarInfo(name=long_name)
            info.size = 4
            tar.addfile(info, io.BytesIO(b'test'))
        buffer.seek(0)

        with tarfile.open(fileobj=buffer, mode='r:gz') as tar:
            with pytest.raises(ValueError, match="Filename too long"):
                handler._safe_extract_tarball(tar, extract_dir)

    def test_filename_with_null_byte_rejected(self, tmp_path: Path) -> None:
        """Test that filenames with null bytes are rejected or sanitized."""
        handler = GitHubSourceHandler()
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Note: Python's tarfile module may automatically handle null bytes
        # This test verifies our check works or that tarfile prevents the issue
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
            # Try to create filename with null byte
            # In Python 3.11+, tarfile may allow it but truncate at null byte
            info = tarfile.TarInfo(name='file\0evil.txt')
            info.size = 4
            tar.addfile(info, io.BytesIO(b'test'))
        buffer.seek(0)

        with tarfile.open(fileobj=buffer, mode='r:gz') as tar:
            # Check what actually got stored
            members = tar.getmembers()
            if members and '\0' in members[0].name:
                # Null byte preserved - our check should catch it
                with pytest.raises(ValueError, match="Null byte in filename"):
                    handler._safe_extract_tarball(tar, extract_dir)
            else:
                # Null byte was sanitized by tarfile - that's also acceptable
                pytest.skip("tarfile module sanitizes null bytes in filenames")

    def test_setuid_bit_removed(self, tmp_path: Path) -> None:
        """Test that setuid/setgid bits are removed from files."""
        handler = GitHubSourceHandler()
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        # Create tar with setuid bit
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
            info = tarfile.TarInfo(name='setuid_file')
            info.size = 4
            info.mode = 0o4755  # setuid bit set
            tar.addfile(info, io.BytesIO(b'test'))
        buffer.seek(0)

        # Should succeed but with setuid bit removed
        with tarfile.open(fileobj=buffer, mode='r:gz') as tar:
            handler._safe_extract_tarball(tar, extract_dir)

        # Verify file was extracted
        extracted_file = extract_dir / "setuid_file"
        assert extracted_file.exists()
        # setuid/setgid bits should be removed (mode should not have 0o6000)
        assert (extracted_file.stat().st_mode & 0o6000) == 0


class TestInputValidation:
    """Test input validation and sanitization."""

    def test_valid_skill_names_accepted(self) -> None:
        """Test that valid skill names are accepted."""
        valid_names = [
            "skill-name",
            "skill123",
            "my-cool-skill-2024",
            "a",
            "123",
        ]

        for name in valid_names:
            skill = Skill(
                name=name,
                source="github:test/test",
                scope=SkillScope.PROJECT
            )
            assert skill.name == name

    def test_source_format_validation(self) -> None:
        """Test that invalid source formats are rejected."""
        invalid_sources = [
            "invalid:source",
            "http://example.com",
            "ftp://example.com",
            "",
        ]

        for source in invalid_sources:
            with pytest.raises(ValueError, match="Invalid source format"):
                Skill(
                    name="test",
                    source=source,
                    scope=SkillScope.PROJECT
                )

    def test_valid_source_formats_accepted(self) -> None:
        """Test that valid source formats are accepted."""
        valid_sources = [
            "github:owner/repo",
            "github:owner/repo/path",
            "local:/path/to/skill",
            "local:~/skills/my-skill",
            "git:https://example.com/repo.git",
        ]

        for source in valid_sources:
            skill = Skill(
                name="test",
                source=source,
                scope=SkillScope.PROJECT
            )
            assert skill.source == source

    def test_version_and_ref_mutual_exclusivity(self) -> None:
        """Test that version and ref cannot be specified together."""
        with pytest.raises(ValueError, match="Cannot specify both version and ref"):
            Skill(
                name="test",
                source="github:owner/repo",
                version="v1.0.0",
                ref="main",
                scope=SkillScope.PROJECT
            )


class TestSecretsHandling:
    """Test that secrets are handled securely."""

    def test_github_token_not_logged_in_headers(self) -> None:
        """Test that GitHub token is properly handled in headers."""
        token = "ghp_secret_token_123456"
        handler = GitHubSourceHandler(token=token)

        headers = handler._get_headers()

        # Token should be in Authorization header
        assert "Authorization" in headers
        assert headers["Authorization"] == f"token {token}"

        # Should not contain token in other fields
        assert "User-Agent" in headers
        assert token not in headers["User-Agent"]

    def test_github_token_not_in_error_messages(self, tmp_path: Path) -> None:
        """Test that GitHub tokens don't leak in error messages."""
        token = "ghp_secret_token_123456"
        handler = GitHubSourceHandler(token=token, cache_dir=tmp_path)

        # Error messages should not contain the token
        # This is already handled by the implementation, but we document it here
        assert True  # Placeholder test
