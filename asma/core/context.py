"""Context extractor module for reading skill metadata."""
import json
import re
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, List

from asma.models.lock import LockEntry
from asma.models.skill import SkillScope


@dataclass
class SkillContext:
    """Extracted context from a skill's SKILL.md frontmatter."""

    skill_name: str
    scope: SkillScope
    metadata: Dict[str, Any]
    install_path: Path
    error: Optional[str] = None


class ContextExtractor:
    """Extract and format context from installed skills."""

    def get_install_path(self, entry: LockEntry) -> Path:
        """
        Get the expected install path for a skill.

        Args:
            entry: Lock file entry for the skill

        Returns:
            Path where the skill should be installed
        """
        if entry.scope == SkillScope.GLOBAL:
            return Path.home() / ".claude/skills" / entry.name
        else:
            return Path.cwd() / ".claude/skills" / entry.name

    def extract_context(
        self,
        entry: LockEntry,
        base_path: Optional[Path] = None,
    ) -> SkillContext:
        """
        Extract context (frontmatter) from a skill's SKILL.md.

        Args:
            entry: Lock file entry for the skill
            base_path: Optional base path override (for testing)

        Returns:
            SkillContext with metadata or error
        """
        # Determine install path
        if base_path is not None:
            install_path = base_path / ".claude/skills" / entry.name
        else:
            install_path = self.get_install_path(entry)

        skill_md_path = install_path / "SKILL.md"

        # Check if skill exists
        if not install_path.exists() or not skill_md_path.exists():
            return SkillContext(
                skill_name=entry.name,
                scope=entry.scope,
                metadata={},
                install_path=install_path,
                error=f"SKILL.md not found at {skill_md_path}",
            )

        # Read and parse frontmatter
        try:
            content = skill_md_path.read_text()
            metadata = self._parse_frontmatter(content)

            if metadata is None:
                return SkillContext(
                    skill_name=entry.name,
                    scope=entry.scope,
                    metadata={},
                    install_path=install_path,
                    error="Invalid or missing YAML frontmatter",
                )

            return SkillContext(
                skill_name=entry.name,
                scope=entry.scope,
                metadata=metadata,
                install_path=install_path,
            )

        except Exception as e:
            return SkillContext(
                skill_name=entry.name,
                scope=entry.scope,
                metadata={},
                install_path=install_path,
                error=str(e),
            )

    def _parse_frontmatter(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Extract YAML frontmatter from markdown content.

        Args:
            content: Markdown file content

        Returns:
            Parsed frontmatter as dict, or None if not found/invalid
        """
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if not match:
            return None

        try:
            result = yaml.safe_load(match.group(1))
            return result if isinstance(result, dict) else None
        except yaml.YAMLError:
            return None

    def format_text(self, contexts: List[SkillContext]) -> str:
        """
        Format contexts as human-readable text.

        Args:
            contexts: List of SkillContext objects

        Returns:
            Formatted text output
        """
        lines = ["Installed Skills Context:", ""]

        # Group by scope
        global_contexts = [c for c in contexts if c.scope == SkillScope.GLOBAL]
        project_contexts = [c for c in contexts if c.scope == SkillScope.PROJECT]

        # Format global skills
        if global_contexts:
            lines.append("Global Skills:")
            for ctx in sorted(global_contexts, key=lambda c: c.skill_name):
                lines.extend(self._format_context_text(ctx))
            lines.append("")

        # Format project skills
        if project_contexts:
            lines.append("Project Skills:")
            for ctx in sorted(project_contexts, key=lambda c: c.skill_name):
                lines.extend(self._format_context_text(ctx))
            lines.append("")

        return "\n".join(lines)

    def _format_context_text(self, ctx: SkillContext) -> List[str]:
        """Format a single context as text lines."""
        lines = [f"  {ctx.skill_name}:"]

        if ctx.error:
            lines.append(f"    error: {ctx.error}")
        else:
            for key, value in ctx.metadata.items():
                if isinstance(value, list):
                    lines.append(f"    {key}:")
                    for item in value:
                        lines.append(f"      - {item}")
                else:
                    lines.append(f"    {key}: {value}")

        lines.append("")
        return lines

    def format_yaml(self, contexts: List[SkillContext]) -> str:
        """
        Format contexts as YAML.

        Args:
            contexts: List of SkillContext objects

        Returns:
            YAML formatted output
        """
        data = self._build_output_dict(contexts)
        return yaml.safe_dump(data, default_flow_style=False, sort_keys=False)

    def format_json(self, contexts: List[SkillContext]) -> str:
        """
        Format contexts as JSON.

        Args:
            contexts: List of SkillContext objects

        Returns:
            JSON formatted output
        """
        data = self._build_output_dict(contexts)
        return json.dumps(data, indent=2)

    def _build_output_dict(self, contexts: List[SkillContext]) -> Dict[str, Any]:
        """Build output dictionary from contexts."""
        data: Dict[str, Dict[str, Any]] = {
            "global": {},
            "project": {},
        }

        for ctx in contexts:
            scope_key = "global" if ctx.scope == SkillScope.GLOBAL else "project"
            if ctx.error:
                data[scope_key][ctx.skill_name] = {"error": ctx.error}
            else:
                data[scope_key][ctx.skill_name] = ctx.metadata

        return data
