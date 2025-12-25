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
@click.option('--file', 'skillset_file', default='skillset.yaml', help='Path to skillset file')
@click.option('--scope', type=click.Choice(['global', 'project']), help='Install only specified scope')
@click.option('--force', is_flag=True, help='Reinstall even if already installed')
def install(skillset_file: str, scope: str, force: bool) -> None:
    """Install skills from skillset.yaml."""
    import os
    from asma.core.config import load_skillset
    from asma.core.installer import SkillInstaller
    from asma.core.sources.local import LocalSourceHandler
    from asma.core.sources.github import GitHubSourceHandler
    from asma.models.skill import SkillScope

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
        else:
            click.echo(
                click.style(f"✗ {skill.name}", fg="red") +
                f" - {result.error}"
            )
            fail_count += 1

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
