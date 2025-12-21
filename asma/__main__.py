"""Main entry point for asma CLI."""
import sys
from asma.cli.main import cli


def main() -> int:
    """Main entry point."""
    try:
        cli()
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
