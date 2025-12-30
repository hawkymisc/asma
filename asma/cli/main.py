"""Main CLI entry point for asma."""
import click
from pathlib import Path
from asma import __version__


SKILLSET_TEMPLATE = """# Agent Skills Manager Configuration
# See: https://github.com/hawkymisc/asma

# Global configuration
config:
  auto_update: false
  parallel_downloads: 4
  github_token_env: GITHUB_TOKEN

# Global skills (installed to ~/.claude/skills/)
global:
  # Example:
  # - name: document-analyzer
  #   source: github:anthropics/skills/document-analyzer
  #   version: v1.0.0

# Project skills (installed to .claude/skills/)
project:
  # Example:
  # - name: test-runner
  #   source: github:anthropics/skills/test-runner
  #   version: v2.1.0
"""


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """asma - Agent Skills Manager

    A declarative package manager for Claude Agent Skills.
    """
    pass


@cli.command()
@click.option('--force', is_flag=True, help='Overwrite existing skillset.yaml')
def init(force: bool) -> None:
    """Initialize a new skillset.yaml file."""
    skillset_path = Path("skillset.yaml")

    # Check if file already exists
    if skillset_path.exists() and not force:
        click.echo(
            click.style("Error: ", fg="red", bold=True) +
            "skillset.yaml already exists. Use --force to overwrite."
        )
        raise click.Abort()

    # Write template
    skillset_path.write_text(SKILLSET_TEMPLATE)

    click.echo(
        click.style("✓ ", fg="green") +
        "Created skillset.yaml"
    )
    click.echo("  Edit this file to add your skills, then run: asma install")


@cli.command()
def version() -> None:
    """Show asma version."""
    click.echo(f"asma version {__version__}")


@cli.command()
@click.option('--scope', type=click.Choice(['global', 'project']), help='Filter by scope')
def list(scope: str) -> None:
    """List installed skills."""
    from asma.models.lock import Lockfile
    from asma.models.skill import SkillScope

    # Load lock file
    lock_path = Path("skillset.lock")

    if not lock_path.exists():
        click.echo("No skills installed (skillset.lock not found)")
        return

    try:
        lockfile = Lockfile.load(lock_path)
    except Exception as e:
        click.echo(
            click.style("Error: ", fg="red", bold=True) +
            f"Failed to load skillset.lock: {e}"
        )
        raise click.Abort()

    # Filter skills by scope if specified
    skills = lockfile.skills
    if scope:
        target_scope = SkillScope.GLOBAL if scope == 'global' else SkillScope.PROJECT
        skills = {
            key: entry for key, entry in skills.items()
            if entry.scope == target_scope
        }

    if not skills:
        click.echo("No skills installed")
        return

    # Group skills by scope
    global_skills = []
    project_skills = []

    for key, entry in skills.items():
        if entry.scope == SkillScope.GLOBAL:
            global_skills.append(entry)
        else:
            project_skills.append(entry)

    # Display global skills
    if global_skills:
        click.echo(click.style("Global Skills:", fg="cyan", bold=True))
        for entry in sorted(global_skills, key=lambda e: e.name):
            click.echo(f"  • {entry.name}")
            click.echo(f"    Source: {entry.source}")
            click.echo(f"    Version: {entry.resolved_version}")
        click.echo()

    # Display project skills
    if project_skills:
        click.echo(click.style("Project Skills:", fg="cyan", bold=True))
        for entry in sorted(project_skills, key=lambda e: e.name):
            click.echo(f"  • {entry.name}")
            click.echo(f"    Source: {entry.source}")
            click.echo(f"    Version: {entry.resolved_version}")
        click.echo()


