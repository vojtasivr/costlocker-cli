from __future__ import annotations

from typing import Optional

import typer

from costlocker_cli.commands.list_mappings import list_mappings_command
from costlocker_cli.commands.map_cmd import map_command
from costlocker_cli.commands.sync import sync_command
from costlocker_cli.config import setup_config

app = typer.Typer(help="Sync Google Calendar events to Costlocker timesheets", no_args_is_help=True)


@app.command()
def sync(
    date_str: Optional[str] = typer.Option(None, "--date", "-d", help="Date to sync (YYYY-MM-DD). Defaults to today."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview what would be logged without actually logging it."),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactively confirm each event before logging."),
) -> None:
    """Fetch Google Calendar events and log them to Costlocker."""
    sync_command(date_str, dry_run, interactive)


@app.command()
def setup() -> None:
    """Interactive setup — configure API keys and calendar access."""
    setup_config()


@app.command()
def map() -> None:
    """Manage mappings between calendar event names and Costlocker projects."""
    map_command()


@app.command()
def list_mappings() -> None:
    """List mappings between calendar event names and Costlocker projects."""
    list_mappings_command()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
