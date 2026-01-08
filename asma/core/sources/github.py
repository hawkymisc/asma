"""GitHub source handler."""
import hashlib
import re
import shutil
import sys
import tarfile
import tempfile
import warnings
from pathlib import Path
from typing import Optional, Tuple

import requests

from asma.core.sources.base import ResolvedSource, SourceHandler
from asma.models.skill import Skill


def parse_github_source(source: str) -> Tuple[str, str, Optional[str]]:
    """
    Parse github:owner/repo[/path] format.

    Args:
        source: Source string like "github:owner/repo" or "github:owner/repo/path"

    Returns:
        Tuple of (owner, repo, path) where path may be None

    Raises:
        ValueError: If format is invalid
    """
    if not source.startswith("github:"):
        raise ValueError(f"Invalid GitHub source format: {source}")

    # Remove "github:" prefix
    path_part = source[7:]  # len("github:") == 7

    parts = path_part.split("/")
    if len(parts) < 2:
        raise ValueError(f"Invalid GitHub source format: {source}")

    owner = parts[0]
    repo = parts[1]
    subpath = "/".join(parts[2:]) if len(parts) > 2 else None

    return owner, repo, subpath


class GitHubSourceHandler(SourceHandler):
    """Handle github:owner/repo sources."""

    API_BASE = "https://api.github.com"

    # Security limits for tar extraction (tar bomb protection)
    MAX_EXTRACT_SIZE = 500 * 1024 * 1024  # 500 MB total
    MAX_FILE_COUNT = 10000  # Maximum number of files
    MAX_SINGLE_FILE_SIZE = 100 * 1024 * 1024  # 100 MB per file
    MAX_FILENAME_LENGTH = 255  # Standard filesystem limit

    def __init__(
        self,
        token: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        strict: bool = False
    ):
        """
        Initialize GitHub source handler.

        Args:
            token: GitHub API token for authentication
            cache_dir: Directory for caching downloaded tarballs
            strict: If True, raise error when version/ref not specified.
                    If False (default), emit warning and use default branch.
        """
        self.token = token
        self.cache_dir = cache_dir or Path.home() / ".cache" / "asma" / "github"
        self.strict = strict
        self._pending_subpath: Optional[str] = None

    def _safe_extract_tarball(self, tar: tarfile.TarFile, extract_dir: Path) -> None:
        """
        Safely extract tarball with comprehensive security checks.

        This method provides backward compatibility for Python 3.8-3.11
        while using the secure filter parameter on Python 3.12+.

        Protection against:
        - Path traversal attacks (CVE-2007-4559)
        - Tar bomb attacks (compression bombs)
        - Device files and special files
        - Excessively long filenames
        - Malicious symlinks

        Args:
            tar: Open tarfile object
            extract_dir: Directory to extract to

        Raises:
            ValueError: If tarball contains dangerous content or exceeds limits
        """
        if sys.version_info >= (3, 12):
            # Python 3.12+: use built-in data filter for secure extraction
            # Still need to check for tar bomb even with filter
            total_size = 0
            file_count = 0

            for member in tar.getmembers():
                # Tar bomb protection: check file count
                file_count += 1
                if file_count > self.MAX_FILE_COUNT:
                    raise ValueError(
                        f"Tar archive contains too many files (>{self.MAX_FILE_COUNT}). "
                        f"Possible tar bomb attack."
                    )

                # Tar bomb protection: check individual file size
                if member.size > self.MAX_SINGLE_FILE_SIZE:
                    raise ValueError(
                        f"File too large in tar: {member.name} ({member.size} bytes, "
                        f"max {self.MAX_SINGLE_FILE_SIZE}). Possible tar bomb attack."
                    )

                # Tar bomb protection: check total extracted size
                total_size += member.size
                if total_size > self.MAX_EXTRACT_SIZE:
                    raise ValueError(
                        f"Total extracted size exceeds limit ({total_size} bytes, "
                        f"max {self.MAX_EXTRACT_SIZE}). Possible tar bomb attack."
                    )

            tar.extractall(path=extract_dir, filter="data")
        else:
            # Python 3.8-3.11: manual validation for security
            safe_members = []
            extract_dir_resolved = extract_dir.resolve()
            total_size = 0
            file_count = 0

            for member in tar.getmembers():
                # Tar bomb protection: check file count
                file_count += 1
                if file_count > self.MAX_FILE_COUNT:
                    raise ValueError(
                        f"Tar archive contains too many files (>{self.MAX_FILE_COUNT}). "
                        f"Possible tar bomb attack."
                    )

                # Tar bomb protection: check individual file size
                if member.size > self.MAX_SINGLE_FILE_SIZE:
                    raise ValueError(
                        f"File too large in tar: {member.name} ({member.size} bytes, "
                        f"max {self.MAX_SINGLE_FILE_SIZE}). Possible tar bomb attack."
                    )

                # Tar bomb protection: check total extracted size
                total_size += member.size
                if total_size > self.MAX_EXTRACT_SIZE:
                    raise ValueError(
                        f"Total extracted size exceeds limit ({total_size} bytes, "
                        f"max {self.MAX_EXTRACT_SIZE}). Possible tar bomb attack."
                    )

                # Filename length check
                if len(member.name) > self.MAX_FILENAME_LENGTH:
                    raise ValueError(
                        f"Filename too long in tar: {member.name[:50]}... "
                        f"({len(member.name)} chars, max {self.MAX_FILENAME_LENGTH})"
                    )

                # Check for null bytes in filename
                if '\0' in member.name:
                    raise ValueError(f"Null byte in filename: {member.name}")

                # Check for device files and FIFOs
                if member.isdev():
                    raise ValueError(
                        f"Device file not allowed in tar: {member.name}"
                    )

                if member.isfifo():
                    raise ValueError(
                        f"FIFO (named pipe) not allowed in tar: {member.name}"
                    )

                # Remove setuid/setgid bits for security
                if member.mode & 0o6000:  # Check for setuid (4000) or setgid (2000)
                    member.mode &= 0o1777  # Remove setuid/setgid, keep other bits

                # Resolve member path and ensure it's within extract_dir
                member_path = (extract_dir / member.name).resolve()

                # Check for path traversal
                try:
                    member_path.relative_to(extract_dir_resolved)
                except ValueError:
                    raise ValueError(
                        f"Attempted path traversal in tar archive: {member.name}"
                    )

                # Check for absolute paths
                if Path(member.name).is_absolute():
                    raise ValueError(
                        f"Absolute path in tar archive: {member.name}"
                    )

                # Validate symlinks and hardlinks
                if member.issym() or member.islnk():
                    link_target = Path(member.linkname)

                    # Reject absolute link targets
                    if link_target.is_absolute():
                        raise ValueError(
                            f"Absolute symlink target in tar: {member.name} -> {member.linkname}"
                        )

                    # Reject links with path traversal
                    if ".." in link_target.parts:
                        raise ValueError(
                            f"Path traversal in symlink: {member.name} -> {member.linkname}"
                        )

                    # Resolve link target and ensure it's within extract_dir
                    link_dest = (extract_dir / member.name).parent / member.linkname
                    try:
                        link_dest.resolve().relative_to(extract_dir_resolved)
                    except ValueError:
                        raise ValueError(
                            f"Symlink target outside extraction directory: "
                            f"{member.name} -> {member.linkname}"
                        )

                safe_members.append(member)

            # Extract only validated members
            tar.extractall(path=extract_dir, members=safe_members)

    def _get_headers(self) -> dict:
        """Get headers for GitHub API requests."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "asma-skill-manager"
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def _api_request(self, endpoint: str) -> dict:
        """
        Make a GitHub API request.

        Args:
            endpoint: API endpoint (e.g., "/repos/owner/repo")

        Returns:
            JSON response as dict

        Raises:
            FileNotFoundError: If resource not found (404)
            PermissionError: If authentication fails or rate limited
            ConnectionError: If network error occurs
        """
        url = f"{self.API_BASE}{endpoint}"
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=30)
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Failed to connect to GitHub API: {e}")

        if response.status_code == 404:
            raise FileNotFoundError(f"Repository not found: {endpoint}")
        elif response.status_code == 401:
            raise PermissionError("GitHub authentication failed: invalid token")
        elif response.status_code == 403:
            message = response.json().get("message", "")
            if "rate limit" in message.lower():
                raise PermissionError(f"GitHub API rate limit exceeded: {message}")
            raise PermissionError(f"GitHub access denied: {message}")
        elif response.status_code != 200:
            raise ConnectionError(f"GitHub API error: {response.status_code}")

        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("Expected JSON object from GitHub API")
        return result

    def resolve(self, skill: Skill) -> ResolvedSource:
        """
        Resolve GitHub source to downloadable information.

        Args:
            skill: Skill with github: source

        Returns:
            ResolvedSource with download_url

        Raises:
            FileNotFoundError: If repository not found
            PermissionError: If authentication fails
            ValueError: If source format is invalid
        """
        owner, repo, subpath = parse_github_source(skill.source)
        self._pending_subpath = subpath

        # Determine ref to use
        if skill.ref:
            # Use specified ref directly
            ref = skill.ref
        elif skill.version:
            if skill.version == "latest":
                # Fetch latest release
                data = self._api_request(f"/repos/{owner}/{repo}/releases/latest")
                ref = data["tag_name"]
            else:
                # Use version as tag
                ref = skill.version
        else:
            # No version or ref specified
            if self.strict:
                raise ValueError(
                    f"Version not specified for skill '{skill.name}'. "
                    f"In strict mode, you must specify 'version' or 'ref' in skillset.yaml."
                )

            # Emit warning and use default branch
            warnings.warn(
                f"No version specified for skill '{skill.name}'. "
                f"Using default branch. Consider pinning a version for reproducibility.",
                UserWarning,
                stacklevel=2
            )

            # Get default branch
            data = self._api_request(f"/repos/{owner}/{repo}")
            ref = data["default_branch"]

        # Build download URL
        download_url = f"{self.API_BASE}/repos/{owner}/{repo}/tarball/{ref}"

        return ResolvedSource(
            version=ref,
            commit=ref,
            download_url=download_url
        )

    def download(self, resolved: ResolvedSource) -> Path:
        """
        Download and extract tarball from GitHub.

        Args:
            resolved: Resolved source with download_url

        Returns:
            Path to the extracted skill directory

        Raises:
            ConnectionError: If download fails
            ValueError: If tarball is invalid
        """
        if not resolved.download_url:
            raise ValueError("ResolvedSource must have download_url for GitHub sources")

        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Generate cache key from URL
        url_hash = hashlib.sha256(resolved.download_url.encode()).hexdigest()[:16]
        cache_key = f"{url_hash}_{resolved.version}"
        extract_dir = self.cache_dir / cache_key

        # Check cache
        if extract_dir.exists():
            return self._get_skill_path(extract_dir)

        # Download tarball
        try:
            response = requests.get(
                resolved.download_url,
                headers=self._get_headers(),
                stream=True,
                timeout=60
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Failed to download from GitHub: {e}")

        # Extract tarball
        extract_dir.mkdir(parents=True, exist_ok=True)
        try:
            with tarfile.open(fileobj=response.raw, mode="r|gz") as tar:
                self._safe_extract_tarball(tar, extract_dir)
        except tarfile.TarError as e:
            shutil.rmtree(extract_dir, ignore_errors=True)
            raise ValueError(f"Failed to extract tarball: {e}")
        except ValueError as e:
            # Security validation error
            shutil.rmtree(extract_dir, ignore_errors=True)
            raise

        return self._get_skill_path(extract_dir)

    def _get_skill_path(self, extract_dir: Path) -> Path:
        """
        Get the skill directory path from extracted tarball.

        GitHub tarballs have a root directory like "repo-ref/".
        If subpath is specified, navigate to that directory.

        Args:
            extract_dir: Directory where tarball was extracted

        Returns:
            Path to the skill directory (containing SKILL.md)
        """
        # Find the root directory (GitHub creates one directory)
        contents = list(extract_dir.iterdir())
        if len(contents) == 1 and contents[0].is_dir():
            root_dir = contents[0]
        else:
            root_dir = extract_dir

        # Navigate to subpath if specified
        if self._pending_subpath:
            skill_path = root_dir / self._pending_subpath
        else:
            skill_path = root_dir

        return skill_path

    def should_symlink(self) -> bool:
        """GitHub sources should be copied, not symlinked."""
        return False