@cli.command()
@click.option('--scope', type=click.Choice(['global', 'project']), help='Check only specified scope')
@click.option('--checksum', is_flag=True, help='Also verify SKILL.md checksums')
@click.option('--quiet', is_flag=True, help='Only show errors')
def check(scope: str, checksum: bool, quiet: bool) -> None:
    """Check that installed skills exist on filesystem."""
    import sys
    from asma.models.lock import Lockfile
    from asma.models.skill import SkillScope
    from asma.core.checker import SkillChecker, CheckResult

    # Load lock file
    lock_path = Path("skillset.lock")

    if not lock_path.exists():
        click.echo(
            click.style("Error: ", fg="red", bold=True) +
            "skillset.lock not found. Run 'asma install' first."
        )
        sys.exit(2)

    try:
        lockfile = Lockfile.load(lock_path)
    except Exception as e:
        click.echo(
            click.style("Error: ", fg="red", bold=True) +
            f"Failed to load skillset.lock: {e}"
        )
        sys.exit(2)

    # Filter skills by scope if specified
    skills = lockfile.skills
    if scope:
        target_scope = SkillScope.GLOBAL if scope == 'global' else SkillScope.PROJECT
        skills = {
            key: entry for key, entry in skills.items()
            if entry.scope == target_scope
        }

    if not skills:
        if not quiet:
            click.echo("No skills to check")
        sys.exit(0)

    # Check skills
    checker = SkillChecker()
    results: list[CheckResult] = []

    if not quiet:
        msg = "Checking installed skills"
        if checksum:
            msg += " (with checksum)"
        click.echo(f"{msg}...")

    for key, entry in skills.items():
        result = checker.check_skill(entry, verify_checksum=checksum)
        results.append(result)

        # Display result
        if result.status == "ok":
            if not quiet:
                click.echo(
                    click.style("✓ ", fg="green") +
                    f"{entry.name} ({entry.scope.value}) - OK"
                )
        elif result.status == "checksum_mismatch":
            click.echo(
                click.style("! ", fg="yellow") +
                f"{entry.name} ({entry.scope.value}) - checksum mismatch"
            )
        else:
            click.echo(
                click.style("✗ ", fg="red") +
                f"{entry.name} ({entry.scope.value}) - {result.error_message or result.status}"
            )

    # Summary
    ok_count = sum(1 for r in results if r.status == "ok")
    missing_count = sum(1 for r in results if r.status in ("missing", "broken_symlink"))
    mismatch_count = sum(1 for r in results if r.status == "checksum_mismatch")
    total = len(results)

    if not quiet:
        click.echo()
        click.echo(f"Checked: {ok_count}/{total} skills OK")
        if missing_count > 0:
            click.echo(f"Missing: {missing_count} skill(s) (run 'asma install' to fix)")
        if mismatch_count > 0:
            click.echo(f"Modified: {mismatch_count} skill(s) (reinstall with 'asma install --force')")

    # Exit code
    if missing_count > 0 or mismatch_count > 0:
        sys.exit(1)
    sys.exit(0)


@cli.command()
@click.argument('skill_name', required=False)
@click.option('--scope', type=click.Choice(['global', 'project']), help='Filter by scope')
@click.option(
    '--format', 'output_format',
    type=click.Choice(['text', 'yaml', 'json', 'table']),
    default='text',
    help='Output format (text, yaml, json, table)'
)
@click.option(
    '--wrap-width', 'wrap_width',
    type=int,
    default=None,
    help='Text wrap width for descriptions (default: terminal width)'
)
@click.option(
    '--indent',
    type=int,
    default=2,
    help='Indentation width in spaces (default: 2)'
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='Show all metadata fields (default: name, description, version only)'
)
def context(
    skill_name: str,
    scope: str,
    output_format: str,
    wrap_width: int,
    indent: int,
    verbose: bool,
) -> None:
    """Display context (SKILL.md frontmatter) of installed skills."""
    from asma.models.lock import Lockfile
    from asma.models.skill import SkillScope
    from asma.core.context import ContextExtractor, SkillContext

    # Load lock file
    lock_path = Path("skillset.lock")

    if not lock_path.exists():
        click.echo(
            click.style("Error: ", fg="red", bold=True) +
            "skillset.lock not found. Run 'asma install' first."
        )
        raise click.Abort()

    try:
        lockfile = Lockfile.load(lock_path)
    except Exception as e:
        click.echo(
            click.style("Error: ", fg="red", bold=True) +
            f"Failed to load skillset.lock: {e}"
        )
        raise click.Abort()

    # Filter skills by scope if specified
    skills = lockfile.skills
    if scope:
        target_scope = SkillScope.GLOBAL if scope == 'global' else SkillScope.PROJECT
        skills = {
            key: entry for key, entry in skills.items()
            if entry.scope == target_scope
        }

    # Filter by skill name if specified
    if skill_name:
        skills = {
            key: entry for key, entry in skills.items()
            if entry.name == skill_name
        }

    if not skills:
        if output_format == 'json':
            click.echo('{"global": {}, "project": {}}')
        elif output_format == 'yaml':
            click.echo('global: {}\nproject: {}')
        else:
            click.echo("No skills found")
        return

    # Extract context from each skill
    extractor = ContextExtractor()
    contexts: list[SkillContext] = []

    for key, entry in skills.items():
        ctx = extractor.extract_context(entry)
        contexts.append(ctx)

    # Output in requested format
    if output_format == 'yaml':
        click.echo(extractor.format_yaml(contexts))
    elif output_format == 'json':
        click.echo(extractor.format_json(contexts))
    elif output_format == 'table':
        click.echo(extractor.format_table(contexts, verbose=verbose))
    else:
        click.echo(extractor.format_text(
            contexts,
            indent=indent,
            wrap_width=wrap_width,
            verbose=verbose,
        ))


