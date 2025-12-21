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


if __name__ == "__main__":
    cli()
