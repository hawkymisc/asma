"""GitHub source handler."""
import hashlib
import re
import shutil
import tarfile
import tempfile
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

    def __init__(
        self,
        token: Optional[str] = None,
        cache_dir: Optional[Path] = None
    ):
        """
        Initialize GitHub source handler.

        Args:
            token: GitHub API token for authentication
            cache_dir: Directory for caching downloaded tarballs
        """
        self.token = token
        self.cache_dir = cache_dir or Path.home() / ".cache" / "asma" / "github"
        self._pending_subpath: Optional[str] = None

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

        return response.json()

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
                tar.extractall(path=extract_dir, filter="data")
        except tarfile.TarError as e:
            shutil.rmtree(extract_dir, ignore_errors=True)
            raise ValueError(f"Failed to extract tarball: {e}")

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