@cli.command()
@click.option('--file', 'skillset_file', default='skillset.yaml', help='Path to skillset file')
@click.option('--scope', type=click.Choice(['global', 'project']), help='Install only specified scope')
@click.option('--force', is_flag=True, help='Reinstall even if already installed')
@click.option('--strict', is_flag=True, help='Fail if version/ref not specified for any skill')
def install(skillset_file: str, scope: str, force: bool, strict: bool) -> None:
    """Install skills from skillset.yaml."""
    import os
    from datetime import datetime
    from asma.core.config import load_skillset
    from asma.core.installer import SkillInstaller
    from asma.core.sources.base import SourceHandler
    from asma.core.sources.local import LocalSourceHandler
    from asma.core.sources.github import GitHubSourceHandler
    from asma.models.skill import SkillScope
    from asma.models.lock import Lockfile, LockEntry

    skillset_path = Path(skillset_file)

    # Check if skillset file exists
    if not skillset_path.exists():
        click.echo(
            click.style("Error: ", fg="red", bold=True) +
            f"skillset.yaml not found: {skillset_path}"
        )
        click.echo("  Run 'asma init' to create one.")
        raise click.Abort()

    # Load skillset
    try:
        skillset = load_skillset(skillset_path)
    except Exception as e:
        click.echo(
            click.style("Error: ", fg="red", bold=True) +
            f"Failed to load skillset: {e}"
        )
        raise click.Abort()

    # Determine which skills to install
    skills_to_install = []
    if scope is None or scope == "global":
        skills_to_install.extend(skillset.global_skills)
    if scope is None or scope == "project":
        skills_to_install.extend(skillset.project_skills)

    if not skills_to_install:
        click.echo("No skills to install.")
        return

    # Load existing lock file
    lock_path = skillset_path.parent / "skillset.lock"
    lockfile = Lockfile.load(lock_path)

    # Install skills
    installer = SkillInstaller()
    success_count = 0
    fail_count = 0

    click.echo(f"Installing {len(skills_to_install)} skill(s)...")

    for skill in skills_to_install:
        # Determine install base
        if skill.scope == SkillScope.GLOBAL:
            install_base = Path.home() / ".claude/skills"
        else:
            install_base = Path.cwd() / ".claude/skills"

        # Get source handler
        # strict mode: CLI --strict flag OR skillset.yaml config.strict
        strict_mode = strict or skillset.config.strict

        source_handler: SourceHandler
        if skill.source.startswith("local:"):
            source_handler = LocalSourceHandler()
        elif skill.source.startswith("github:"):
            token = os.environ.get("GITHUB_TOKEN")
            source_handler = GitHubSourceHandler(token=token, strict=strict_mode)
        else:
            click.echo(
                click.style(f"✗ {skill.name}", fg="yellow") +
                f" - unsupported source: {skill.source}"
            )
            fail_count += 1
            continue

        # Install
        result = installer.install_skill(
            skill=skill,
            source_handler=source_handler,
            install_base=install_base,
            force=force
        )

        if result.success:
            click.echo(
                click.style(f"✓ {skill.name}", fg="green") +
                f" ({skill.scope.value})"
            )
            success_count += 1

            # Add to lock file
            if result.checksum:  # Only add if we have valid install info
                lock_entry = LockEntry(
                    name=skill.name,
                    scope=skill.scope,
                    source=skill.source,
                    resolved_version=result.version or "unknown",
                    resolved_commit=result.resolved_commit or "unknown",
                    installed_at=datetime.now(),
                    checksum=result.checksum,
                    symlink=result.symlink,
                    resolved_path=result.resolved_path
                )
                lockfile.add_entry(lock_entry)
        else:
            click.echo(
                click.style(f"✗ {skill.name}", fg="red") +
                f" - {result.error}"
            )
            fail_count += 1

    # Save lock file
    if success_count > 0:
        lockfile.save(lock_path)

    # Summary
    click.echo()
    if fail_count == 0:
        click.echo(click.style(f"Successfully installed {success_count} skill(s).", fg="green", bold=True))
    else:
        click.echo(
            f"Installed: {success_count} skill(s), " +
            click.style(f"Failed: {fail_count}", fg="red")
        )


