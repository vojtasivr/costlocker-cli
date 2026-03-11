from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from costlocker_cli.config import load_config

console = Console()


def list_mappings_command() -> None:
    config = load_config()
    mappings = config.get("mappings", {}) if config else {}

    if not mappings:
        console.print("No mappings configured yet. Run `costlocker map` to add some.")
        raise typer.Exit(0)

    table = Table(title="Configured Mappings")
    table.add_column("Calendar Event", style="cyan")
    table.add_column("Costlocker Project", style="yellow")
    for event, mapping in mappings.items():
        table.add_row(event, mapping.get("name", ""))
    console.print(table)
