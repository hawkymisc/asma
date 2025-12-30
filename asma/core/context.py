"""Context extractor module for reading skill metadata."""
import json
import re
import shutil
import textwrap
import yaml
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Optional, Dict, Any, List

from rich.console import Console
from rich.table import Table

from asma.models.lock import LockEntry
from asma.models.skill import SkillScope

# Basic fields to display by default (non-verbose mode)
BASIC_FIELDS = {"name", "description", "version"}


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

    def format_text(
        self,
        contexts: List[SkillContext],
        indent: int = 2,
        wrap_width: Optional[int] = None,
        verbose: bool = False,
    ) -> str:
        """
        Format contexts as human-readable text.

        Args:
            contexts: List of SkillContext objects
            indent: Number of spaces for indentation (default: 2)
            wrap_width: Width for text wrapping (None = terminal width)
            verbose: If True, show all metadata fields; if False, show only basic fields

        Returns:
            Formatted text output
        """
        # Determine wrap width
        if wrap_width is None:
            wrap_width = shutil.get_terminal_size().columns

        lines = ["Installed Skills Context:", ""]

        # Group by scope
        global_contexts = [c for c in contexts if c.scope == SkillScope.GLOBAL]
        project_contexts = [c for c in contexts if c.scope == SkillScope.PROJECT]

        # Format global skills
        if global_contexts:
            lines.append("Global Skills:")
            for ctx in sorted(global_contexts, key=lambda c: c.skill_name):
                lines.extend(self._format_context_text(ctx, indent, wrap_width, verbose))
            lines.append("")

        # Format project skills
        if project_contexts:
            lines.append("Project Skills:")
            for ctx in sorted(project_contexts, key=lambda c: c.skill_name):
                lines.extend(self._format_context_text(ctx, indent, wrap_width, verbose))
            lines.append("")

        return "\n".join(lines)

    def _format_context_text(
        self,
        ctx: SkillContext,
        indent: int = 2,
        wrap_width: int = 80,
        verbose: bool = False,
    ) -> List[str]:
        """Format a single context as text lines."""
        indent_str = " " * indent
        double_indent = " " * (indent * 2)

        lines = [f"{indent_str}{ctx.skill_name}:"]

        if ctx.error:
            error_line = f"{double_indent}error: {ctx.error}"
            if len(error_line) > wrap_width:
                lines.extend(self._wrap_text(
                    "error", ctx.error, double_indent, wrap_width
                ))
            else:
                lines.append(error_line)
        else:
            # Filter fields based on verbose mode
            fields_to_show = ctx.metadata.items()
            if not verbose:
                fields_to_show = [
                    (k, v) for k, v in ctx.metadata.items()
                    if k in BASIC_FIELDS
                ]

            for key, value in fields_to_show:
                if isinstance(value, list):
                    lines.append(f"{double_indent}{key}:")
                    triple_indent = " " * (indent * 3)
                    for item in value:
                        item_line = f"{triple_indent}- {item}"
                        if len(item_line) > wrap_width:
                            # Wrap list item
                            wrapped = textwrap.wrap(
                                str(item),
                                width=wrap_width - len(triple_indent) - 2,
                            )
                            lines.append(f"{triple_indent}- {wrapped[0]}")
                            for cont in wrapped[1:]:
                                lines.append(f"{triple_indent}  {cont}")
                        else:
                            lines.append(item_line)
                else:
                    full_line = f"{double_indent}{key}: {value}"
                    if len(full_line) > wrap_width:
                        lines.extend(self._wrap_text(
                            key, str(value), double_indent, wrap_width
                        ))
                    else:
                        lines.append(full_line)

        lines.append("")
        return lines

    def _wrap_text(
        self,
        key: str,
        value: str,
        base_indent: str,
        wrap_width: int,
    ) -> List[str]:
        """Wrap a key-value pair across multiple lines."""
        prefix = f"{base_indent}{key}: "
        subsequent_indent = base_indent + " " * (len(key) + 2)

        wrapper = textwrap.TextWrapper(
            width=wrap_width,
            initial_indent=prefix,
            subsequent_indent=subsequent_indent,
        )
        return wrapper.wrap(value)

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

    def format_table(
        self,
        contexts: List[SkillContext],
        verbose: bool = False,
    ) -> str:
        """
        Format contexts as a rich table.

        Args:
            contexts: List of SkillContext objects
            verbose: If True, show additional columns for extra metadata

        Returns:
            Formatted table output as string
        """
        table = Table(title="Installed Skills Context")

        # Add basic columns
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Scope", style="magenta")
        table.add_column("Description", style="white")
        table.add_column("Version", style="green")

        # Add extra columns in verbose mode
        if verbose:
            table.add_column("Author", style="yellow")

        # Sort contexts by scope then name
        sorted_contexts = sorted(
            contexts,
            key=lambda c: (c.scope.value, c.skill_name)
        )

        for ctx in sorted_contexts:
            if ctx.error:
                row = [
                    ctx.skill_name,
                    ctx.scope.value,
                    f"[red]Error: {ctx.error}[/red]",
                    "-",
                ]
                if verbose:
                    row.append("-")
            else:
                row = [
                    ctx.skill_name,
                    ctx.scope.value,
                    str(ctx.metadata.get("description", "-")),
                    str(ctx.metadata.get("version", "-")),
                ]
                if verbose:
                    row.append(str(ctx.metadata.get("author", "-")))

            table.add_row(*row)

        # Render table to string
        console = Console(file=StringIO(), force_terminal=True)
        console.print(table)
        return console.file.getvalue()
