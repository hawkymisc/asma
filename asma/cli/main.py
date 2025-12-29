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
@click.option('--file', 'skillset_file', default='skillset.yaml', help='Path to skillset file')
@click.option('--scope', type=click.Choice(['global', 'project']), help='Install only specified scope')
@click.option('--force', is_flag=True, help='Reinstall even if already installed')
def install(skillset_file: str, scope: str, force: bool) -> None:
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
        source_handler: SourceHandler
        if skill.source.startswith("local:"):
            source_handler = LocalSourceHandler()
        elif skill.source.startswith("github:"):
            token = os.environ.get("GITHUB_TOKEN")
            source_handler = GitHubSourceHandler(token=token)
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


if __name__ == "__main__":
    cli()
