"""Allow ``python -m mining_brief_agent`` to run the CLI."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