@cli.command()
@click.argument('source')
@click.option('--global', 'is_global', is_flag=True, help='Install to global scope (~/.claude/skills/)')
@click.option('--scope', type=click.Choice(['global', 'project']), help='Installation scope')
@click.option('--force', is_flag=True, help='Overwrite existing skill in skillset.yaml')
@click.option('--name', 'custom_name', help='Override skill name from SKILL.md frontmatter')
@click.option('--file', 'skillset_file', default='skillset.yaml', help='Path to skillset file')
def add(
    source: str,
    is_global: bool,
    scope: str,
    force: bool,
    custom_name: str,
    skillset_file: str
) -> None:
    """Add a skill from source to skillset.yaml.

    SOURCE is a skill source in format:

    \b
      github:owner/repo[/path]   - GitHub repository
      local:/path/to/skill       - Local filesystem

    \b
    Examples:
      asma add github:anthropics/skills/skills/frontend-design
      asma add local:~/my-skills/custom-skill --global
      asma add github:owner/repo/skill --force --name my-skill
    """
    import os
    from asma.core.skill_fetcher import SkillFetcher
    from asma.core.skillset_writer import SkillsetWriter, SkillEntry
    from asma.models.skill import SkillScope

    # Determine scope (--global flag takes precedence)
    if is_global:
        target_scope = SkillScope.GLOBAL
    elif scope:
        target_scope = SkillScope.GLOBAL if scope == 'global' else SkillScope.PROJECT
    else:
        target_scope = SkillScope.PROJECT

    skillset_path = Path(skillset_file)

    # Check if skillset file exists
    if not skillset_path.exists():
        click.echo(
            click.style("Error: ", fg="red", bold=True) +
            f"skillset.yaml not found: {skillset_path}"
        )
        click.echo("  Run 'asma init' to create one.")
        raise click.Abort()

    # Fetch metadata from source
    click.echo(f"Fetching skill from {source}...")

    github_token = os.environ.get("GITHUB_TOKEN")
    fetcher = SkillFetcher(github_token=github_token)
    result = fetcher.fetch_metadata(source)

    if not result.success:
        click.echo(
            click.style("Error: ", fg="red", bold=True) +
            f"Failed to fetch skill: {result.error}"
        )
        raise click.Abort()

    # Use custom name if provided, otherwise use name from frontmatter
    skill_name = custom_name or result.name

    click.echo(f"Found skill: {skill_name}")
    if result.description:
        click.echo(f"Description: {result.description}")

    # Check if skill already exists
    writer = SkillsetWriter(skillset_path)

    if writer.skill_exists(skill_name, target_scope) and not force:
        click.echo(
            click.style("Error: ", fg="red", bold=True) +
            f"Skill '{skill_name}' already exists in {target_scope.value} scope."
        )
        click.echo("  Use --force to overwrite.")
        raise click.Abort()

    # Add skill to skillset.yaml
    # Don't include version for local sources (local@checksum format)
    version = None
    if result.version and not result.version.startswith("local@"):
        version = result.version

    entry = SkillEntry(
        name=skill_name,
        source=source,
        version=version
    )

    try:
        writer.add_skill(entry, target_scope, force=force)
    except Exception as e:
        click.echo(
            click.style("Error: ", fg="red", bold=True) +
            f"Failed to update skillset.yaml: {e}"
        )
        raise click.Abort()

    # Success message
    scope_display = "global" if target_scope == SkillScope.GLOBAL else "project"
    click.echo(
        click.style("✓ ", fg="green") +
        f"Added '{skill_name}' to {scope_display} scope"
    )
    click.echo("  Run 'asma install' to install the skill.")


if __name__ == "__main__":
    cli()
