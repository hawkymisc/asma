"""Skill fetcher for retrieving skill metadata from sources."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from asma.core.sources.base import SourceHandler
from asma.core.sources.github import GitHubSourceHandler
from asma.core.sources.local import LocalSourceHandler
from asma.core.validator import SkillValidator
from asma.models.skill import Skill, SkillScope


@dataclass
class FetchResult:
    """Result of fetching skill metadata."""

    success: bool
    name: Optional[str] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    version: Optional[str] = None


class SkillFetcher:
    """Fetches skill metadata from various sources."""

    def __init__(
        self,
        github_token: Optional[str] = None,
        cache_dir: Optional[Path] = None
    ):
        """
        Initialize skill fetcher.

        Args:
            github_token: Optional GitHub API token for authentication
            cache_dir: Optional cache directory for GitHub downloads
        """
        self.github_token = github_token
        self.cache_dir = cache_dir

    def get_source_handler(self, source: str) -> SourceHandler:
        """
        Get appropriate source handler for the source type.

        Args:
            source: Source string (github:... or local:...)

        Returns:
            SourceHandler instance for the source type

        Raises:
            ValueError: If source type is not supported
        """
        if source.startswith("local:"):
            return LocalSourceHandler()
        elif source.startswith("github:"):
            return GitHubSourceHandler(
                token=self.github_token,
                cache_dir=self.cache_dir
            )
        else:
            raise ValueError(
                f"Unsupported source type: {source}. "
                f"Supported formats: github:owner/repo[/path], local:/path/to/skill"
            )

    def fetch_metadata(self, source: str) -> FetchResult:
        """
        Fetch skill metadata from source.

        Args:
            source: Source string (github:... or local:...)

        Returns:
            FetchResult with metadata or error
        """
        try:
            # Create a temporary skill object for resolution
            # Use a placeholder name since we'll get real name from frontmatter
            temp_skill = Skill(
                name="temp-fetch",
                source=source,
                scope=SkillScope.PROJECT  # Scope doesn't matter for fetching
            )

            handler = self.get_source_handler(source)

            # Resolve source
            resolved = handler.resolve(temp_skill)

            # Download to get the files
            source_path = handler.download(resolved)

            # Validate and get metadata
            validation = SkillValidator.validate(source_path)

            if not validation.valid:
                return FetchResult(
                    success=False,
                    error=f"Invalid skill: {', '.join(validation.errors)}"
                )

            # Extract metadata from validation result
            metadata = validation.metadata
            name = metadata.get("name")
            description = metadata.get("description")

            if not name:
                return FetchResult(
                    success=False,
                    error="SKILL.md missing required 'name' field"
                )

            return FetchResult(
                success=True,
                name=name,
                description=description,
                metadata=metadata,
                version=resolved.version
            )

        except FileNotFoundError as e:
            return FetchResult(
                success=False,
                error=f"Source not found: {e}"
            )
        except PermissionError as e:
            return FetchResult(
                success=False,
                error=f"Permission denied: {e}"
            )
        except ConnectionError as e:
            return FetchResult(
                success=False,
                error=f"Connection error: {e}"
            )
        except ValueError as e:
            return FetchResult(
                success=False,
                error=str(e)
            )
        except Exception as e:
            return FetchResult(
                success=False,
                error=f"Unexpected error: {e}"
            )
